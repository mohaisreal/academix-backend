import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from academic.models import Career, Subject
from users.models import Teacher, TeacherQualifiedSubject

print('\n' + '='*80)
print('RESUMEN POR CARRERA')
print('='*80 + '\n')

for career in Career.objects.all().order_by('name'):
    subjects = Subject.objects.filter(study_plans__study_plan__career=career).distinct()
    print(f'{career.name} ({career.code}):')
    print(f'  Total asignaturas: {subjects.count()}')
    print(f'  Por año:')
    for year in [1, 2, 3]:
        count = subjects.filter(course_year=year).count()
        if count > 0:
            print(f'    Año {year}: {count} asignaturas')
    print()

print('\n' + '='*80)
print('CUALIFICACIONES DE PROFESORES')
print('='*80 + '\n')

for teacher in Teacher.objects.all().order_by('employee_id'):
    qualifications = TeacherQualifiedSubject.objects.filter(teacher=teacher).select_related('subject')
    print(f'{teacher.user.get_full_name()} ({teacher.employee_id})')
    print(f'  Especialización: {teacher.specialization or "No especificada"}')
    print(f'  Cualificado para {qualifications.count()} asignaturas')
    if qualifications.exists():
        codes = [q.subject.code for q in qualifications[:5]]
        more = '...' if qualifications.count() > 5 else ''
        print(f'  Materias: {", ".join(codes)}{more}')
    print()

print('='*80)
print(f'TOTAL GENERAL:')
print(f'  Carreras: {Career.objects.count()}')
print(f'  Asignaturas: {Subject.objects.count()}')
print(f'  Profesores: {Teacher.objects.count()}')
print(f'  Cualificaciones: {TeacherQualifiedSubject.objects.count()}')
print('='*80)
