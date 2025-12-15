"""
PDF Generation for Schedules
Generates formatted PDF documents for schedule generations
"""

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from collections import defaultdict

from .models import ScheduleGeneration, ScheduleSession, TimeSlot


class SchedulePDFGenerator:
    """Generate PDF documents for schedule generations"""

    def __init__(self, generation_id):
        self.generation = ScheduleGeneration.objects.select_related(
            'academic_period'
        ).get(id=generation_id)
        self.sessions = ScheduleSession.objects.filter(
            schedule_generation=self.generation
        ).select_related(
            'time_slot', 'teacher__user', 'subject_group__subject',
            'classroom', 'teacher_assignment'
        ).order_by('time_slot__day_of_week', 'time_slot__start_time')

    def generate(self):
        """Generate the PDF and return as BytesIO buffer"""
        buffer = BytesIO()

        # Create document with landscape orientation
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        # Container for the 'Flowable' objects
        elements = []

        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        # Title
        title = Paragraph(
            f"Horario Académico - {self.generation.academic_period.name}",
            title_style
        )
        elements.append(title)

        # Generation info
        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=20
        )

        generation_date = self.generation.started_at.strftime('%d/%m/%Y %H:%M')
        info_text = f"Generación #{self.generation.id} | Fecha: {generation_date} | Éxito: {self.generation.success_rate:.1f}%"
        info = Paragraph(info_text, info_style)
        elements.append(info)

        # Add schedule grid
        elements.append(Spacer(1, 0.2*inch))
        schedule_table = self._create_schedule_table()
        elements.append(schedule_table)

        # Add statistics on next page
        elements.append(PageBreak())
        elements.append(Paragraph("Estadísticas de la Generación", title_style))
        elements.append(Spacer(1, 0.2*inch))
        stats_table = self._create_statistics_table()
        elements.append(stats_table)

        # Build PDF
        doc.build(elements)

        # Return buffer
        buffer.seek(0)
        return buffer

    def _create_schedule_table(self):
        """Create the main schedule grid table"""
        DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

        # Get unique time slots
        time_slots = TimeSlot.objects.filter(
            id__in=self.sessions.values_list('time_slot_id', flat=True)
        ).order_by('start_time').distinct('start_time')

        # Structure: {day: {time: [sessions]}}
        grid = defaultdict(lambda: defaultdict(list))

        for session in self.sessions:
            day = session.time_slot.day_of_week
            time_key = session.time_slot.start_time.strftime('%H:%M')

            session_info = (
                f"{session.subject_group.subject.code}\n"
                f"{session.subject_group.subject.name}\n"
                f"Grupo: {session.subject_group.code}\n"
                f"Prof: {session.teacher.user.get_full_name()}\n"
                f"Aula: {session.classroom.code}"
            )

            grid[day][time_key].append(session_info)

        # Build table data
        unique_times = sorted(set(
            session.time_slot.start_time.strftime('%H:%M')
            for session in self.sessions
        ))

        # Header row
        header = ['Hora'] + DAYS
        data = [header]

        # Data rows
        for time_str in unique_times:
            row = [time_str]
            for day_idx in range(len(DAYS)):
                sessions_at_time = grid[day_idx].get(time_str, [])
                if sessions_at_time:
                    cell_content = '\n\n'.join(sessions_at_time)
                else:
                    cell_content = '-'
                row.append(cell_content)
            data.append(row)

        # Create table
        table = Table(data, repeatRows=1)

        # Style the table
        table_style = TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

            # Time column styling
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e5e7eb')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (0, -1), 8),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),

            # Data cells styling
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (1, 1), (-1, -1), 7),
            ('ALIGN', (1, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (1, 1), (-1, -1), 'TOP'),
            ('LEFTPADDING', (1, 1), (-1, -1), 5),
            ('RIGHTPADDING', (1, 1), (-1, -1), 5),
            ('TOPPADDING', (1, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (1, 1), (-1, -1), 5),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ])

        table.setStyle(table_style)

        return table

    def _create_statistics_table(self):
        """Create statistics summary table"""
        # Calculate statistics
        total_sessions = self.sessions.count()
        unique_teachers = self.sessions.values('teacher').distinct().count()
        unique_groups = self.sessions.values('subject_group').distinct().count()
        unique_classrooms = self.sessions.values('classroom').distinct().count()

        # Sessions by day
        sessions_by_day = {}
        for day in range(7):
            count = self.sessions.filter(time_slot__day_of_week=day).count()
            if count > 0:
                sessions_by_day[TimeSlot.WEEKDAY_CHOICES[day][1]] = count

        # Build statistics table
        data = [
            ['Estadística', 'Valor'],
            ['Total de Sesiones', str(total_sessions)],
            ['Profesores Únicos', str(unique_teachers)],
            ['Grupos Únicos', str(unique_groups)],
            ['Aulas Utilizadas', str(unique_classrooms)],
            ['Tasa de Éxito', f"{self.generation.success_rate:.1f}%"],
            ['Tiempo de Ejecución', f"{self.generation.execution_time_seconds:.2f}s"],
            ['Score de Optimización', f"{self.generation.optimization_score or 0:.1f}/100"],
            ['Conflictos Detectados', str(len(self.generation.conflicts_detected))],
            ['Advertencias', str(len(self.generation.warnings))],
        ]

        # Add sessions by day
        for day_name, count in sessions_by_day.items():
            data.append([f'Sesiones {day_name}', str(count)])

        # Create table
        table = Table(data, colWidths=[4*inch, 2*inch])

        # Style the table
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 1), (-1, -1), 10),
            ('RIGHTPADDING', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),

            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),

            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ])

        table.setStyle(table_style)

        return table
