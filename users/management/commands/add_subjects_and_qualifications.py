from django.core.management.base import BaseCommand
from django.utils import timezone
from academic.models import Career, Subject, StudyPlan, StudyPlanSubject
from users.models import Teacher, TeacherQualifiedSubject
from datetime import date


class Command(BaseCommand):
    help = 'Añade al menos 5 asignaturas por carrera y asigna profesores cualificados'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando proceso de añadir asignaturas y cualificaciones...'))

        # Obtener carreras
        try:
            isc = Career.objects.get(code='ISC')
            ind = Career.objects.get(code='IND')
            ime = Career.objects.get(code='IME')
        except Career.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Error: No se encontró una carrera: {e}'))
            return

        # Definir asignaturas por carrera
        subjects_data = {
            'ISC': [
                # Año 1
                {'code': 'ISC103', 'name': 'Matemáticas Discretas', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC104', 'name': 'Álgebra Lineal', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC105', 'name': 'Cálculo Diferencial', 'credits': 5, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC106', 'name': 'Fundamentos de Física', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                {'code': 'ISC107', 'name': 'Arquitectura de Computadoras', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                # Año 2
                {'code': 'ISC203', 'name': 'Algoritmos Avanzados', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC204', 'name': 'Sistemas Operativos', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC205', 'name': 'Redes de Computadoras', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'ISC206', 'name': 'Desarrollo Web', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'ISC207', 'name': 'Ingeniería de Software', 'credits': 5, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                # Año 3
                {'code': 'ISC301', 'name': 'Inteligencia Artificial', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC302', 'name': 'Compiladores', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC303', 'name': 'Seguridad Informática', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'mandatory'},
                {'code': 'ISC304', 'name': 'Computación en la Nube', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'elective'},
                {'code': 'ISC305', 'name': 'Machine Learning', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'elective'},
            ],
            'IND': [
                # Año 1
                {'code': 'IND103', 'name': 'Estadística Descriptiva', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND104', 'name': 'Dibujo Industrial', 'credits': 3, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND105', 'name': 'Química Industrial', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND106', 'name': 'Termodinámica', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IND107', 'name': 'Metrología', 'credits': 3, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                # Año 2
                {'code': 'IND202', 'name': 'Control de Calidad', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND203', 'name': 'Ingeniería de Métodos', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND204', 'name': 'Logística Industrial', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IND205', 'name': 'Gestión de Proyectos', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IND206', 'name': 'Diseño de Plantas', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                # Año 3
                {'code': 'IND301', 'name': 'Administración de la Producción', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND302', 'name': 'Simulación de Sistemas', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND303', 'name': 'Ergonomía Industrial', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IND304', 'name': 'Manufactura Esbelta', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'elective'},
                {'code': 'IND305', 'name': 'Gestión Ambiental', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'elective'},
            ],
            'IME': [
                # Año 1
                {'code': 'IME103', 'name': 'Matemáticas para Ingeniería', 'credits': 5, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME104', 'name': 'Física Mecánica', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME105', 'name': 'Programación para Ingenieros', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME106', 'name': 'Electrónica Digital', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IME107', 'name': 'Estática y Dinámica', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                # Año 2
                {'code': 'IME202', 'name': 'Microcontroladores', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME203', 'name': 'Neumática e Hidráulica', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME204', 'name': 'Automatización Industrial', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IME205', 'name': 'Robótica', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IME206', 'name': 'Máquinas Eléctricas', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                # Año 3
                {'code': 'IME301', 'name': 'Sistemas Embebidos', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME302', 'name': 'Instrumentación Industrial', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME303', 'name': 'Visión Artificial', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IME304', 'name': 'Internet de las Cosas', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'elective'},
                {'code': 'IME305', 'name': 'Sistemas Mecatrónicos Avanzados', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'elective'},
            ],
        }

        # Crear asignaturas
        created_subjects = {}
        for career_code, subjects in subjects_data.items():
            career = Career.objects.get(code=career_code)
            created_subjects[career_code] = []

            self.stdout.write(f'\nCreando asignaturas para {career.name}...')

            for subject_data in subjects:
                subject, created = Subject.objects.get_or_create(
                    code=subject_data['code'],
                    defaults={
                        'name': subject_data['name'],
                        'credits': subject_data['credits'],
                        'course_year': subject_data['year'],
                        'semester': subject_data['semester'],
                        'type': subject_data['type'],
                        'is_active': True,
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Creada: {subject.code} - {subject.name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Ya existe: {subject.code} - {subject.name}'))

                created_subjects[career_code].append(subject)

                # Añadir al plan de estudios
                study_plan = career.study_plans.filter(is_active=True).first()
                if not study_plan:
                    # Crear plan de estudios si no existe
                    study_plan = StudyPlan.objects.create(
                        career=career,
                        name=f'Plan de Estudios {career.name} 2024',
                        code=f'{career_code}-2024',
                        start_year=2024,
                        is_active=True
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Creado plan de estudios: {study_plan.code}'))

                # Añadir asignatura al plan
                StudyPlanSubject.objects.get_or_create(
                    study_plan=study_plan,
                    subject=subject
                )

        # Obtener todos los profesores
        teachers = list(Teacher.objects.all())

        if not teachers:
            self.stdout.write(self.style.ERROR('No hay profesores en la base de datos'))
            return

        self.stdout.write(f'\n\nAsignando profesores a asignaturas...')
        self.stdout.write(f'Total de profesores disponibles: {len(teachers)}')

        # Distribución de profesores por carrera
        # Asignaremos 3-4 profesores por carrera con especialización
        assignments = {
            'ISC': {
                'teachers': teachers[0:4],  # Primeros 4 profesores
                'specializations': {
                    teachers[0].id: 'Programación y Algoritmos',
                    teachers[1].id: 'Bases de Datos y Redes',
                    teachers[2].id: 'Inteligencia Artificial',
                    teachers[3].id: 'Matemáticas y Física',
                }
            },
            'IND': {
                'teachers': teachers[4:8],  # Siguientes 4 profesores
                'specializations': {
                    teachers[4].id: 'Procesos y Manufactura',
                    teachers[5].id: 'Calidad y Estadística',
                    teachers[6].id: 'Logística y Proyectos',
                    teachers[7].id: 'Química y Termodinámica',
                }
            },
            'IME': {
                'teachers': teachers[8:10],  # Últimos 2 profesores
                'specializations': {
                    teachers[8].id: 'Electrónica y Control',
                    teachers[9].id: 'Mecánica y Robótica',
                }
            },
        }

        # Asignar materias específicas a profesores
        subject_assignments = {
            'ISC': {
                teachers[0].id: ['ISC101', 'ISC102', 'ISC203', 'ISC204'],  # Programación
                teachers[1].id: ['ISC202', 'ISC205', 'ISC206'],  # Bases de datos y redes
                teachers[2].id: ['ISC301', 'ISC305', 'ISC303'],  # IA y ML
                teachers[3].id: ['ISC103', 'ISC104', 'ISC105', 'ISC106', 'ISC207', 'ISC302', 'ISC304'],  # Matemáticas y otros
            },
            'IND': {
                teachers[4].id: ['IND101', 'IND102', 'IND203', 'IND206'],  # Procesos
                teachers[5].id: ['IND103', 'IND202', 'IND302'],  # Estadística y calidad
                teachers[6].id: ['IND201', 'IND204', 'IND205', 'IND301'],  # Logística
                teachers[7].id: ['IND105', 'IND106', 'IND107', 'IND303', 'IND304', 'IND305'],  # Química y otros
            },
            'IME': {
                teachers[8].id: ['IME102', 'IME106', 'IME201', 'IME202', 'IME204', 'IME206', 'IME302'],  # Electrónica
                teachers[9].id: ['IME101', 'IME103', 'IME104', 'IME105', 'IME107', 'IME203', 'IME205', 'IME301', 'IME303', 'IME304', 'IME305'],  # Mecánica
            },
        }

        # Crear las cualificaciones
        total_qualifications = 0
        for career_code, assignment_data in assignments.items():
            self.stdout.write(f'\n{career_code} - {Career.objects.get(code=career_code).name}:')

            for teacher in assignment_data['teachers']:
                specialization = assignment_data['specializations'].get(teacher.id, '')

                # Actualizar especialización del profesor
                if specialization:
                    teacher.specialization = specialization
                    teacher.save()

                # Obtener las materias asignadas a este profesor
                subject_codes = subject_assignments.get(career_code, {}).get(teacher.id, [])

                if subject_codes:
                    self.stdout.write(f'\n  Profesor: {teacher.user.get_full_name()} ({teacher.employee_id})')
                    self.stdout.write(f'  Especialización: {specialization}')

                    for code in subject_codes:
                        try:
                            subject = Subject.objects.get(code=code)
                            qualification, created = TeacherQualifiedSubject.objects.get_or_create(
                                teacher=teacher,
                                subject=subject,
                                defaults={
                                    'notes': f'Especializado en {specialization}'
                                }
                            )

                            if created:
                                total_qualifications += 1
                                self.stdout.write(self.style.SUCCESS(f'    ✓ Cualificado para: {subject.code} - {subject.name}'))
                            else:
                                self.stdout.write(self.style.WARNING(f'    ⚠ Ya cualificado: {subject.code} - {subject.name}'))
                        except Subject.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f'    ✗ No se encontró la asignatura: {code}'))

        # Resumen final
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('\nRESUMEN:'))
        self.stdout.write(f'Total de asignaturas en base de datos: {Subject.objects.count()}')
        self.stdout.write(f'Total de profesores: {Teacher.objects.count()}')
        self.stdout.write(f'Total de cualificaciones creadas: {total_qualifications}')

        for career_code in ['ISC', 'IND', 'IME']:
            career = Career.objects.get(code=career_code)
            count = Subject.objects.filter(study_plans__study_plan__career=career).distinct().count()
            self.stdout.write(f'  - {career.name}: {count} asignaturas')

        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('\n¡Proceso completado exitosamente!'))
