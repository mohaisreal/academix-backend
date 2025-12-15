"""
Django management command to reset and load custom test data
Usage: python manage.py reset_and_load_custom_data

Este comando crea:
- 1 usuario admin (usuario: admin, contraseña: admin)
- 20 estudiantes
- 10 profesores
- 3 carreras con 5 asignaturas cada una
- 2 períodos académicos (uno anterior con tareas y calificaciones, uno actual)
- Franjas horarias de 55 minutos
- NO genera horarios completos
- NO genera formularios
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import datetime, time, timedelta
from django.utils import timezone
from decimal import Decimal

from academic.models import AcademicPeriod, Career, Subject, Classroom, StudyPlan, StudyPlanSubject
from users.models import Teacher, Student, TeacherQualifiedCareer
from enrollment.models import SubjectGroup, CareerEnrollment, SubjectEnrollment
from schedules.models import TimeSlot, TeacherAssignment
from grades.models import Assignment, Submission, Grade, GradingCategory, FinalGrade
from notifications.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Resetea y carga datos personalizados: 3 carreras, 20 estudiantes, 10 profesores'

    def clean_database(self):
        """Elimina todos los datos"""
        self.stdout.write(self.style.WARNING('\n' + '=' * 70))
        self.stdout.write(self.style.WARNING('LIMPIANDO BASE DE DATOS COMPLETA'))
        self.stdout.write(self.style.WARNING('=' * 70))

        # Orden de eliminación basado en dependencias
        models_to_clean = [
            (Grade, 'Calificaciones'),
            (FinalGrade, 'Calificaciones Finales'),
            (Submission, 'Entregas de Tareas'),
            (Assignment, 'Tareas/Evaluaciones'),
            (GradingCategory, 'Categorías de Calificación'),
            (Notification, 'Notificaciones'),
            (SubjectEnrollment, 'Inscripciones a Materias'),
            (CareerEnrollment, 'Inscripciones a Carreras'),
            (SubjectGroup, 'Grupos de Materias'),
            (TimeSlot, 'Franjas Horarias'),
            (Student, 'Estudiantes'),
            (Teacher, 'Profesores'),
            (StudyPlanSubject, 'Materias del Plan de Estudios'),
            (StudyPlan, 'Planes de Estudio'),
            (Subject, 'Materias'),
            (Classroom, 'Aulas'),
            (Career, 'Carreras'),
            (AcademicPeriod, 'Períodos Académicos'),
        ]

        for model, name in models_to_clean:
            count = model.objects.all().delete()[0]
            if count > 0:
                self.stdout.write(f'   🗑️  {name}: {count} eliminados')

        # Eliminar TODOS los usuarios
        user_count = User.objects.all().count()
        if user_count > 0:
            User.objects.all().delete()
            self.stdout.write(f'   🗑️  Usuarios: {user_count} eliminados')

        self.stdout.write(self.style.SUCCESS('\n✓ Base de datos limpiada completamente\n'))

    def handle(self, *args, **options):
        # Limpiar la base de datos
        self.clean_database()

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('GENERANDO DATOS PERSONALIZADOS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # 1. Crear Usuario Admin
        self.stdout.write('\n[1/12] Creando Usuario Admin...')
        admin_user = User.objects.create_user(
            username='admin',
            email='admin@academix.edu',
            password='admin',
            first_name='Administrador',
            last_name='Sistema',
            role='admin'
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        self.stdout.write(self.style.SUCCESS(f'   ✓ Usuario admin creado (usuario: admin, contraseña: admin)'))

        # 2. Crear Períodos Académicos (uno anterior y uno actual)
        self.stdout.write('\n[2/12] Creando Períodos Académicos...')

        # Período anterior (con tareas y calificaciones)
        period_anterior = AcademicPeriod.objects.create(
            code='2024-2',
            name='2024 Segundo Semestre',
            start_date=datetime(2024, 8, 1).date(),
            end_date=datetime(2024, 12, 15).date(),
            enrollment_start=datetime(2024, 7, 15).date(),
            enrollment_end=datetime(2024, 7, 31).date(),
            is_active=False,
        )
        self.stdout.write(self.style.SUCCESS(f'   ✓ Período anterior: {period_anterior.name}'))

        # Período actual
        period_actual = AcademicPeriod.objects.create(
            code='2025-1',
            name='2025 Primer Semestre',
            start_date=datetime(2025, 2, 1).date(),
            end_date=datetime(2025, 6, 30).date(),
            enrollment_start=datetime(2025, 1, 15).date(),
            enrollment_end=datetime(2025, 1, 31).date(),
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(f'   ✓ Período actual: {period_actual.name}'))

        # 3. Crear 3 Carreras
        self.stdout.write('\n[3/12] Creando 3 Carreras...')
        careers_data = [
            {
                'code': 'ISC',
                'name': 'Ingeniería en Sistemas Computacionales',
                'description': 'Formación de profesionales en desarrollo de software y sistemas',
                'duration_years': 4,
                'total_credits': 240,
                'department': 'Sistemas'
            },
            {
                'code': 'IND',
                'name': 'Ingeniería Industrial',
                'description': 'Optimización de procesos y sistemas industriales',
                'duration_years': 4,
                'total_credits': 240,
                'department': 'Industrial'
            },
            {
                'code': 'IME',
                'name': 'Ingeniería Mecatrónica',
                'description': 'Integración de sistemas mecánicos, electrónicos y de control',
                'duration_years': 4,
                'total_credits': 240,
                'department': 'Mecatrónica'
            },
        ]

        careers = {}
        for career_data in careers_data:
            career = Career.objects.create(
                code=career_data['code'],
                name=career_data['name'],
                description=career_data['description'],
                duration_years=career_data['duration_years'],
                total_credits=career_data['total_credits'],
                is_active=True,
            )
            careers[career_data['code']] = {
                'career': career,
                'department': career_data['department']
            }
            self.stdout.write(self.style.SUCCESS(f'   ✓ {career.code} - {career.name}'))

        # 4. Crear 5 Asignaturas por carrera
        self.stdout.write('\n[4/12] Creando 5 Asignaturas por Carrera...')

        subjects_by_career = {
            'ISC': [
                {'code': 'ISC101', 'name': 'Fundamentos de Programación', 'credits': 6, 'year': 1, 'semester': 1},
                {'code': 'ISC102', 'name': 'Programación Orientada a Objetos', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'ISC201', 'name': 'Estructuras de Datos', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'ISC202', 'name': 'Bases de Datos', 'credits': 5, 'year': 2, 'semester': 2},
                {'code': 'ISC301', 'name': 'Desarrollo Web', 'credits': 5, 'year': 3, 'semester': 1},
            ],
            'IND': [
                {'code': 'IND101', 'name': 'Introducción a la Ingeniería Industrial', 'credits': 5, 'year': 1, 'semester': 1},
                {'code': 'IND102', 'name': 'Procesos de Manufactura', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'IND201', 'name': 'Investigación de Operaciones', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'IND202', 'name': 'Control de Calidad', 'credits': 5, 'year': 2, 'semester': 2},
                {'code': 'IND301', 'name': 'Administración de la Producción', 'credits': 5, 'year': 3, 'semester': 1},
            ],
            'IME': [
                {'code': 'IME101', 'name': 'Mecánica Básica', 'credits': 6, 'year': 1, 'semester': 1},
                {'code': 'IME102', 'name': 'Electrónica Analógica', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'IME201', 'name': 'Sistemas de Control', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'IME202', 'name': 'Robótica', 'credits': 6, 'year': 2, 'semester': 2},
                {'code': 'IME301', 'name': 'Automatización Industrial', 'credits': 5, 'year': 3, 'semester': 1},
            ],
        }

        all_subjects = {}
        subject_count = 0

        for career_code, subjects_list in subjects_by_career.items():
            for subj_data in subjects_list:
                subject = Subject.objects.create(
                    code=subj_data['code'],
                    name=subj_data['name'],
                    credits=subj_data['credits'],
                    course_year=subj_data['year'],
                    semester=subj_data['semester'],
                    type='mandatory',
                    is_active=True,
                )
                subject_count += 1
                all_subjects[subj_data['code']] = {'subject': subject, 'career': career_code}

        self.stdout.write(self.style.SUCCESS(f'   ✓ {subject_count} asignaturas creadas (5 por carrera)'))

        # 5. Crear Planes de Estudio
        self.stdout.write('\n[5/12] Creando Planes de Estudio...')
        study_plans = {}
        for career_code, career_info in careers.items():
            plan = StudyPlan.objects.create(
                career=career_info['career'],
                code=f'{career_code}-2025',
                name=f'Plan de Estudios {career_code} 2025',
                start_year=2025,
                is_active=True,
            )
            study_plans[career_code] = plan

            # Agregar asignaturas al plan de estudios
            for subj_code, subj_info in all_subjects.items():
                if subj_info['career'] == career_code:
                    StudyPlanSubject.objects.create(
                        study_plan=plan,
                        subject=subj_info['subject']
                    )

            self.stdout.write(self.style.SUCCESS(f'   ✓ Plan: {plan.name}'))

        # 6. Crear 10 Profesores
        self.stdout.write('\n[6/12] Creando 10 Profesores...')

        first_names = ['Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Laura', 'Pedro', 'Sofia', 'Miguel', 'Carmen']
        last_names = ['García', 'Martínez', 'Rodríguez', 'López', 'González', 'Fernández', 'Sánchez', 'Ramírez', 'Torres', 'Flores']
        departments = ['Sistemas', 'Industrial', 'Mecatrónica']

        teachers = []
        for i in range(10):
            first_name = first_names[i]
            last_name = last_names[i]
            username = f'prof.{last_name.lower()}'
            email = f'{first_name.lower()}.{last_name.lower()}@academix.edu'

            user = User.objects.create_user(
                username=username,
                email=email,
                password='password123',
                first_name=first_name,
                last_name=last_name,
                role='teacher',
            )

            teacher = Teacher.objects.create(
                user=user,
                employee_id=f'P{(i+1):04d}',
                department=departments[i % len(departments)],
                hire_date=timezone.now().date() - timedelta(days=365),
                status='active',
            )
            teachers.append(teacher)

        self.stdout.write(self.style.SUCCESS(f'   ✓ 10 profesores creados'))

        # 6b. Calificar profesores para impartir carreras completas
        self.stdout.write('\n[6b/13] Calificando Profesores para Carreras...')
        qualification_count = 0

        # Calificar cada profesor para todas las carreras (simplificado para pruebas)
        for teacher in teachers:
            for career_code, career_info in careers.items():
                TeacherQualifiedCareer.objects.create(
                    teacher=teacher,
                    career=career_info['career']
                )
                qualification_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {qualification_count} calificaciones de carrera creadas'))

        # 7. Crear 20 Estudiantes
        self.stdout.write('\n[7/13] Creando 20 Estudiantes...')

        student_first_names = [
            'Andrés', 'Beatriz', 'Carlos', 'Diana', 'Eduardo', 'Fernanda', 'Gabriel', 'Helena', 'Iván', 'Julia',
            'Kevin', 'Lorena', 'Mario', 'Natalia', 'Oscar', 'Paula', 'Ramón', 'Sandra', 'Tomás', 'Valeria'
        ]

        student_last_names = [
            'Acosta', 'Benítez', 'Carrillo', 'Durán', 'Espinosa', 'Franco', 'Guzmán', 'Herrera', 'Ibarra', 'Juárez',
            'Kuri', 'Lara', 'Mendoza', 'Núñez', 'Olivares', 'Padilla', 'Quintero', 'Rivas', 'Silva', 'Téllez'
        ]

        students = []
        for i in range(20):
            first_name = student_first_names[i]
            last_name = student_last_names[i]
            username = f'est.{last_name.lower()}'
            email = f'{first_name.lower()}.{last_name.lower()}@estudiantes.academix.edu'

            user = User.objects.create_user(
                username=username,
                email=email,
                password='password123',
                first_name=first_name,
                last_name=last_name,
                role='student',
            )

            student = Student.objects.create(
                user=user,
                student_id=f'E{(i+1):05d}',
                status='active',
            )
            students.append(student)

        self.stdout.write(self.style.SUCCESS(f'   ✓ 20 estudiantes creados'))

        # 8. Crear Grupos de Asignaturas para ambos períodos
        self.stdout.write('\n[8/13] Creando Grupos de Asignaturas...')

        subject_groups_anterior = []
        subject_groups_actual = []

        # Grupos para período anterior
        for subj_code, subj_info in all_subjects.items():
            subject = subj_info['subject']
            # Asignar un profesor rotativo
            teacher = teachers[len(subject_groups_anterior) % len(teachers)]

            group = SubjectGroup.objects.create(
                subject=subject,
                academic_period=period_anterior,
                code='G1',
                max_capacity=30,
                current_enrollment=0,
                is_active=True,
            )
            subject_groups_anterior.append({
                'group': group,
                'subject': subject,
                'career': subj_info['career'],
                'teacher': teacher
            })

        # Grupos para período actual
        for subj_code, subj_info in all_subjects.items():
            subject = subj_info['subject']
            teacher = teachers[len(subject_groups_actual) % len(teachers)]

            group = SubjectGroup.objects.create(
                subject=subject,
                academic_period=period_actual,
                code='G1',
                max_capacity=30,
                current_enrollment=0,
                is_active=True,
            )
            subject_groups_actual.append({
                'group': group,
                'subject': subject,
                'career': subj_info['career'],
                'teacher': teacher
            })

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(subject_groups_anterior)} grupos para período anterior'))
        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(subject_groups_actual)} grupos para período actual'))

        # 9. Asignar Profesores a Grupos (TeacherAssignment)
        self.stdout.write('\n[9/13] Asignando Profesores a Grupos...')
        assignment_count = 0

        # Asignar profesores al período anterior
        for group_info in subject_groups_anterior:
            group = group_info['group']
            teacher = group_info['teacher']

            TeacherAssignment.objects.create(
                teacher=teacher,
                subject_group=group,
                weekly_hours=group.subject.credits,
                is_main_teacher=True,
                status='active',
            )
            assignment_count += 1

        # Asignar profesores al período actual
        for group_info in subject_groups_actual:
            group = group_info['group']
            teacher = group_info['teacher']

            TeacherAssignment.objects.create(
                teacher=teacher,
                subject_group=group,
                weekly_hours=group.subject.credits,
                is_main_teacher=True,
                status='active',
            )
            assignment_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {assignment_count} asignaciones de profesores creadas'))

        # 10. Matricular Estudiantes en Carreras y Asignaturas
        self.stdout.write('\n[10/13] Matriculando Estudiantes...')

        career_enrollments = []
        students_per_career = 20 // 3  # Distribuir estudiantes entre las 3 carreras

        career_codes = list(careers.keys())
        for i, student in enumerate(students):
            # Asignar carrera de forma rotativa
            career_code = career_codes[i % len(career_codes)]
            career_info = careers[career_code]
            study_plan = study_plans[career_code]

            # Matricular en carrera
            career_enrollment = CareerEnrollment.objects.create(
                student=student,
                career=career_info['career'],
                study_plan=study_plan,
                status='active',
            )
            career_enrollments.append(career_enrollment)

            # Matricular en asignaturas del período anterior
            for group_info in subject_groups_anterior:
                if group_info['career'] == career_code:
                    SubjectEnrollment.objects.create(
                        student=student,
                        subject_group=group_info['group'],
                        career_enrollment=career_enrollment,
                        status='completed',  # Ya completó el período anterior
                    )
                    group_info['group'].current_enrollment += 1
                    group_info['group'].save()

            # Matricular en asignaturas del período actual
            for group_info in subject_groups_actual:
                if group_info['career'] == career_code:
                    SubjectEnrollment.objects.create(
                        student=student,
                        subject_group=group_info['group'],
                        career_enrollment=career_enrollment,
                        status='enrolled',
                    )
                    group_info['group'].current_enrollment += 1
                    group_info['group'].save()

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(career_enrollments)} estudiantes matriculados en carreras'))

        # 11. Crear Franjas Horarias de 55 minutos
        self.stdout.write('\n[11/13] Creando Franjas Horarias (55 minutos)...')

        days = [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
        ]

        # Crear franjas de 55 minutos de 7:00 AM a 9:00 PM
        timeslot_count = 0

        for period in [period_anterior, period_actual]:
            for day_num, day_name in days:
                current_time = datetime.combine(datetime.today(), time(7, 0))
                end_of_day = datetime.combine(datetime.today(), time(21, 0))

                while current_time < end_of_day:
                    start_time_obj = current_time.time()
                    end_time_obj = (current_time + timedelta(minutes=55)).time()
                    slot_code = f"{day_name[:3].upper()}-{start_time_obj.strftime('%H:%M')}"

                    TimeSlot.objects.create(
                        academic_period=period,
                        day_of_week=day_num,
                        start_time=start_time_obj,
                        end_time=end_time_obj,
                        slot_code=slot_code,
                        is_active=True,
                    )
                    timeslot_count += 1

                    # Avanzar 55 minutos para la próxima franja
                    current_time += timedelta(minutes=55)

        self.stdout.write(self.style.SUCCESS(f'   ✓ {timeslot_count} franjas horarias de 55 minutos creadas'))

        # 12. Crear Categorías de Calificación, Tareas y Calificaciones para el Período Anterior
        self.stdout.write('\n[12/13] Creando Tareas y Calificaciones para Período Anterior...')

        assignment_count = 0
        grade_count = 0

        for group_info in subject_groups_anterior:
            group = group_info['group']

            # Crear categorías de calificación para este grupo
            cat_examen = GradingCategory.objects.create(
                subject_group=group,
                name='Exámenes',
                weight=Decimal('40.00'),
                order=1
            )

            cat_tareas = GradingCategory.objects.create(
                subject_group=group,
                name='Tareas',
                weight=Decimal('30.00'),
                order=2
            )

            cat_participacion = GradingCategory.objects.create(
                subject_group=group,
                name='Participación',
                weight=Decimal('30.00'),
                order=3
            )

            # Crear 2 exámenes
            for i in range(1, 3):
                assignment = Assignment.objects.create(
                    subject_group=group,
                    category=cat_examen,
                    title=f'Examen {i}',
                    description=f'Examen {i} del período anterior',
                    assignment_type='exam',
                    max_score=Decimal('100.00'),
                    start_date=period_anterior.start_date + timedelta(days=30*i),
                    due_date=period_anterior.start_date + timedelta(days=30*i+7),
                    published_at=timezone.now() - timedelta(days=60),
                )
                assignment_count += 1

                # Crear calificaciones para estudiantes matriculados
                enrollments = SubjectEnrollment.objects.filter(subject_group=group, status='completed')
                for enrollment in enrollments:
                    # Generar una calificación aleatoria entre 60 y 100
                    import random
                    score = Decimal(str(random.randint(60, 100)))

                    Grade.objects.create(
                        assignment=assignment,
                        student=enrollment.student,
                        score=score,
                        feedback=f'Buen trabajo en el examen {i}',
                        graded_at=timezone.now() - timedelta(days=50),
                    )
                    grade_count += 1

            # Crear 3 tareas
            for i in range(1, 4):
                assignment = Assignment.objects.create(
                    subject_group=group,
                    category=cat_tareas,
                    title=f'Tarea {i}',
                    description=f'Tarea {i} del período anterior',
                    assignment_type='task',
                    max_score=Decimal('100.00'),
                    start_date=period_anterior.start_date + timedelta(days=15*i),
                    due_date=period_anterior.start_date + timedelta(days=15*i+7),
                    published_at=timezone.now() - timedelta(days=60),
                )
                assignment_count += 1

                # Crear calificaciones
                enrollments = SubjectEnrollment.objects.filter(subject_group=group, status='completed')
                for enrollment in enrollments:
                    import random
                    score = Decimal(str(random.randint(70, 100)))

                    Grade.objects.create(
                        assignment=assignment,
                        student=enrollment.student,
                        score=score,
                        feedback=f'Buena entrega de la tarea {i}',
                        graded_at=timezone.now() - timedelta(days=45),
                    )
                    grade_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {assignment_count} tareas/exámenes creados'))
        self.stdout.write(self.style.SUCCESS(f'   ✓ {grade_count} calificaciones creadas'))

        # 13. Crear Aulas (opcional, para completar)
        self.stdout.write('\n[13/13] Creando Aulas...')
        classroom_count = 0

        for i in range(1, 11):
            Classroom.objects.create(
                code=f'A{i:03d}',
                name=f'Aula {i}',
                building='Edificio Principal',
                capacity=35,
                is_active=True,
            )
            classroom_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {classroom_count} aulas creadas'))

        # Resumen Final
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE DATOS GENERADOS'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'✓ Usuarios Admin: 1')
        self.stdout.write(f'✓ Carreras: {Career.objects.count()}')
        self.stdout.write(f'✓ Asignaturas: {Subject.objects.count()}')
        self.stdout.write(f'✓ Profesores: {Teacher.objects.count()}')
        self.stdout.write(f'✓ Estudiantes: {Student.objects.count()}')
        self.stdout.write(f'✓ Períodos Académicos: {AcademicPeriod.objects.count()}')
        self.stdout.write(f'✓ Grupos de Asignaturas: {SubjectGroup.objects.count()}')
        self.stdout.write(f'✓ Asignaciones de Profesores: {TeacherAssignment.objects.count()}')
        self.stdout.write(f'✓ Matrículas a Carreras: {CareerEnrollment.objects.count()}')
        self.stdout.write(f'✓ Matrículas a Asignaturas: {SubjectEnrollment.objects.count()}')
        self.stdout.write(f'✓ Franjas Horarias: {TimeSlot.objects.count()} (55 minutos cada una)')
        self.stdout.write(f'✓ Tareas/Exámenes: {Assignment.objects.count()}')
        self.stdout.write(f'✓ Calificaciones: {Grade.objects.count()}')
        self.stdout.write(f'✓ Aulas: {Classroom.objects.count()}')

        # Distribución por carrera
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('DISTRIBUCIÓN POR CARRERA'))
        self.stdout.write('=' * 70)
        for career in Career.objects.all():
            student_count = CareerEnrollment.objects.filter(career=career, status='active').count()
            self.stdout.write(f'  {career.code}: {student_count} estudiantes')

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('DATOS GENERADOS EXITOSAMENTE'))
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.WARNING('\nCredenciales de acceso:'))
        self.stdout.write('  Admin: admin / admin')
        self.stdout.write('  Profesores: prof.garcia / password123 (o cualquier profesor)')
        self.stdout.write('  Estudiantes: est.acosta / password123 (o cualquier estudiante)')
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('NOTAS IMPORTANTES:'))
        self.stdout.write('  - Período anterior (2024-2) contiene tareas y calificaciones de prueba')
        self.stdout.write('  - Período actual (2025-1) está activo para nuevas inscripciones')
        self.stdout.write('  - NO se generaron horarios completos (solo franjas horarias)')
        self.stdout.write('  - NO se generaron formularios')
        self.stdout.write('=' * 70 + '\n')
