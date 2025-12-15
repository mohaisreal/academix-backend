"""
Django management command to load complete test data
Usage: python manage.py load_complete_test_data

Este comando crea:
- 5 carreras
- 20 alumnos por carrera (100 total)
- Asignaturas para cada carrera
- Profesores asignados a cada grupo de asignatura
- Sin profesores huérfanos, sin clases sin asignaturas, sin alumnos sin carrera
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import datetime, time, timedelta
from django.utils import timezone

from academic.models import AcademicPeriod, Career, Subject, Classroom, StudyPlan, StudyPlanSubject
from users.models import Teacher, Student
from enrollment.models import SubjectGroup, CareerEnrollment, SubjectEnrollment
from schedules.models import TimeSlot, TeacherAssignment
from grades.models import Evaluation, Grade, FinalGrade
from notifications.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga datos de prueba completos: 5 carreras, 20 alumnos por carrera, profesores para cada clase'

    def clean_database(self):
        """Elimina todos los datos excepto el usuario admin"""
        self.stdout.write(self.style.WARNING('\n' + '=' * 70))
        self.stdout.write(self.style.WARNING('LIMPIANDO BASE DE DATOS (preservando admin)'))
        self.stdout.write(self.style.WARNING('=' * 70))

        # Orden de eliminación basado en dependencias
        models_to_clean = [
            (Grade, 'Calificaciones'),
            (FinalGrade, 'Calificaciones Finales'),
            (Evaluation, 'Evaluaciones'),
            (Notification, 'Notificaciones'),
            (TeacherAssignment, 'Asignaciones de Profesores'),
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

        # Eliminar usuarios excepto admin
        admin_users = User.objects.filter(role='admin')
        non_admin_users = User.objects.exclude(role='admin')
        count = non_admin_users.count()
        if count > 0:
            non_admin_users.delete()
            self.stdout.write(f'   🗑️  Usuarios (no admin): {count} eliminados')

        self.stdout.write(self.style.SUCCESS(f'   ✓ Usuarios admin preservados: {admin_users.count()}'))
        self.stdout.write(self.style.SUCCESS('\n✓ Base de datos limpiada exitosamente\n'))

    def handle(self, *args, **options):
        # Siempre limpiar la base de datos
        self.clean_database()

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('GENERANDO DATOS DE PRUEBA COMPLETOS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # 1. Crear Período Académico Activo
        self.stdout.write('\n[1/10] Creando Período Académico...')
        period, created = AcademicPeriod.objects.get_or_create(
            code='2025-1',
            defaults={
                'name': '2025 Primer Semestre',
                'start_date': datetime(2025, 2, 1).date(),
                'end_date': datetime(2025, 6, 30).date(),
                'enrollment_start': datetime(2025, 1, 15).date(),
                'enrollment_end': datetime(2025, 1, 31).date(),
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'   ✓ Período creado: {period.name}'))

        # 2. Crear 5 Carreras
        self.stdout.write('\n[2/10] Creando 5 Carreras...')
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
            {
                'code': 'IEL',
                'name': 'Ingeniería Electrónica',
                'description': 'Diseño y desarrollo de sistemas electrónicos',
                'duration_years': 4,
                'total_credits': 240,
                'department': 'Electrónica'
            },
            {
                'code': 'ARQ',
                'name': 'Arquitectura',
                'description': 'Diseño y planificación de espacios arquitectónicos',
                'duration_years': 5,
                'total_credits': 300,
                'department': 'Arquitectura'
            },
        ]

        careers = {}
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
            careers[career_data['code']] = {
                'career': career,
                'department': career_data['department']
            }
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ {career.code} - {career.name}'))

        # 3. Crear Asignaturas para cada carrera
        self.stdout.write('\n[3/10] Creando Asignaturas por Carrera...')

        subjects_by_career = {
            'ISC': [
                {'code': 'ISC101', 'name': 'Fundamentos de Programación', 'credits': 6, 'year': 1, 'semester': 1},
                {'code': 'ISC102', 'name': 'Programación Orientada a Objetos', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'ISC201', 'name': 'Estructuras de Datos', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'ISC202', 'name': 'Bases de Datos', 'credits': 5, 'year': 2, 'semester': 2},
                {'code': 'ISC301', 'name': 'Desarrollo Web', 'credits': 5, 'year': 3, 'semester': 1},
                {'code': 'ISC302', 'name': 'Inteligencia Artificial', 'credits': 6, 'year': 3, 'semester': 2},
            ],
            'IND': [
                {'code': 'IND101', 'name': 'Introducción a la Ingeniería Industrial', 'credits': 5, 'year': 1, 'semester': 1},
                {'code': 'IND102', 'name': 'Procesos de Manufactura', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'IND201', 'name': 'Investigación de Operaciones', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'IND202', 'name': 'Control de Calidad', 'credits': 5, 'year': 2, 'semester': 2},
                {'code': 'IND301', 'name': 'Administración de la Producción', 'credits': 5, 'year': 3, 'semester': 1},
                {'code': 'IND302', 'name': 'Logística Industrial', 'credits': 5, 'year': 3, 'semester': 2},
            ],
            'IME': [
                {'code': 'IME101', 'name': 'Mecánica Básica', 'credits': 6, 'year': 1, 'semester': 1},
                {'code': 'IME102', 'name': 'Electrónica Analógica', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'IME201', 'name': 'Sistemas de Control', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'IME202', 'name': 'Robótica', 'credits': 6, 'year': 2, 'semester': 2},
                {'code': 'IME301', 'name': 'Automatización Industrial', 'credits': 5, 'year': 3, 'semester': 1},
                {'code': 'IME302', 'name': 'Sistemas Embebidos', 'credits': 5, 'year': 3, 'semester': 2},
            ],
            'IEL': [
                {'code': 'IEL101', 'name': 'Circuitos Eléctricos I', 'credits': 6, 'year': 1, 'semester': 1},
                {'code': 'IEL102', 'name': 'Circuitos Eléctricos II', 'credits': 6, 'year': 1, 'semester': 2},
                {'code': 'IEL201', 'name': 'Electrónica Digital', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'IEL202', 'name': 'Microcontroladores', 'credits': 6, 'year': 2, 'semester': 2},
                {'code': 'IEL301', 'name': 'Telecomunicaciones', 'credits': 5, 'year': 3, 'semester': 1},
                {'code': 'IEL302', 'name': 'Procesamiento de Señales', 'credits': 5, 'year': 3, 'semester': 2},
            ],
            'ARQ': [
                {'code': 'ARQ101', 'name': 'Diseño Arquitectónico I', 'credits': 8, 'year': 1, 'semester': 1},
                {'code': 'ARQ102', 'name': 'Diseño Arquitectónico II', 'credits': 8, 'year': 1, 'semester': 2},
                {'code': 'ARQ201', 'name': 'Estructuras', 'credits': 6, 'year': 2, 'semester': 1},
                {'code': 'ARQ202', 'name': 'Instalaciones', 'credits': 6, 'year': 2, 'semester': 2},
                {'code': 'ARQ301', 'name': 'Urbanismo', 'credits': 6, 'year': 3, 'semester': 1},
                {'code': 'ARQ302', 'name': 'Teoría de la Arquitectura', 'credits': 5, 'year': 3, 'semester': 2},
            ],
        }

        # Agregar materias comunes para todas las carreras
        common_subjects = [
            {'code': 'MAT101', 'name': 'Cálculo Diferencial', 'credits': 6, 'year': 1, 'semester': 1},
            {'code': 'MAT102', 'name': 'Cálculo Integral', 'credits': 6, 'year': 1, 'semester': 2},
            {'code': 'FIS101', 'name': 'Física I', 'credits': 5, 'year': 1, 'semester': 1},
            {'code': 'ING101', 'name': 'Inglés I', 'credits': 3, 'year': 1, 'semester': 1},
        ]

        all_subjects = {}
        subject_count = 0

        for career_code, subjects_list in subjects_by_career.items():
            for subj_data in subjects_list:
                subject, created = Subject.objects.get_or_create(
                    code=subj_data['code'],
                    defaults={
                        'name': subj_data['name'],
                        'credits': subj_data['credits'],
                        'course_year': subj_data['year'],
                        'semester': subj_data['semester'],
                        'type': 'mandatory',
                        'is_active': True,
                    }
                )
                if created:
                    subject_count += 1
                all_subjects[subj_data['code']] = {'subject': subject, 'career': career_code}

        # Crear materias comunes
        for subj_data in common_subjects:
            subject, created = Subject.objects.get_or_create(
                code=subj_data['code'],
                defaults={
                    'name': subj_data['name'],
                    'credits': subj_data['credits'],
                    'course_year': subj_data['year'],
                    'semester': subj_data['semester'],
                    'type': 'core',
                    'is_active': True,
                }
            )
            if created:
                subject_count += 1
            all_subjects[subj_data['code']] = {'subject': subject, 'career': 'COMMON'}

        self.stdout.write(self.style.SUCCESS(f'   ✓ {subject_count} asignaturas creadas'))

        # 4. Crear Planes de Estudio
        self.stdout.write('\n[4/10] Creando Planes de Estudio...')
        study_plans = {}
        for career_code, career_info in careers.items():
            plan, created = StudyPlan.objects.get_or_create(
                career=career_info['career'],
                code=f'{career_code}-2025',
                defaults={
                    'name': f'Plan de Estudios {career_code} 2025',
                    'start_year': 2025,
                    'is_active': True,
                }
            )
            study_plans[career_code] = plan

            # Agregar asignaturas al plan de estudios
            for subj_code, subj_info in all_subjects.items():
                if subj_info['career'] == career_code or subj_info['career'] == 'COMMON':
                    StudyPlanSubject.objects.get_or_create(
                        study_plan=plan,
                        subject=subj_info['subject']
                    )

            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Plan: {plan.name}'))

        # 5. Crear Grupos de Asignaturas (1 grupo por asignatura)
        self.stdout.write('\n[5/10] Creando Grupos de Asignaturas...')
        subject_groups = []
        group_count = 0

        for subj_code, subj_info in all_subjects.items():
            subject = subj_info['subject']
            group, created = SubjectGroup.objects.get_or_create(
                subject=subject,
                academic_period=period,
                code='G1',
                defaults={
                    'max_capacity': 30,
                    'current_enrollment': 0,
                    'is_active': True,
                }
            )
            subject_groups.append({
                'group': group,
                'subject': subject,
                'career': subj_info['career']
            })
            if created:
                group_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {group_count} grupos creados'))

        # 6. Crear Profesores (uno por grupo de asignatura)
        self.stdout.write('\n[6/10] Creando Profesores...')

        first_names = ['Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Laura', 'Pedro', 'Sofia', 'Miguel', 'Carmen',
                      'José', 'Isabel', 'Antonio', 'Elena', 'Francisco', 'Patricia', 'Manuel', 'Rosa', 'David', 'Lucía',
                      'Javier', 'Marta', 'Sergio', 'Cristina', 'Roberto', 'Silvia', 'Fernando', 'Beatriz', 'Alberto', 'Pilar',
                      'Raúl', 'Teresa', 'Alejandro', 'Mónica', 'Pablo', 'Adriana', 'Jorge', 'Nuria', 'Daniel', 'Victoria']

        last_names = ['García', 'Martínez', 'Rodríguez', 'López', 'González', 'Fernández', 'Sánchez', 'Ramírez', 'Torres', 'Flores',
                     'Díaz', 'Morales', 'Jiménez', 'Álvarez', 'Romero', 'Ruiz', 'Hernández', 'Navarro', 'Domínguez', 'Gil',
                     'Castro', 'Ortiz', 'Rubio', 'Molina', 'Delgado', 'Moreno', 'Suárez', 'Ortega', 'Peña', 'Vega',
                     'Medina', 'Campos', 'Guerrero', 'Cortés', 'Vargas', 'Reyes', 'Cruz', 'Santos', 'Núñez', 'Mendoza']

        teachers = []
        teacher_count = 0

        for i, group_info in enumerate(subject_groups):
            career_code = group_info['career']
            department = careers.get(career_code, {}).get('department', 'General') if career_code != 'COMMON' else 'Ciencias Básicas'

            first_name = first_names[i % len(first_names)]
            last_name = last_names[i % len(last_names)]

            username = f'prof.{last_name.lower()}{i+1}'
            email = f'{first_name.lower()}.{last_name.lower()}{i+1}@academix.edu'

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'role': 'teacher',
                }
            )
            if user_created:
                user.set_password('password123')
                user.save()

            teacher, created = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': f'P{(i+1):04d}',
                    'department': department,
                    'hire_date': timezone.now().date() - timedelta(days=365),
                    'status': 'active',
                }
            )
            teachers.append(teacher)
            if created:
                teacher_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {teacher_count} profesores creados'))

        # 7. Asignar Profesores a Grupos (1 profesor por grupo)
        self.stdout.write('\n[7/10] Asignando Profesores a Grupos...')
        assignment_count = 0

        for i, group_info in enumerate(subject_groups):
            group = group_info['group']
            teacher = teachers[i]

            assignment, created = TeacherAssignment.objects.get_or_create(
                teacher=teacher,
                subject_group=group,
                defaults={
                    'weekly_hours': group.subject.credits,
                    'is_main_teacher': True,
                    'status': 'active',
                }
            )
            if created:
                assignment_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {assignment_count} asignaciones creadas'))

        # 8. Crear 20 Estudiantes por Carrera (100 total)
        self.stdout.write('\n[8/10] Creando Estudiantes (20 por carrera)...')

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

        students_by_career = {code: [] for code in careers.keys()}
        student_count = 0

        student_idx = 0
        for career_code in careers.keys():
            for i in range(20):  # 20 estudiantes por carrera
                first_name = student_first_names[student_idx % len(student_first_names)]
                last_name = student_last_names[student_idx % len(student_last_names)]

                username = f'est.{last_name.lower()}{student_idx+1}'
                email = f'{first_name.lower()}.{last_name.lower()}{student_idx+1}@estudiantes.academix.edu'

                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': email,
                        'role': 'student',
                    }
                )
                if user_created:
                    user.set_password('password123')
                    user.save()

                student, created = Student.objects.get_or_create(
                    user=user,
                    defaults={
                        'student_id': f'E{(student_idx+1):05d}',
                        'status': 'active',
                    }
                )
                students_by_career[career_code].append(student)
                if created:
                    student_count += 1

                student_idx += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {student_count} estudiantes creados (20 por carrera)'))

        # 9. Matricular Estudiantes en Carreras
        self.stdout.write('\n[9/10] Matriculando Estudiantes en Carreras...')
        career_enrollments = {}
        enrollment_count = 0

        for career_code, students_list in students_by_career.items():
            career_info = careers[career_code]
            study_plan = study_plans[career_code]

            for student in students_list:
                enrollment, created = CareerEnrollment.objects.get_or_create(
                    student=student,
                    career=career_info['career'],
                    study_plan=study_plan,
                    defaults={
                        'status': 'active',
                    }
                )
                career_enrollments[student.id] = enrollment
                if created:
                    enrollment_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {enrollment_count} matrículas a carreras creadas'))

        # 10. Matricular Estudiantes en Asignaturas de su Carrera
        self.stdout.write('\n[10/10] Matriculando Estudiantes en Asignaturas...')
        subject_enrollment_count = 0

        for career_code, students_list in students_by_career.items():
            # Obtener grupos de asignaturas de esta carrera
            career_groups = [
                g for g in subject_groups
                if g['career'] == career_code or g['career'] == 'COMMON'
            ]

            # Matricular cada estudiante en los grupos de su carrera
            for student in students_list:
                career_enrollment = career_enrollments[student.id]

                for group_info in career_groups:
                    group = group_info['group']

                    enrollment, created = SubjectEnrollment.objects.get_or_create(
                        student=student,
                        subject_group=group,
                        career_enrollment=career_enrollment,
                        defaults={
                            'status': 'enrolled',
                        }
                    )

                    if created:
                        subject_enrollment_count += 1
                        # Actualizar contador de inscripciones
                        group.current_enrollment += 1
                        group.save()

        self.stdout.write(self.style.SUCCESS(f'   ✓ {subject_enrollment_count} matrículas a asignaturas creadas'))

        # 11. Crear Aulas
        self.stdout.write('\n[Adicional] Creando Aulas...')
        classrooms_data = []

        for i in range(1, 21):
            classrooms_data.append({
                'code': f'A{i:03d}',
                'name': f'Aula {i}',
                'building': 'Edificio Principal',
                'capacity': 35
            })

        classroom_count = 0
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
            if created:
                classroom_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {classroom_count} aulas creadas'))

        # 12. Crear Franjas Horarias
        self.stdout.write('\n[Adicional] Creando Franjas Horarias...')

        days = [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
        ]

        # Horario de 7:00 AM a 9:00 PM (14 horas por día = 70 franjas por período)
        start_hour = 7
        end_hour = 21

        timeslot_count = 0
        for day_num, day_name in days:
            for hour in range(start_hour, end_hour):
                start_time_obj = time(hour, 0)
                end_time_obj = time(hour + 1, 0)
                slot_code = f"{day_name[:3].upper()}-{hour:02d}:00"

                timeslot, created = TimeSlot.objects.get_or_create(
                    academic_period=period,
                    day_of_week=day_num,
                    start_time=start_time_obj,
                    end_time=end_time_obj,
                    defaults={
                        'slot_code': slot_code,
                        'is_active': True,
                    }
                )
                if created:
                    timeslot_count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {timeslot_count} franjas horarias creadas (5 días × {end_hour - start_hour} horas)'))

        # Resumen Final
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE DATOS GENERADOS'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'✓ Carreras: {Career.objects.count()}')
        self.stdout.write(f'✓ Asignaturas: {Subject.objects.count()}')
        self.stdout.write(f'✓ Grupos de Asignaturas: {SubjectGroup.objects.count()}')
        self.stdout.write(f'✓ Profesores: {Teacher.objects.count()}')
        self.stdout.write(f'✓ Estudiantes: {Student.objects.count()}')
        self.stdout.write(f'✓ Asignaciones Profesor-Grupo: {TeacherAssignment.objects.count()}')
        self.stdout.write(f'✓ Matrículas a Carreras: {CareerEnrollment.objects.count()}')
        self.stdout.write(f'✓ Matrículas a Asignaturas: {SubjectEnrollment.objects.count()}')
        self.stdout.write(f'✓ Aulas: {Classroom.objects.count()}')
        self.stdout.write(f'✓ Franjas Horarias: {TimeSlot.objects.filter(academic_period=period).count()}')

        # Verificaciones
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('VERIFICACIONES'))
        self.stdout.write('=' * 70)

        # Verificar que no hay profesores sin clases
        teachers_without_classes = Teacher.objects.filter(assignments__isnull=True).count()
        if teachers_without_classes == 0:
            self.stdout.write(self.style.SUCCESS('✓ Todos los profesores tienen clases asignadas'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ {teachers_without_classes} profesores sin clases'))

        # Verificar que no hay alumnos sin carrera
        students_without_career = Student.objects.filter(career_enrollments__isnull=True).count()
        if students_without_career == 0:
            self.stdout.write(self.style.SUCCESS('✓ Todos los estudiantes tienen carrera asignada'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ {students_without_career} estudiantes sin carrera'))

        # Verificar que no hay grupos sin profesor
        groups_without_teacher = SubjectGroup.objects.filter(teacher_assignments__isnull=True).count()
        if groups_without_teacher == 0:
            self.stdout.write(self.style.SUCCESS('✓ Todos los grupos tienen profesor asignado'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ {groups_without_teacher} grupos sin profesor'))

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
        self.stdout.write('  Admin: admin / admin123')
        self.stdout.write('  Profesores: prof.garcia1 / password123 (o cualquier profesor)')
        self.stdout.write('  Estudiantes: est.acosta1 / password123 (o cualquier estudiante)')
        self.stdout.write('=' * 70 + '\n')
