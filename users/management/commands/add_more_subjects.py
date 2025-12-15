from django.core.management.base import BaseCommand
from django.utils import timezone
from academic.models import Career, Subject, StudyPlan, StudyPlanSubject
from users.models import Teacher, TeacherQualifiedSubject
from datetime import date


class Command(BaseCommand):
    help = 'Añade 4 asignaturas más por año a cada carrera'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Añadiendo 4 asignaturas más por año a cada carrera...'))

        # Obtener carreras
        try:
            isc = Career.objects.get(code='ISC')
            ind = Career.objects.get(code='IND')
            ime = Career.objects.get(code='IME')
        except Career.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Error: No se encontró una carrera: {e}'))
            return

        # Definir las nuevas asignaturas (4 por año, 3 años = 12 por carrera)
        new_subjects_data = {
            'ISC': [
                # Año 1 - 4 asignaturas más
                {'code': 'ISC108', 'name': 'Introducción a la Ingeniería en Sistemas', 'credits': 3, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC109', 'name': 'Lógica Matemática', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC110', 'name': 'Cálculo Integral', 'credits': 5, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                {'code': 'ISC111', 'name': 'Probabilidad y Estadística', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                # Año 2 - 4 asignaturas más
                {'code': 'ISC208', 'name': 'Programación de Dispositivos Móviles', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC209', 'name': 'Teoría de la Computación', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC210', 'name': 'Análisis y Diseño de Algoritmos', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'ISC211', 'name': 'Interacción Humano-Computadora', 'credits': 3, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                # Año 3 - 4 asignaturas más
                {'code': 'ISC306', 'name': 'Administración de Proyectos de Software', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC307', 'name': 'Arquitectura de Software', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'ISC308', 'name': 'Minería de Datos', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'elective'},
                {'code': 'ISC309', 'name': 'Blockchain y Criptomonedas', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'elective'},
            ],
            'IND': [
                # Año 1 - 4 asignaturas más
                {'code': 'IND108', 'name': 'Introducción a la Ingeniería Industrial', 'credits': 3, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND109', 'name': 'Matemáticas Aplicadas', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND110', 'name': 'Física para Ingenieros', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IND111', 'name': 'Economía Industrial', 'credits': 3, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                # Año 2 - 4 asignaturas más
                {'code': 'IND207', 'name': 'Estudio del Trabajo', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND208', 'name': 'Estadística Inferencial', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND209', 'name': 'Ingeniería Económica', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IND210', 'name': 'Sistemas de Información', 'credits': 3, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                # Año 3 - 4 asignaturas más
                {'code': 'IND306', 'name': 'Planeación Estratégica', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND307', 'name': 'Seguridad e Higiene Industrial', 'credits': 3, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IND308', 'name': 'Cadena de Suministro', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'elective'},
                {'code': 'IND309', 'name': 'Desarrollo Sustentable', 'credits': 3, 'year': 3, 'semester': 2, 'type': 'elective'},
            ],
            'IME': [
                # Año 1 - 4 asignaturas más
                {'code': 'IME108', 'name': 'Química para Ingenieros', 'credits': 4, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME109', 'name': 'Cálculo Vectorial', 'credits': 5, 'year': 1, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME110', 'name': 'Circuitos Eléctricos', 'credits': 4, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IME111', 'name': 'Dibujo Asistido por Computadora', 'credits': 3, 'year': 1, 'semester': 2, 'type': 'mandatory'},
                # Año 2 - 4 asignaturas más
                {'code': 'IME207', 'name': 'Mecánica de Materiales', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME208', 'name': 'Señales y Sistemas', 'credits': 4, 'year': 2, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME209', 'name': 'Control Digital', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                {'code': 'IME210', 'name': 'Programación de PLC', 'credits': 4, 'year': 2, 'semester': 2, 'type': 'mandatory'},
                # Año 3 - 4 asignaturas más
                {'code': 'IME306', 'name': 'Diseño Mecatrónico', 'credits': 4, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME307', 'name': 'Redes Industriales', 'credits': 3, 'year': 3, 'semester': 1, 'type': 'mandatory'},
                {'code': 'IME308', 'name': 'Inteligencia Artificial Aplicada', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'elective'},
                {'code': 'IME309', 'name': 'Manufactura Avanzada', 'credits': 4, 'year': 3, 'semester': 2, 'type': 'elective'},
            ],
        }

        # Crear asignaturas
        created_subjects = {}
        total_created = 0

        for career_code, subjects in new_subjects_data.items():
            career = Career.objects.get(code=career_code)
            created_subjects[career_code] = []

            self.stdout.write(f'\n{career.name} ({career_code}):')

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
                    total_created += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {subject.code} - {subject.name} (Año {subject_data["year"]})'))
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Ya existe: {subject.code}'))

                created_subjects[career_code].append(subject)

                # Añadir al plan de estudios
                study_plan = career.study_plans.filter(is_active=True).first()
                if study_plan:
                    StudyPlanSubject.objects.get_or_create(
                        study_plan=study_plan,
                        subject=subject
                    )

        # Asignar profesores a las nuevas materias
        self.stdout.write('\n' + '='*80)
        self.stdout.write('Asignando profesores a las nuevas asignaturas...')
        self.stdout.write('='*80 + '\n')

        teachers = list(Teacher.objects.all())

        # Asignaciones específicas para las nuevas materias
        new_assignments = {
            'ISC': {
                teachers[0].id: ['ISC208', 'ISC210'],  # Programación
                teachers[1].id: ['ISC211'],  # UX/UI
                teachers[2].id: ['ISC308', 'ISC309'],  # IA y nuevas tecnologías
                teachers[3].id: ['ISC108', 'ISC109', 'ISC110', 'ISC111', 'ISC209', 'ISC306', 'ISC307'],  # Matemáticas y gestión
            },
            'IND': {
                teachers[4].id: ['IND207'],  # Procesos
                teachers[5].id: ['IND208', 'IND307'],  # Estadística y seguridad
                teachers[6].id: ['IND209', 'IND306', 'IND308'],  # Economía y planeación
                teachers[7].id: ['IND108', 'IND109', 'IND110', 'IND111', 'IND210', 'IND309'],  # Ciencias básicas
            },
            'IME': {
                teachers[8].id: ['IME110', 'IME208', 'IME209', 'IME210', 'IME307'],  # Electrónica
                teachers[9].id: ['IME108', 'IME109', 'IME111', 'IME207', 'IME306', 'IME308', 'IME309'],  # Mecánica
            },
        }

        total_qualifications = 0
        for career_code, assignment_data in new_assignments.items():
            career = Career.objects.get(code=career_code)
            self.stdout.write(f'\n{career.name}:')

            for teacher_id, subject_codes in assignment_data.items():
                teacher = Teacher.objects.get(id=teacher_id)
                self.stdout.write(f'  {teacher.user.get_full_name()}:')

                for code in subject_codes:
                    try:
                        subject = Subject.objects.get(code=code)
                        qualification, created = TeacherQualifiedSubject.objects.get_or_create(
                            teacher=teacher,
                            subject=subject,
                            defaults={
                                'notes': f'Cualificado para {subject.name}'
                            }
                        )

                        if created:
                            total_qualifications += 1
                            self.stdout.write(self.style.SUCCESS(f'    ✓ {subject.code} - {subject.name}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'    ⚠ Ya cualificado: {subject.code}'))
                    except Subject.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'    ✗ No encontrada: {code}'))

        # Resumen final
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('RESUMEN FINAL:'))
        self.stdout.write('='*80)
        self.stdout.write(f'\nAsignaturas nuevas creadas: {total_created}')
        self.stdout.write(f'Cualificaciones nuevas: {total_qualifications}')
        self.stdout.write(f'\nTotal de asignaturas en BD: {Subject.objects.count()}')

        for career_code in ['ISC', 'IND', 'IME']:
            career = Career.objects.get(code=career_code)
            total_subjects = Subject.objects.filter(study_plans__study_plan__career=career).distinct().count()
            self.stdout.write(f'  {career.name}: {total_subjects} asignaturas')
            for year in [1, 2, 3]:
                year_count = Subject.objects.filter(
                    study_plans__study_plan__career=career,
                    course_year=year
                ).distinct().count()
                self.stdout.write(f'    Año {year}: {year_count} asignaturas')

        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('¡Proceso completado exitosamente!'))
        self.stdout.write('='*80 + '\n')
