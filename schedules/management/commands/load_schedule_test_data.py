"""
Django management command to load test data for the schedule generation system
Usage: python manage.py load_schedule_test_data [--clean]
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import datetime, time

from academic.models import AcademicPeriod, Career, Subject, Classroom
from users.models import Teacher, Student
from enrollment.models import SubjectGroup, CareerEnrollment, SubjectEnrollment
from schedules.models import TimeSlot, TeacherAssignment, ScheduleConfiguration, ScheduleGeneration, ScheduleSession
from grades.models import Evaluation, Grade, FinalGrade
from notifications.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga datos de prueba para el sistema de generación de horarios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Elimina todos los datos existentes (excepto el usuario admin) antes de cargar los nuevos',
        )

    def clean_database(self):
        """Elimina todos los datos excepto el usuario admin"""
        self.stdout.write(self.style.WARNING('\n' + '=' * 60))
        self.stdout.write(self.style.WARNING('LIMPIANDO BASE DE DATOS'))
        self.stdout.write(self.style.WARNING('=' * 60))

        # Orden de eliminación basado en dependencias
        models_to_clean = [
            (ScheduleSession, 'Sesiones de Horario'),
            (ScheduleGeneration, 'Generaciones de Horario'),
            (ScheduleConfiguration, 'Configuraciones CSP'),
            (TimeSlot, 'Franjas Horarias'),
            (TeacherAssignment, 'Asignaciones de Profesores'),
            (SubjectEnrollment, 'Inscripciones a Materias'),
            (CareerEnrollment, 'Inscripciones a Carreras'),
            (Grade, 'Calificaciones'),
            (FinalGrade, 'Calificaciones Finales'),
            (Evaluation, 'Evaluaciones'),
            (Notification, 'Notificaciones'),
            (SubjectGroup, 'Grupos de Materias'),
            (Student, 'Estudiantes'),
            (Teacher, 'Profesores'),
            (Subject, 'Materias'),
            (Classroom, 'Aulas'),
            (Career, 'Carreras'),
            (AcademicPeriod, 'Períodos Académicos'),
        ]

        for model, name in models_to_clean:
            count = model.objects.all().delete()[0]
            self.stdout.write(f'   🗑️  {name}: {count} eliminados')

        # Eliminar usuarios excepto admin
        admin_users = User.objects.filter(role='admin')
        non_admin_users = User.objects.exclude(role='admin')
        count = non_admin_users.count()
        non_admin_users.delete()
        self.stdout.write(f'   🗑️  Usuarios (no admin): {count} eliminados')
        self.stdout.write(self.style.SUCCESS(f'   ✓ Usuarios admin preservados: {admin_users.count()}'))

        self.stdout.write(self.style.SUCCESS('\n✓ Base de datos limpiada exitosamente\n'))

    def handle(self, *args, **options):
        # Limpiar base de datos si se especifica --clean
        if options['clean']:
            self.clean_database()

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('CARGANDO DATOS DE PRUEBA PARA GENERACIÓN DE HORARIOS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 1. Crear Períodos Académicos (5 períodos)
        self.stdout.write('\n[1/12] Creando Períodos Académicos...')
        periods_data = [
            {'name': '2024-2025 Primer Cuatrimestre', 'code': '2024-1', 'year': 2024, 'month_start': 9, 'month_end': 1, 'year_end': 2025},
            {'name': '2024-2025 Segundo Cuatrimestre', 'code': '2024-2', 'year': 2025, 'month_start': 2, 'month_end': 6, 'year_end': 2025},
            {'name': '2025-2026 Primer Cuatrimestre', 'code': '2025-1', 'year': 2025, 'month_start': 9, 'month_end': 1, 'year_end': 2026},
            {'name': '2025-2026 Segundo Cuatrimestre', 'code': '2025-2', 'year': 2026, 'month_start': 2, 'month_end': 6, 'year_end': 2026},
            {'name': '2026-2027 Primer Cuatrimestre', 'code': '2026-1', 'year': 2026, 'month_start': 9, 'month_end': 1, 'year_end': 2027},
        ]

        periods = []
        for period_data in periods_data:
            period, created = AcademicPeriod.objects.get_or_create(
                name=period_data['name'],
                defaults={
                    'code': period_data['code'],
                    'start_date': datetime(period_data['year'], period_data['month_start'], 1).date(),
                    'end_date': datetime(period_data['year_end'], period_data['month_end'], 28).date(),
                    'enrollment_start': datetime(period_data['year'], period_data['month_start'] - 1, 1).date() if period_data['month_start'] > 1 else datetime(period_data['year'] - 1, 12, 1).date(),
                    'enrollment_end': datetime(period_data['year'], period_data['month_start'] - 1, 28).date() if period_data['month_start'] > 1 else datetime(period_data['year'] - 1, 12, 31).date(),
                    'is_active': True,
                }
            )
            periods.append(period)
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Período académico creado: {period.name}'))

        # 2. Crear Carreras (5 carreras)
        self.stdout.write('\n[2/12] Creando Carreras...')
        careers_data = [
            {'code': 'ISC', 'name': 'Ingeniería en Sistemas Computacionales', 'description': 'Carrera de Ingeniería en Sistemas', 'duration_years': 4, 'total_credits': 240},
            {'code': 'IND', 'name': 'Ingeniería Industrial', 'description': 'Carrera de Ingeniería Industrial', 'duration_years': 4, 'total_credits': 240},
            {'code': 'IME', 'name': 'Ingeniería Mecatrónica', 'description': 'Carrera de Ingeniería Mecatrónica', 'duration_years': 4, 'total_credits': 240},
            {'code': 'IEL', 'name': 'Ingeniería Electrónica', 'description': 'Carrera de Ingeniería Electrónica', 'duration_years': 4, 'total_credits': 240},
            {'code': 'ARQ', 'name': 'Arquitectura', 'description': 'Carrera de Arquitectura', 'duration_years': 5, 'total_credits': 300},
        ]

        careers = []
        for career_data in careers_data:
            career, created = Career.objects.get_or_create(
                code=career_data['code'],
                defaults={
                    'name': career_data['name'],
                    'description': career_data['description'],
                    'duration_years': career_data['duration_years'],
                    'total_credits': career_data['total_credits'],
                    'is_active': True,
                }
            )
            careers.append(career)
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Carrera creada: {career.name}'))

        # 3. Crear Materias (50 materias)
        self.stdout.write('\n[3/12] Creando Materias...')
        subjects_data = [
            # Matemáticas y Ciencias Básicas (10)
            {'code': 'MAT101', 'name': 'Cálculo Diferencial', 'credits': 6, 'course_year': 1, 'semester': 1},
            {'code': 'MAT102', 'name': 'Cálculo Integral', 'credits': 6, 'course_year': 1, 'semester': 2},
            {'code': 'MAT201', 'name': 'Álgebra Lineal', 'credits': 5, 'course_year': 2, 'semester': 1},
            {'code': 'MAT202', 'name': 'Ecuaciones Diferenciales', 'credits': 5, 'course_year': 2, 'semester': 2},
            {'code': 'MAT301', 'name': 'Probabilidad y Estadística', 'credits': 5, 'course_year': 3, 'semester': 1},
            {'code': 'FIS101', 'name': 'Física I', 'credits': 5, 'course_year': 1, 'semester': 1},
            {'code': 'FIS102', 'name': 'Física II', 'credits': 5, 'course_year': 1, 'semester': 2},
            {'code': 'QUI101', 'name': 'Química', 'credits': 4, 'course_year': 1, 'semester': 1},
            {'code': 'BIO101', 'name': 'Biología', 'credits': 4, 'course_year': 1, 'semester': 2},
            {'code': 'EST201', 'name': 'Métodos Numéricos', 'credits': 5, 'course_year': 2, 'semester': 2},

            # Programación y Desarrollo de Software (10)
            {'code': 'PROG101', 'name': 'Fundamentos de Programación', 'credits': 6, 'course_year': 1, 'semester': 1},
            {'code': 'PROG102', 'name': 'Programación Orientada a Objetos', 'credits': 6, 'course_year': 1, 'semester': 2},
            {'code': 'PROG201', 'name': 'Estructuras de Datos', 'credits': 6, 'course_year': 2, 'semester': 1},
            {'code': 'PROG202', 'name': 'Algoritmos Avanzados', 'credits': 5, 'course_year': 2, 'semester': 2},
            {'code': 'WEB101', 'name': 'Desarrollo Web Frontend', 'credits': 5, 'course_year': 2, 'semester': 1},
            {'code': 'WEB201', 'name': 'Desarrollo Web Backend', 'credits': 5, 'course_year': 2, 'semester': 2},
            {'code': 'MOV101', 'name': 'Desarrollo de Aplicaciones Móviles', 'credits': 5, 'course_year': 3, 'semester': 1},
            {'code': 'GAME101', 'name': 'Desarrollo de Videojuegos', 'credits': 5, 'course_year': 3, 'semester': 2},
            {'code': 'IA101', 'name': 'Inteligencia Artificial', 'credits': 6, 'course_year': 3, 'semester': 2},
            {'code': 'ML101', 'name': 'Machine Learning', 'credits': 6, 'course_year': 4, 'semester': 1},

            # Bases de Datos y Sistemas (10)
            {'code': 'BD101', 'name': 'Bases de Datos', 'credits': 5, 'course_year': 2, 'semester': 1},
            {'code': 'BD201', 'name': 'Bases de Datos Avanzadas', 'credits': 5, 'course_year': 3, 'semester': 1},
            {'code': 'SO101', 'name': 'Sistemas Operativos', 'credits': 5, 'course_year': 2, 'semester': 2},
            {'code': 'RED101', 'name': 'Redes de Computadoras', 'credits': 5, 'course_year': 3, 'semester': 1},
            {'code': 'RED201', 'name': 'Administración de Redes', 'credits': 5, 'course_year': 3, 'semester': 2},
            {'code': 'SEG101', 'name': 'Seguridad Informática', 'credits': 5, 'course_year': 3, 'semester': 2},
            {'code': 'CLOUD101', 'name': 'Computación en la Nube', 'credits': 5, 'course_year': 4, 'semester': 1},
            {'code': 'ARQ101', 'name': 'Arquitectura de Computadoras', 'credits': 5, 'course_year': 2, 'semester': 1},
            {'code': 'DIST101', 'name': 'Sistemas Distribuidos', 'credits': 5, 'course_year': 4, 'semester': 1},
            {'code': 'BIG101', 'name': 'Big Data', 'credits': 5, 'course_year': 4, 'semester': 2},

            # Ingeniería de Software (10)
            {'code': 'ING101', 'name': 'Ingeniería de Software I', 'credits': 5, 'course_year': 2, 'semester': 2},
            {'code': 'ING201', 'name': 'Ingeniería de Software II', 'credits': 5, 'course_year': 3, 'semester': 1},
            {'code': 'REQ101', 'name': 'Análisis de Requerimientos', 'credits': 4, 'course_year': 2, 'semester': 2},
            {'code': 'DIS101', 'name': 'Diseño de Software', 'credits': 5, 'course_year': 3, 'semester': 1},
            {'code': 'PRUE101', 'name': 'Pruebas de Software', 'credits': 4, 'course_year': 3, 'semester': 2},
            {'code': 'AGIL101', 'name': 'Metodologías Ágiles', 'credits': 4, 'course_year': 3, 'semester': 2},
            {'code': 'DEVOPS101', 'name': 'DevOps', 'credits': 5, 'course_year': 4, 'semester': 1},
            {'code': 'CAL101', 'name': 'Calidad de Software', 'credits': 4, 'course_year': 4, 'semester': 1},
            {'code': 'GES101', 'name': 'Gestión de Proyectos', 'credits': 5, 'course_year': 4, 'semester': 2},
            {'code': 'MANT101', 'name': 'Mantenimiento de Software', 'credits': 4, 'course_year': 4, 'semester': 2},

            # Humanidades y Administración (10)
            {'code': 'COM101', 'name': 'Comunicación Oral y Escrita', 'credits': 4, 'course_year': 1, 'semester': 1},
            {'code': 'ING100', 'name': 'Inglés I', 'credits': 3, 'course_year': 1, 'semester': 1},
            {'code': 'ING200', 'name': 'Inglés II', 'credits': 3, 'course_year': 1, 'semester': 2},
            {'code': 'ADM101', 'name': 'Fundamentos de Administración', 'credits': 4, 'course_year': 2, 'semester': 1},
            {'code': 'CONT101', 'name': 'Contabilidad', 'credits': 4, 'course_year': 2, 'semester': 1},
            {'code': 'ECO101', 'name': 'Economía', 'credits': 4, 'course_year': 2, 'semester': 2},
            {'code': 'DER101', 'name': 'Derecho Informático', 'credits': 3, 'course_year': 3, 'semester': 1},
            {'code': 'ETI101', 'name': 'Ética Profesional', 'credits': 3, 'course_year': 3, 'semester': 2},
            {'code': 'EMP101', 'name': 'Emprendimiento', 'credits': 4, 'course_year': 4, 'semester': 1},
            {'code': 'PROY101', 'name': 'Proyecto Final', 'credits': 10, 'course_year': 4, 'semester': 2},
        ]

        subjects = []
        for subj_data in subjects_data:
            subj, created = Subject.objects.get_or_create(
                code=subj_data['code'],
                defaults={
                    'name': subj_data['name'],
                    'credits': subj_data['credits'],
                    'course_year': subj_data['course_year'],
                    'semester': subj_data['semester'],
                    'is_active': True,
                }
            )
            subjects.append(subj)
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Materia creada: {subj.code} - {subj.name}'))

        # 4. Crear Aulas (50 aulas)
        self.stdout.write('\n[4/12] Creando Aulas...')
        classrooms_data = []

        # Edificio A - Aulas tradicionales (10 aulas)
        for i in range(1, 11):
            classrooms_data.append({
                'code': f'A{i:03d}',
                'name': f'Aula A-{i:03d}',
                'building': 'Edificio A',
                'capacity': 35 if i <= 5 else 40
            })

        # Edificio B - Aulas tradicionales (10 aulas)
        for i in range(1, 11):
            classrooms_data.append({
                'code': f'B{i:03d}',
                'name': f'Aula B-{i:03d}',
                'building': 'Edificio B',
                'capacity': 30 if i <= 5 else 35
            })

        # Edificio C - Laboratorios de Cómputo (10 laboratorios)
        for i in range(1, 11):
            classrooms_data.append({
                'code': f'LAB{i:03d}',
                'name': f'Laboratorio de Cómputo {i}',
                'building': 'Edificio C - Laboratorios',
                'capacity': 25
            })

        # Edificio D - Laboratorios de Física y Química (10 laboratorios)
        lab_types = ['Física', 'Química', 'Electrónica', 'Mecánica', 'Materiales']
        for i in range(1, 11):
            lab_type = lab_types[(i-1) % len(lab_types)]
            classrooms_data.append({
                'code': f'LABF{i:03d}',
                'name': f'Laboratorio de {lab_type} {((i-1) // len(lab_types)) + 1}',
                'building': 'Edificio D - Laboratorios',
                'capacity': 20
            })

        # Edificio E - Aulas especiales (10 aulas)
        special_rooms = [
            {'code': 'AUD001', 'name': 'Auditorio Principal', 'capacity': 200},
            {'code': 'AUD002', 'name': 'Auditorio Secundario', 'capacity': 150},
            {'code': 'SAL001', 'name': 'Sala de Conferencias 1', 'capacity': 50},
            {'code': 'SAL002', 'name': 'Sala de Conferencias 2', 'capacity': 50},
            {'code': 'TAL001', 'name': 'Taller de Diseño 1', 'capacity': 30},
            {'code': 'TAL002', 'name': 'Taller de Diseño 2', 'capacity': 30},
            {'code': 'BIB001', 'name': 'Sala de Estudio Biblioteca 1', 'capacity': 40},
            {'code': 'BIB002', 'name': 'Sala de Estudio Biblioteca 2', 'capacity': 40},
            {'code': 'MULT01', 'name': 'Sala Multimedia 1', 'capacity': 35},
            {'code': 'MULT02', 'name': 'Sala Multimedia 2', 'capacity': 35},
        ]
        for room in special_rooms:
            classrooms_data.append({
                'code': room['code'],
                'name': room['name'],
                'building': 'Edificio E - Espacios Especiales',
                'capacity': room['capacity']
            })

        classrooms = []
        for class_data in classrooms_data:
            classroom, created = Classroom.objects.get_or_create(
                code=class_data['code'],
                defaults={
                    'name': class_data['name'],
                    'building': class_data['building'],
                    'capacity': class_data['capacity'],
                    'is_active': True,
                }
            )
            classrooms.append(classroom)
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Aula creada: {classroom.code} - {classroom.name}'))

        # 5. Crear Profesores (40 profesores)
        self.stdout.write('\n[5/11] Creando Profesores...')

        # Definir departamentos y nombres
        departments = ['Matemáticas', 'Sistemas', 'Física', 'Química', 'Humanidades', 'Industrial', 'Mecatrónica', 'Electrónica']
        first_names = ['Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Laura', 'Pedro', 'Sofia', 'Miguel', 'Carmen',
                      'José', 'Isabel', 'Antonio', 'Elena', 'Francisco', 'Patricia', 'Manuel', 'Rosa', 'David', 'Lucía',
                      'Javier', 'Marta', 'Sergio', 'Cristina', 'Roberto', 'Silvia', 'Fernando', 'Beatriz', 'Alberto', 'Pilar',
                      'Raúl', 'Teresa', 'Alejandro', 'Mónica', 'Pablo', 'Adriana', 'Jorge', 'Nuria', 'Daniel', 'Victoria']
        last_names = ['García', 'Martínez', 'Rodríguez', 'López', 'González', 'Fernández', 'Sánchez', 'Ramírez', 'Torres', 'Flores',
                     'Díaz', 'Morales', 'Jiménez', 'Álvarez', 'Romero', 'Ruiz', 'Hernández', 'Navarro', 'Domínguez', 'Gil',
                     'Castro', 'Ortiz', 'Rubio', 'Molina', 'Delgado', 'Moreno', 'Suárez', 'Ortega', 'Peña', 'Vega',
                     'Medina', 'Campos', 'Guerrero', 'Cortés', 'Vargas', 'Reyes', 'Cruz', 'Santos', 'Núñez', 'Mendoza']

        teachers_data = []
        for i in range(40):
            dept = departments[i % len(departments)]
            teachers_data.append({
                'username': f'prof.{last_names[i].lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")}{i+1}',
                'first_name': first_names[i],
                'last_name': last_names[i],
                'email': f'{first_names[i].lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")}.{last_names[i].lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")}{i+1}@academix.edu',
                'employee_id': f'P{(i+1):03d}',
                'department': dept
            })

        teachers = []
        for teacher_data in teachers_data:
            user, user_created = User.objects.get_or_create(
                username=teacher_data['username'],
                defaults={
                    'first_name': teacher_data['first_name'],
                    'last_name': teacher_data['last_name'],
                    'email': teacher_data['email'],
                    'role': 'teacher',
                    'phone': '5551234567',
                }
            )
            if user_created:
                user.set_password('password123')
                user.save()

            teacher, created = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': teacher_data['employee_id'],
                    'department': teacher_data['department'],
                    'hire_date': datetime(2023, 1, 1).date(),
                    'status': 'active',
                }
            )
            teachers.append(teacher)
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Profesor creado: {teacher.user.get_full_name()} ({teacher.department})'))

        # 6. Crear Estudiantes (100 estudiantes)
        self.stdout.write('\n[6/11] Creando Estudiantes...')

        student_first_names = [
            'Andrés', 'Beatriz', 'Carlos', 'Diana', 'Eduardo', 'Fernanda', 'Gabriel', 'Helena', 'Iván', 'Julia',
            'Kevin', 'Lorena', 'Mario', 'Natalia', 'Oscar', 'Paula', 'Ramón', 'Sandra', 'Tomás', 'Valeria',
            'Walter', 'Ximena', 'Yolanda', 'Zacarías', 'Adriana', 'Bruno', 'Cecilia', 'Diego', 'Elisa', 'Felipe',
            'Gabriela', 'Héctor', 'Irene', 'Javier', 'Karen', 'Leonardo', 'Mariana', 'Nicolás', 'Olivia', 'Pablo',
            'Quintín', 'Raquel', 'Samuel', 'Tatiana', 'Ulises', 'Verónica', 'William', 'Xiomara', 'Yamila', 'Zoe',
            'Alberto', 'Brenda', 'César', 'Daniela', 'Emilio', 'Fabiola', 'Gonzalo', 'Hugo', 'Isabel', 'Jorge',
            'Karla', 'Luis', 'Mónica', 'Néstor', 'Olga', 'Pedro', 'Quetzal', 'Ricardo', 'Silvia', 'Teresa',
            'Uriel', 'Victoria', 'Xavier', 'Yesenia', 'Zaira', 'Alma', 'Benito', 'Clara', 'Dante', 'Eva',
            'Francisco', 'Gisela', 'Horacio', 'Ingrid', 'José', 'Karina', 'Lorenzo', 'Marisol', 'Norberto', 'Patricia',
            'Rafael', 'Sofía', 'Tania', 'Úrsula', 'Vicente', 'Wendy', 'Yadira', 'Zamira', 'Ángel', 'Blanca'
        ]

        student_last_names = [
            'Acosta', 'Benítez', 'Carrillo', 'Durán', 'Espinosa', 'Franco', 'Guzmán', 'Herrera', 'Ibarra', 'Juárez',
            'Kuri', 'Lara', 'Mendoza', 'Núñez', 'Olivares', 'Padilla', 'Quintero', 'Rivas', 'Silva', 'Téllez',
            'Ugalde', 'Vázquez', 'Wong', 'Ximénez', 'Yáñez', 'Zavala', 'Alonso', 'Bernal', 'Campos', 'Duarte',
            'Elizondo', 'Fuentes', 'Gallardo', 'Hinojosa', 'Iglesias', 'Jaramillo', 'Karam', 'León', 'Mata', 'Navarrete',
            'Ochoa', 'Parra', 'Quesada', 'Rojas', 'Salinas', 'Treviño', 'Uribe', 'Valdez', 'Walls', 'Xochitl',
            'Yunes', 'Zúñiga', 'Aguilar', 'Bravo', 'Cárdenas', 'Delgadillo', 'Escobar', 'Figueroa', 'Galindo', 'Huerta',
            'Iturbe', 'Jiménez', 'Kelly', 'Lomelí', 'Maldonado', 'Nava', 'Ontiveros', 'Pérez', 'Quiroz', 'Ramírez',
            'Sandoval', 'Torres', 'Ulloa', 'Varela', 'Werner', 'Xalapa', 'Ybarra', 'Zapata', 'Arce', 'Burgos',
            'Camacho', 'Dávalos', 'Enríquez', 'Flores', 'Garza', 'Hernández', 'Iñiguez', 'Jurado', 'Kauffman', 'López',
            'Moreno', 'Negrete', 'Orellana', 'Ponce', 'Quiroga', 'Reyna', 'Soto', 'Trujillo', 'Urban', 'Villegas'
        ]

        students_data = []
        for i in range(100):
            career_idx = i % len(careers)
            students_data.append({
                'username': f'est.{student_last_names[i].lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")}{i+1}',
                'first_name': student_first_names[i],
                'last_name': student_last_names[i],
                'email': f'{student_first_names[i].lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")}.{student_last_names[i].lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")}{i+1}@estudiantes.academix.edu',
                'student_id': f'E{(i+1):05d}',
                'career': careers[career_idx]
            })

        students = []
        for student_data in students_data:
            user, user_created = User.objects.get_or_create(
                username=student_data['username'],
                defaults={
                    'first_name': student_data['first_name'],
                    'last_name': student_data['last_name'],
                    'email': student_data['email'],
                    'role': 'student',
                    'phone': '5559876543',
                }
            )
            if user_created:
                user.set_password('password123')
                user.save()

            student, created = Student.objects.get_or_create(
                user=user,
                defaults={
                    'student_id': student_data['student_id'],
                    'status': 'active',
                }
            )
            students.append((student, student_data['career']))
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Estudiante creado: {student.user.get_full_name()} - {student.student_id}'))

        # 7. Crear Grupos de Materias (80 grupos = 16 por período)
        self.stdout.write('\n[7/11] Creando Grupos de Materias...')
        subject_groups = []

        # Para cada período, crear 16 grupos usando las primeras 8 materias con 2 grupos cada una
        for period in periods:
            for idx, subject in enumerate(subjects[:8]):
                for group_num in range(1, 3):
                    group_code = f"{subject.code}-{period.code}-G{group_num}"
                    group, created = SubjectGroup.objects.get_or_create(
                        code=group_code,
                        subject=subject,
                        academic_period=period,
                        defaults={
                            'max_capacity': 30,
                            'current_enrollment': 0,
                            'is_active': True,
                        }
                    )
                    subject_groups.append(group)
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'   ✓ Grupo creado: {group_code}'))

        # 8. Crear Asignaciones de Profesores a Grupos
        self.stdout.write('\n[8/11] Creando Asignaciones de Profesores...')

        for idx, group in enumerate(subject_groups):
            teacher = teachers[idx % len(teachers)]
            hours_per_week = group.subject.credits

            assignment, created = TeacherAssignment.objects.get_or_create(
                teacher=teacher,
                subject_group=group,
                defaults={
                    'weekly_hours': hours_per_week,
                    'status': 'active',
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Asignación: {teacher.user.get_full_name()} -> {group.code} ({hours_per_week}h/semana)'))

        # 9. Crear Franjas Horarias (para todos los períodos)
        self.stdout.write('\n[9/11] Creando Franjas Horarias...')

        days = [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
        ]

        start_hour = 7
        end_hour = 16

        timeslot_count = 0
        for period in periods:
            for day_num, day_name in days:
                for hour in range(start_hour, end_hour):
                    start_time = time(hour, 0)
                    end_time = time(hour + 1, 0)
                    slot_code = f"{day_name[:3].upper()}-{hour:02d}:00-{period.code}"

                    timeslot, created = TimeSlot.objects.get_or_create(
                        academic_period=period,
                        day_of_week=day_num,
                        start_time=start_time,
                        end_time=end_time,
                        defaults={
                            'slot_code': slot_code,
                            'is_active': True,
                        }
                    )
                    if created:
                        timeslot_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {timeslot_count} franjas horarias creadas'))

        # 10. Crear Restricciones de Disponibilidad de Profesores (ejemplos)
        self.stdout.write('\n[10/13] Creando Restricciones de Disponibilidad de Profesores...')

        from schedules.models import TeacherAvailability

        # Ejemplo 1: Profesor completamente no disponible (de permiso)
        if len(teachers) >= 5:
            avail1, created = TeacherAvailability.objects.get_or_create(
                teacher=teachers[4],
                academic_period=periods[0],
                defaults={
                    'availability_type': 'unavailable',
                    'restriction_reason': 'De permiso médico',
                    'notes': 'No disponible para el primer período académico',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Restricción creada: {teachers[4].user.get_full_name()} - No disponible'))

        # Ejemplo 2: Profesor con disponibilidad restringida (medio tiempo)
        if len(teachers) >= 10:
            # Get time slots for morning only (7:00-12:00)
            morning_slots = TimeSlot.objects.filter(
                academic_period=periods[0],
                start_time__hour__lt=12
            )

            avail2, created = TeacherAvailability.objects.get_or_create(
                teacher=teachers[9],
                academic_period=periods[0],
                defaults={
                    'availability_type': 'restricted',
                    'max_teaching_hours': 15,
                    'restriction_reason': 'Medio tiempo - Solo mañanas',
                    'notes': 'Disponible solo en horario matutino',
                    'is_active': True
                }
            )
            if created:
                avail2.available_time_slots.set(morning_slots)
                self.stdout.write(self.style.SUCCESS(f'   ✓ Restricción creada: {teachers[9].user.get_full_name()} - Restringido (mañanas)'))

        # Ejemplo 3: Profesor con días bloqueados
        if len(teachers) >= 15:
            avail3, created = TeacherAvailability.objects.get_or_create(
                teacher=teachers[14],
                academic_period=periods[0],
                defaults={
                    'availability_type': 'restricted',
                    'max_teaching_hours': 20,
                    'blocked_days': [2, 4],  # Miércoles y Viernes bloqueados
                    'restriction_reason': 'Compromiso académico externo',
                    'notes': 'No puede dar clases miércoles y viernes',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Restricción creada: {teachers[14].user.get_full_name()} - Días bloqueados (Miércoles, Viernes)'))

        # Ejemplo 4: Profesor con límite de horas
        if len(teachers) >= 20:
            avail4, created = TeacherAvailability.objects.get_or_create(
                teacher=teachers[19],
                academic_period=periods[0],
                defaults={
                    'availability_type': 'full',
                    'max_teaching_hours': 12,
                    'restriction_reason': 'Carga administrativa adicional',
                    'notes': 'Máximo 12 horas semanales por rol administrativo',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Restricción creada: {teachers[19].user.get_full_name()} - Máx 12 horas'))

        self.stdout.write(self.style.SUCCESS(f'   ✓ Restricciones de disponibilidad configuradas'))

        # 11. Crear Planes de Estudio
        self.stdout.write('\n[11/13] Creando Planes de Estudio...')
        study_plans = {}

        from academic.models import StudyPlan

        for career in careers:
            plan, created = StudyPlan.objects.get_or_create(
                career=career,
                code=f'{career.code}-2024',
                defaults={
                    'name': f'Plan de Estudios {career.code} 2024',
                    'start_year': 2024,
                    'is_active': True,
                }
            )
            study_plans[career.code] = plan
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Plan de estudios creado: {plan.name}'))

        # 12. Inscribir Estudiantes a Carreras
        self.stdout.write('\n[12/13] Creando Inscripciones a Carreras...')
        career_enrollments = {}

        for student, career in students:
            study_plan = study_plans[career.code]
            enrollment, created = CareerEnrollment.objects.get_or_create(
                student=student,
                career=career,
                study_plan=study_plan,
                defaults={
                    'status': 'active',
                }
            )
            career_enrollments[student.id] = enrollment
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Inscripción creada: {student.user.get_full_name()} -> {career.code}'))

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(career_enrollments)} inscripciones a carreras creadas'))

        # 13. Inscribir Estudiantes a Materias (inscribir a los grupos del primer período)
        self.stdout.write('\n[13/13] Creando Inscripciones a Materias...')
        subject_enrollments = []

        # Filtrar los grupos del primer período
        first_period_groups = [g for g in subject_groups if g.academic_period == periods[0]]

        # Inscribir estudiantes a los grupos (distribuir uniformemente)
        for idx, (student, career) in enumerate(students[:len(first_period_groups) * 15]):  # 15 estudiantes por grupo máximo
            group_idx = idx % len(first_period_groups)
            group = first_period_groups[group_idx]

            # Obtener la inscripción a carrera del estudiante
            career_enrollment = career_enrollments.get(student.id)

            if career_enrollment:
                enrollment, created = SubjectEnrollment.objects.get_or_create(
                    student=student,
                    subject_group=group,
                    career_enrollment=career_enrollment,
                    defaults={
                        'status': 'enrolled',
                    }
                )

                if created:
                    subject_enrollments.append(enrollment)
                    # Actualizar el contador de inscripciones del grupo
                    group.current_enrollment = SubjectEnrollment.objects.filter(subject_group=group).count()
                    group.save()

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(subject_enrollments)} inscripciones a materias creadas'))

        # 12. Crear Configuración CSP (para todos los períodos)
        self.stdout.write('\nCreando Configuración CSP por defecto...')
        config_count = 0
        for period in periods:
            config, created = ScheduleConfiguration.objects.get_or_create(
                academic_period=period,
                defaults={
                    'algorithm': 'backtracking',
                    'max_execution_time_seconds': 300,
                    'optimization_priority': 'balanced',
                    'allow_teacher_gaps': True,
                    'max_daily_hours_per_teacher': 6,
                    'max_daily_hours_per_group': 8,
                    'min_break_between_classes': 0,
                    'weight_minimize_teacher_gaps': 5,
                    'weight_balanced_distribution': 7,
                    'weight_teacher_preferences': 8,
                    'weight_classroom_proximity': 4,
                    'weight_minimize_daily_changes': 6,
                }
            )
            if created:
                config_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {config_count} configuraciones CSP creadas'))

        # Resumen
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE DATOS CARGADOS'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'✓ Períodos Académicos: {AcademicPeriod.objects.count()}')
        self.stdout.write(f'✓ Carreras: {Career.objects.count()}')
        self.stdout.write(f'✓ Materias: {Subject.objects.count()}')
        self.stdout.write(f'✓ Aulas: {Classroom.objects.count()}')
        self.stdout.write(f'✓ Profesores: {Teacher.objects.count()}')
        self.stdout.write(f'✓ Estudiantes: {Student.objects.count()}')
        self.stdout.write(f'✓ Grupos de Materias: {SubjectGroup.objects.count()}')
        self.stdout.write(f'✓ Asignaciones de Profesores: {TeacherAssignment.objects.count()}')
        self.stdout.write(f'✓ Inscripciones a Carreras: {CareerEnrollment.objects.count()}')
        self.stdout.write(f'✓ Inscripciones a Materias: {SubjectEnrollment.objects.count()}')
        self.stdout.write(f'✓ Franjas Horarias: {TimeSlot.objects.count()}')
        self.stdout.write(f'✓ Configuraciones CSP: {ScheduleConfiguration.objects.count()}')
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('DATOS DE PRUEBA CARGADOS EXITOSAMENTE'))
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.WARNING('\nPuedes iniciar sesión con cualquier profesor:'))
        self.stdout.write('  Usuario: prof.garcia1 (o cualquier otro: prof.martinez2, prof.rodriguez3, etc.)')
        self.stdout.write('  Contraseña: password123')
        self.stdout.write(self.style.WARNING('\nO iniciar sesión como estudiante:'))
        self.stdout.write('  Usuario: est.acosta1 (o cualquier otro: est.benitez2, est.carrillo3, etc.)')
        self.stdout.write('  Contraseña: password123')
        self.stdout.write(self.style.WARNING('\nPara generar horarios, inicia sesión como administrador:'))
        self.stdout.write('  Usuario: admin')
        self.stdout.write('  Contraseña: admin123')
        self.stdout.write(self.style.SUCCESS('\n¡Ahora puedes usar el generador de horarios en el frontend!'))
        self.stdout.write('=' * 60)
