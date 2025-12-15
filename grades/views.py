from rest_framework import viewsets, views, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Avg, Sum, Count, Q, Prefetch
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    GradingCategory,
    Assignment,
    Submission,
    Grade,
    FinalGradeConfig,
    FinalGrade,
    GradeReport,
    CourseMaterial,
    Quiz,
    Question,
    QuestionOption,
    QuizAttempt,
    QuizAnswer,
)
from .serializers import (
    GradingCategorySerializer,
    AssignmentListSerializer,
    AssignmentDetailSerializer,
    SubmissionSerializer,
    GradeSerializer,
    GradebookSerializer,
    FinalGradeConfigSerializer,
    FinalGradeSerializer,
    StudentDashboardSerializer,
    GradeReportSerializer,
    BulkGradeSerializer,
    CourseMaterialSerializer,
    AcademicRecordSerializer,
    GradeTranscriptSerializer,
    ProgressReportSerializer,
    QuizListSerializer,
    QuizDetailSerializer,
    QuizCreateUpdateSerializer,
)
from authentication.permissions import IsAdminUser, IsTeacherUser, IsStudentUser, IsTeacherOrAdmin
from enrollment.models import SubjectGroup, SubjectEnrollment
from users.models import Student, Teacher
from schedules.models import TeacherAssignment
from notifications.models import Notification
from academic.models import AcademicPeriod


class GradingCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para categorías de ponderación
    """
    queryset = GradingCategory.objects.all()
    serializer_class = GradingCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Permisos: CRUD solo teacher/admin, GET todos"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_create']:
            return [IsAuthenticated(), IsTeacherOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Filtrar por permisos"""
        queryset = super().get_queryset()
        user = self.request.user

        # Filtros por query params
        subject_group_id = self.request.query_params.get('subject_group')
        if subject_group_id:
            queryset = queryset.filter(subject_group_id=subject_group_id)

        # Profesores solo ven sus grupos
        if user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(subject_group_id__in=assigned_groups)

        return queryset.select_related('subject_group__subject', 'subject_group__academic_period')

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Crear múltiples categorías a la vez
        POST /api/grades/categories/bulk_create/
        Body: {"subject_group": 1, "categories": [{"name": "Exámenes", "weight": 40}, ...]}
        """
        subject_group_id = request.data.get('subject_group')
        categories_data = request.data.get('categories', [])

        if not subject_group_id:
            return Response(
                {'error': 'subject_group es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar que la suma de pesos = 100%
        total_weight = sum(cat.get('weight', 0) for cat in categories_data)
        if total_weight != 100:
            return Response(
                {'error': f'La suma de pesos debe ser 100%. Suma actual: {total_weight}%'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crear categorías
        created = []
        for order, cat_data in enumerate(categories_data, start=1):
            cat_data['subject_group'] = subject_group_id
            cat_data['order'] = order

            serializer = self.get_serializer(data=cat_data)
            if serializer.is_valid():
                serializer.save()
                created.append(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f'{len(created)} categorías creadas exitosamente',
            'categories': created
        }, status=status.HTTP_201_CREATED)


class AssignmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para assignments (tareas, exámenes, quizzes)
    """
    queryset = Assignment.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        """Usar serializer diferente según acción"""
        if self.action in ['list', 'upcoming', 'pending']:
            return AssignmentListSerializer
        return AssignmentDetailSerializer

    def get_permissions(self):
        """Permisos por acción"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'publish']:
            return [IsAuthenticated(), IsTeacherOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Filtrar según rol y query params"""
        queryset = super().get_queryset()
        user = self.request.user

        # Filtros por query params
        subject_group_id = self.request.query_params.get('subject_group')
        assignment_type = self.request.query_params.get('type')
        category_id = self.request.query_params.get('category')
        published = self.request.query_params.get('published')

        if subject_group_id:
            queryset = queryset.filter(subject_group_id=subject_group_id)

        if assignment_type:
            queryset = queryset.filter(assignment_type=assignment_type)

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if published == 'true':
            queryset = queryset.filter(published_at__isnull=False)

        # Filtrar por rol
        if user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            # Profesores solo ven assignments de sus grupos
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(subject_group_id__in=assigned_groups)

        elif user.role == 'student' and hasattr(user, 'student_profile'):
            # Estudiantes solo ven assignments publicados y asignados a ellos
            student = user.student_profile

            # Grupos en los que está inscrito
            enrolled_groups = SubjectEnrollment.objects.filter(
                student=student,
                status='enrolled'
            ).values_list('subject_group_id', flat=True)

            queryset = queryset.filter(
                Q(subject_group_id__in=enrolled_groups),
                Q(published_at__isnull=False),
                Q(scope='all') | Q(assigned_students=student)
            )

        return queryset.select_related(
            'subject_group__subject',
            'subject_group__academic_period',
            'category',
            'created_by__user'
        ).prefetch_related('assigned_students').distinct()

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publicar assignment
        POST /api/grades/assignments/{id}/publish/
        """
        assignment = self.get_object()
        assignment.publish()

        # Notificar estudiantes
        from notifications.models import Notification

        if assignment.scope == 'all':
            enrollments = assignment.subject_group.enrollments.filter(status='enrolled')
            students = [e.student for e in enrollments]
        else:
            students = assignment.assigned_students.all()

        for student in students:
            Notification.objects.create(
                recipient=student.user,
                title=f'Nueva tarea: {assignment.title}',
                message=f'Se ha publicado una nueva tarea en {assignment.subject_group.subject.name}',
                type='general',
                priority='medium'
            )

        serializer = self.get_serializer(assignment)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """
        Listar entregas de un assignment
        GET /api/grades/assignments/{id}/submissions/
        """
        assignment = self.get_object()
        submissions = assignment.submissions.all().select_related('student__user', 'grade')

        serializer = SubmissionSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Estadísticas de un assignment
        GET /api/grades/assignments/{id}/statistics/
        """
        assignment = self.get_object()

        # Estadísticas de entregas
        submissions = assignment.submissions.exclude(status='draft')
        total_submissions = submissions.count()
        late_submissions = submissions.filter(is_late=True).count()

        # Estadísticas de calificaciones
        grades = assignment.grades.filter(score__isnull=False)
        grades_count = grades.count()

        if grades_count > 0:
            avg_score = grades.aggregate(avg=Avg('score'))['avg']
            max_score_obj = grades.order_by('-score').first()
            min_score_obj = grades.order_by('score').first()

            # Normalizar a escala de 10
            avg_normalized = (avg_score / assignment.max_score) * 10 if avg_score else 0
            max_normalized = (max_score_obj.score / assignment.max_score) * 10 if max_score_obj else 0
            min_normalized = (min_score_obj.score / assignment.max_score) * 10 if min_score_obj else 0
        else:
            avg_normalized = None
            max_normalized = None
            min_normalized = None

        # Total asignado
        if assignment.scope == 'all':
            total_assigned = assignment.subject_group.enrollments.filter(status='enrolled').count()
        else:
            total_assigned = assignment.assigned_students.count()

        return Response({
            'total_assigned': total_assigned,
            'total_submissions': total_submissions,
            'late_submissions': late_submissions,
            'pending_submissions': total_assigned - total_submissions,
            'grades_count': grades_count,
            'average_score': float(avg_normalized) if avg_normalized else None,
            'max_score': float(max_normalized) if max_normalized else None,
            'min_score': float(min_normalized) if min_normalized else None,
        })

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Próximas tareas (próximos 7 días)
        GET /api/grades/assignments/upcoming/
        """
        now = timezone.now()
        end_date = now + timedelta(days=7)

        queryset = self.get_queryset().filter(
            due_date__gte=now,
            due_date__lte=end_date
        ).order_by('due_date')

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """
        Tareas pendientes del estudiante (no entregadas)
        GET /api/grades/assignments/pending/
        """
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {'error': 'Solo disponible para estudiantes'},
                status=status.HTTP_403_FORBIDDEN
            )

        student = request.user.student_profile
        queryset = self.get_queryset()

        # Excluir assignments con entrega
        submitted = Submission.objects.filter(
            student=student
        ).exclude(status='draft').values_list('assignment_id', flat=True)

        queryset = queryset.exclude(id__in=submitted).order_by('due_date')

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SubmissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para entregas de estudiantes
    """
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        """Permisos por acción"""
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsStudentUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Filtrar según rol"""
        queryset = super().get_queryset()
        user = self.request.user

        # Filtros por query params
        assignment_id = self.request.query_params.get('assignment')
        student_id = self.request.query_params.get('student')
        status_param = self.request.query_params.get('status')

        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)

        if student_id:
            queryset = queryset.filter(student_id=student_id)

        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filtrar por rol
        if user.role == 'student' and hasattr(user, 'student_profile'):
            # Estudiantes solo ven sus entregas
            queryset = queryset.filter(student=user.student_profile)

        elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            # Profesores ven entregas de sus grupos
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(assignment__subject_group_id__in=assigned_groups)

        return queryset.select_related(
            'assignment__subject_group__subject',
            'student__user'
        ).prefetch_related('grade')

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Marcar submission como entregada
        POST /api/grades/submissions/{id}/submit/
        """
        submission = self.get_object()

        if not submission.can_submit():
            return Response(
                {'error': 'No se puede entregar en este momento'},
                status=status.HTTP_400_BAD_REQUEST
            )

        submission.submit()

        # Notificar al profesor
        from notifications.models import Notification
        teacher_assignments = TeacherAssignment.objects.filter(
            subject_group=submission.assignment.subject_group,
            is_main_teacher=True,
            status='active'
        ).select_related('teacher__user')

        for ta in teacher_assignments:
            Notification.objects.create(
                recipient=ta.teacher.user,
                title=f'Nueva entrega: {submission.assignment.title}',
                message=f'{submission.student.user.get_full_name()} ha entregado la tarea',
                type='general',
                priority='low'
            )

        serializer = self.get_serializer(submission)
        return Response(serializer.data)


class GradeViewSet(viewsets.ModelViewSet):
    """
    ViewSet para calificaciones individuales
    """
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        """Permisos por acción"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_grade']:
            return [IsAuthenticated(), IsTeacherOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Filtrar según rol"""
        queryset = super().get_queryset()
        user = self.request.user

        # Filtros por query params
        assignment_id = self.request.query_params.get('assignment')
        student_id = self.request.query_params.get('student')
        subject_group_id = self.request.query_params.get('subject_group')

        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)

        if student_id:
            queryset = queryset.filter(student_id=student_id)

        if subject_group_id:
            queryset = queryset.filter(assignment__subject_group_id=subject_group_id)

        # Filtrar por rol
        if user.role == 'student' and hasattr(user, 'student_profile'):
            # Estudiantes solo ven sus calificaciones
            queryset = queryset.filter(student=user.student_profile)

        elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            # Profesores ven calificaciones de sus grupos
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(assignment__subject_group_id__in=assigned_groups)

        return queryset.select_related(
            'assignment__subject_group__subject',
            'student__user',
            'submission',
            'graded_by__user'
        )

    @action(detail=False, methods=['post'])
    def bulk_grade(self, request):
        """
        Calificar múltiples entregas a la vez
        POST /api/grades/bulk_grade/
        Body: {"grades": [{"assignment_id": 1, "student_id": 1, "score": 8.5, "feedback": "Bien"}, ...]}
        """
        serializer = BulkGradeSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            result = serializer.save()

            # Notificar estudiantes
            from notifications.models import Notification
            for grade_data in request.data.get('grades', []):
                try:
                    student = Student.objects.get(id=grade_data['student_id'])
                    assignment = Assignment.objects.get(id=grade_data['assignment_id'])

                    Notification.objects.create(
                        recipient=student.user,
                        title=f'Nueva calificación: {assignment.title}',
                        message=f'Tu tarea ha sido calificada: {grade_data["score"]}',
                        type='grade_published',
                        priority='medium'
                    )
                except:
                    pass

            return Response(result, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_grades(self, request):
        """
        Obtener calificaciones del estudiante en formato compatible con frontend
        GET /api/grades/grades/my_grades/
        """
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {'error': 'Solo disponible para estudiantes'},
                status=status.HTTP_403_FORBIDDEN
            )

        student = request.user.student_profile

        # Obtener todas las inscripciones del estudiante
        enrollments = SubjectEnrollment.objects.filter(
            student=student,
            status='enrolled'
        ).select_related('subject_group__subject', 'subject_group__academic_period')

        grades_data = []

        for enrollment in enrollments:
            # Obtener calificaciones de este grupo
            student_grades = Grade.objects.filter(
                student=student,
                assignment__subject_group=enrollment.subject_group,
                score__isnull=False
            ).select_related('assignment__category')

            for grade in student_grades:
                # Transformar al formato esperado por el frontend
                grade_obj = {
                    'id': grade.id,
                    'subject_enrollment': {
                        'id': enrollment.id,
                        'subject_group': {
                            'subject': {
                                'code': enrollment.subject_group.subject.code,
                                'name': enrollment.subject_group.subject.name,
                                'credits': enrollment.subject_group.subject.credits,
                            },
                            'group_code': enrollment.subject_group.code,
                        }
                    },
                    'evaluation': {
                        'id': grade.assignment.category.id if grade.assignment.category else 0,
                        'name': grade.assignment.category.name if grade.assignment.category else grade.assignment.title,
                        'weight': float(grade.assignment.category.weight) if grade.assignment.category else 0,
                        'evaluation_type': grade.assignment.assignment_type,
                    },
                    'score': float(grade.get_normalized_score()),  # Normalizado a escala 0-10
                    'comments': grade.feedback or '',
                    'created_at': grade.graded_at.isoformat() if grade.graded_at else grade.created_at.isoformat(),
                }
                grades_data.append(grade_obj)

        return Response(grades_data)


class GradebookViewSet(viewsets.ViewSet):
    """
    ViewSet para el libro de calificaciones (no es ModelViewSet)
    """
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]

    @action(detail=False, methods=['get'])
    def by_subject_group(self, request):
        """
        Obtener gradebook completo de un grupo
        GET /api/grades/gradebook/by_subject_group/?subject_group=1
        """
        subject_group_id = request.query_params.get('subject_group')

        if not subject_group_id:
            return Response(
                {'error': 'subject_group es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            subject_group = SubjectGroup.objects.select_related(
                'subject',
                'academic_period'
            ).get(id=subject_group_id)
        except SubjectGroup.DoesNotExist:
            return Response(
                {'error': 'Grupo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Obtener categorías
        categories = GradingCategory.objects.filter(subject_group=subject_group).order_by('order')

        # Obtener assignments agrupados por categoría
        assignments_by_category = []
        for category in categories:
            assignments = Assignment.objects.filter(
                subject_group=subject_group,
                category=category,
                published_at__isnull=False
            ).order_by('due_date')

            assignments_by_category.append({
                'category': GradingCategorySerializer(category).data,
                'assignments': AssignmentListSerializer(assignments, many=True).data
            })

        # Assignments sin categoría
        uncategorized = Assignment.objects.filter(
            subject_group=subject_group,
            category__isnull=True,
            published_at__isnull=False
        ).order_by('due_date')

        if uncategorized.exists():
            assignments_by_category.append({
                'category': None,
                'assignments': AssignmentListSerializer(uncategorized, many=True).data
            })

        # Obtener estudiantes con sus calificaciones
        enrollments = SubjectEnrollment.objects.filter(
            subject_group=subject_group,
            status='enrolled'
        ).select_related('student__user').prefetch_related(
            Prefetch('grades', queryset=Grade.objects.select_related('assignment'))
        )

        students_data = []
        for enrollment in enrollments:
            student = enrollment.student

            # Diccionario con calificaciones por assignment
            grades_dict = {}
            for grade in enrollment.grades.all():
                grades_dict[grade.assignment_id] = {
                    'score': float(grade.score) if grade.score else None,
                    'normalized': float(grade.get_normalized_score()) if grade.score else None,
                    'feedback': grade.feedback
                }

            # Promedios por categoría
            category_averages = {}
            for category in categories:
                cat_grades = [
                    g for g in enrollment.grades.all()
                    if g.assignment.category_id == category.id and g.score is not None
                ]

                if cat_grades:
                    avg = sum(g.get_normalized_score() for g in cat_grades) / len(cat_grades)
                    category_averages[category.id] = float(avg)
                else:
                    category_averages[category.id] = None

            # Calificación final
            try:
                final_grade = enrollment.final_grade
                final_score = float(final_grade.final_score) if final_grade.final_score else None
                final_status = final_grade.status
            except:
                final_score = None
                final_status = None

            students_data.append({
                'student_id': student.id,
                'student_code': student.student_id,
                'student_name': student.user.get_full_name(),
                'student_email': student.user.email,
                'grades': grades_dict,
                'category_averages': category_averages,
                'final_grade': final_score,
                'status': final_status
            })

        # Estadísticas generales
        total_students = len(students_data)
        total_assignments = Assignment.objects.filter(
            subject_group=subject_group,
            published_at__isnull=False
        ).count()

        data = {
            'subject_group_id': subject_group.id,
            'subject_name': subject_group.subject.name,
            'subject_code': subject_group.subject.code,
            'group_code': subject_group.code,
            'academic_period': subject_group.academic_period.name,
            'categories': GradingCategorySerializer(categories, many=True).data,
            'assignments': assignments_by_category,
            'students': students_data,
            'statistics': {
                'total_students': total_students,
                'total_assignments': total_assignments
            }
        }

        return Response(data)

    @action(detail=False, methods=['post'])
    def calculate_final_grades(self, request):
        """
        Recalcular todas las calificaciones finales de un grupo
        POST /api/grades/gradebook/calculate_final_grades/
        Body: {"subject_group": 1}
        """
        subject_group_id = request.data.get('subject_group')

        if not subject_group_id:
            return Response(
                {'error': 'subject_group es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        enrollments = SubjectEnrollment.objects.filter(
            subject_group_id=subject_group_id,
            status='enrolled'
        )

        calculated = []
        errors = []

        for enrollment in enrollments:
            try:
                final_grade, created = FinalGrade.objects.get_or_create(
                    subject_enrollment=enrollment
                )

                final_grade.calculate_with_categories()

                calculated.append({
                    'student_id': enrollment.student.id,
                    'student_name': enrollment.student.user.get_full_name(),
                    'final_score': float(final_grade.final_score) if final_grade.final_score else None,
                    'status': final_grade.status
                })
            except Exception as e:
                errors.append({
                    'student_id': enrollment.student.id,
                    'error': str(e)
                })

        return Response({
            'calculated_count': len(calculated),
            'error_count': len(errors),
            'calculated': calculated,
            'errors': errors
        })


class FinalGradeConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet para configuración de calificación final
    """
    queryset = FinalGradeConfig.objects.all()
    serializer_class = FinalGradeConfigSerializer
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        """Filtrar por query params"""
        queryset = super().get_queryset()

        subject_group_id = self.request.query_params.get('subject_group')
        if subject_group_id:
            queryset = queryset.filter(subject_group_id=subject_group_id)

        return queryset.select_related('subject_group__subject')


class FinalGradeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para calificaciones finales (solo lectura + publish)
    """
    queryset = FinalGrade.objects.all()
    serializer_class = FinalGradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtrar según rol"""
        queryset = super().get_queryset()
        user = self.request.user

        # Filtros por query params
        student_id = self.request.query_params.get('student')
        subject_group_id = self.request.query_params.get('subject_group')
        published = self.request.query_params.get('published')

        if student_id:
            queryset = queryset.filter(subject_enrollment__student_id=student_id)

        if subject_group_id:
            queryset = queryset.filter(subject_enrollment__subject_group_id=subject_group_id)

        if published == 'true':
            queryset = queryset.filter(is_published=True)

        # Filtrar por rol
        if user.role == 'student' and hasattr(user, 'student_profile'):
            # Estudiantes solo ven sus calificaciones publicadas
            queryset = queryset.filter(
                subject_enrollment__student=user.student_profile,
                is_published=True
            )

        elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            # Profesores ven calificaciones de sus grupos
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(subject_enrollment__subject_group_id__in=assigned_groups)

        return queryset.select_related(
            'subject_enrollment__student__user',
            'subject_enrollment__subject_group__subject'
        )

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publicar calificación final
        POST /api/grades/final-grades/{id}/publish/
        """
        final_grade = self.get_object()
        final_grade.publish()

        serializer = self.get_serializer(final_grade)
        return Response(serializer.data)


class StudentDashboardView(views.APIView):
    """
    Dashboard completo del estudiante
    GET /api/grades/student-dashboard/
    """
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {'error': 'Perfil de estudiante no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        student = request.user.student_profile

        # Grupos inscritos
        enrolled_groups = SubjectEnrollment.objects.filter(
            student=student,
            status='enrolled'
        ).values_list('subject_group_id', flat=True)

        # Tareas pendientes (no entregadas, no vencidas)
        now = timezone.now()
        pending = Assignment.objects.filter(
            Q(subject_group_id__in=enrolled_groups),
            Q(published_at__isnull=False),
            Q(due_date__gte=now),
            Q(scope='all') | Q(assigned_students=student)
        ).exclude(
            id__in=Submission.objects.filter(student=student).exclude(status='draft').values_list('assignment_id', flat=True)
        ).order_by('due_date')[:5]

        # Próximas tareas (próximos 7 días)
        end_date = now + timedelta(days=7)
        upcoming = Assignment.objects.filter(
            Q(subject_group_id__in=enrolled_groups),
            Q(published_at__isnull=False),
            Q(due_date__gte=now, due_date__lte=end_date),
            Q(scope='all') | Q(assigned_students=student)
        ).order_by('due_date')[:5]

        # Calificaciones recientes (últimos 30 días)
        recent_date = now - timedelta(days=30)
        recent_grades = Grade.objects.filter(
            student=student,
            graded_at__gte=recent_date,
            score__isnull=False
        ).order_by('-graded_at')[:10]

        # Resumen por asignatura
        subjects_summary = []
        enrollments = SubjectEnrollment.objects.filter(
            student=student,
            status='enrolled'
        ).select_related('subject_group__subject')

        for enrollment in enrollments:
            # Calificaciones de esta asignatura
            grades = Grade.objects.filter(
                student=student,
                assignment__subject_group=enrollment.subject_group,
                score__isnull=False
            )

            if grades.exists():
                avg = grades.aggregate(avg=Avg('score'))['avg']
                avg_normalized = sum(g.get_normalized_score() for g in grades) / grades.count()
            else:
                avg_normalized = None

            # Tareas pendientes de esta asignatura
            pending_count = Assignment.objects.filter(
                subject_group=enrollment.subject_group,
                published_at__isnull=False,
                due_date__gte=now
            ).exclude(
                id__in=Submission.objects.filter(student=student).exclude(status='draft').values_list('assignment_id', flat=True)
            ).count()

            subjects_summary.append({
                'subject_id': enrollment.subject_group.subject.id,
                'subject_name': enrollment.subject_group.subject.name,
                'subject_code': enrollment.subject_group.subject.code,
                'group_code': enrollment.subject_group.code,
                'average': float(avg_normalized) if avg_normalized else None,
                'pending_assignments': pending_count
            })

        # Estadísticas generales
        total_assignments = Assignment.objects.filter(
            Q(subject_group_id__in=enrolled_groups),
            Q(published_at__isnull=False),
            Q(scope='all') | Q(assigned_students=student)
        ).count()

        total_submissions = Submission.objects.filter(
            student=student
        ).exclude(status='draft').count()

        total_graded = Grade.objects.filter(
            student=student,
            score__isnull=False
        ).count()

        data = {
            'pending_assignments': AssignmentListSerializer(pending, many=True, context={'request': request}).data,
            'upcoming_assignments': AssignmentListSerializer(upcoming, many=True, context={'request': request}).data,
            'recent_grades': GradeSerializer(recent_grades, many=True, context={'request': request}).data,
            'subjects_summary': subjects_summary,
            'statistics': {
                'total_assignments': total_assignments,
                'total_submissions': total_submissions,
                'total_graded': total_graded,
                'pending_count': total_assignments - total_submissions
            }
        }

        return Response(data)


# ==================== COURSE MATERIALS VIEWSET ====================

class CourseMaterialViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar material educativo del curso
    """
    serializer_class = CourseMaterialSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        """Permisos: CRUD solo teacher/admin, GET todos autenticados"""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'publish', 'bulk_delete']:
            return [IsAuthenticated(), IsTeacherOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = CourseMaterial.objects.select_related('subject_group', 'uploaded_by').all()

        # Filtrar por rol
        if hasattr(user, 'teacher_profile'):
            # Profesores ven material de sus grupos asignados
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(subject_group_id__in=assigned_groups)
        elif hasattr(user, 'student_profile'):
            # Estudiantes solo ven material publicado de sus grupos
            student_groups = SubjectEnrollment.objects.filter(
                student=user.student_profile,
                status='enrolled'
            ).values_list('subject_group_id', flat=True)

            queryset = queryset.filter(
                subject_group_id__in=student_groups,
                is_published=True
            )

        # Filtros opcionales
        subject_group = self.request.query_params.get('subject_group')
        folder = self.request.query_params.get('folder')
        is_published = self.request.query_params.get('is_published')

        if subject_group:
            queryset = queryset.filter(subject_group_id=subject_group)
        if folder:
            queryset = queryset.filter(folder=folder)
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        return queryset.order_by('folder', 'order', 'title')

    @action(detail=False, methods=['get'])
    def by_folder(self, request):
        """
        Agrupar materiales por carpeta
        """
        subject_group_id = request.query_params.get('subject_group')
        if not subject_group_id:
            return Response(
                {'error': 'subject_group parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        materials = self.get_queryset().filter(subject_group_id=subject_group_id)

        # Agrupar por carpeta
        folders = {}
        for material in materials:
            folder_name = material.folder or 'General'
            if folder_name not in folders:
                folders[folder_name] = []
            folders[folder_name].append(material)

        # Crear respuesta
        result = []
        for folder_name, folder_materials in folders.items():
            result.append({
                'folder_name': folder_name,
                'materials': CourseMaterialSerializer(folder_materials, many=True, context={'request': request}).data,
                'total_size': sum(m.file_size for m in folder_materials),
                'file_count': len(folder_materials)
            })

        return Response(result)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publicar material para que los estudiantes puedan verlo
        """
        material = self.get_object()
        material.is_published = True
        material.save()

        # Crear notificación para estudiantes
        students = Student.objects.filter(
            subjectenrollment__subject_group=material.subject_group,
            subjectenrollment__status='enrolled'
        )

        for student in students:
            Notification.objects.create(
                user=student.user,
                title='Nuevo Material Disponible',
                message=f'Se ha publicado nuevo material en {material.subject_group.subject.name}: {material.title}',
                notification_type='material',
                related_object_type='CourseMaterial',
                related_object_id=material.id
            )

        return Response(
            CourseMaterialSerializer(material, context={'request': request}).data
        )

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """
        Eliminar múltiples materiales
        """
        material_ids = request.data.get('material_ids', [])

        if not material_ids:
            return Response(
                {'error': 'material_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar que el usuario tenga permiso
        materials = self.get_queryset().filter(id__in=material_ids)
        deleted_count = materials.count()
        materials.delete()

        return Response({'deleted': deleted_count})


# ==================== ACADEMIC RECORD VIEWS (PHASE 3) ====================

class AcademicRecordView(APIView):
    """
    Vista para obtener el expediente académico completo de un estudiante
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id=None):
        """
        Obtener expediente académico
        - Estudiantes pueden ver solo su propio expediente
        - Profesores y administradores pueden ver cualquier expediente
        """
        user = request.user

        # Determinar qué estudiante consultar
        if student_id:
            # Verificar permisos
            if not (hasattr(user, 'teacher_profile') or user.is_staff):
                return Response(
                    {'error': 'No tiene permiso para ver este expediente'},
                    status=status.HTTP_403_FORBIDDEN
                )
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return Response(
                    {'error': 'Estudiante no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # El estudiante consulta su propio expediente
            if not hasattr(user, 'student_profile'):
                return Response(
                    {'error': 'Usuario no es un estudiante'},
                    status=status.HTTP_403_FORBIDDEN
                )
            student = user.student_profile

        # Obtener todas las inscripciones del estudiante
        enrollments = SubjectEnrollment.objects.filter(
            student=student
        ).select_related(
            'subject_group__subject',
            'subject_group__teacher__user',
            'subject_group__academic_period'
        ).prefetch_related('subject_group__final_grades')

        # Agrupar por período académico
        periods_dict = {}
        total_credits_enrolled = 0
        total_credits_passed = 0
        all_grades = []

        for enrollment in enrollments:
            subject_group = enrollment.subject_group
            period_key = subject_group.academic_period.name
            subject = subject_group.subject

            # Obtener calificación final
            try:
                final_grade = FinalGrade.objects.get(
                    subject_group=subject_group,
                    student=student
                )
                final_grade_value = final_grade.final_grade
                status_value = final_grade.status
                passed = final_grade.passed
            except FinalGrade.DoesNotExist:
                final_grade_value = None
                status_value = 'pending'
                passed = False

            # Contar tareas
            assignments_count = Assignment.objects.filter(
                subject_group=subject_group,
                is_published=True
            ).count()

            # Crear registro de materia
            subject_record = {
                'subject_id': subject.id,
                'subject_code': subject.code,
                'subject_name': subject.name,
                'credits': subject.credits,
                'final_grade': final_grade_value,
                'status': status_value,
                'academic_period': period_key,
                'teacher_name': f"{subject_group.teacher.user.first_name} {subject_group.teacher.user.last_name}",
                'assignments_count': assignments_count,
                'passed': passed,
            }

            # Agregar al período correspondiente
            if period_key not in periods_dict:
                periods_dict[period_key] = {
                    'period_name': period_key,
                    'period_id': subject_group.academic_period.id,
                    'subjects': [],
                    'total_credits': 0,
                    'credits_passed': 0,
                    'period_average': None,
                }

            periods_dict[period_key]['subjects'].append(subject_record)
            periods_dict[period_key]['total_credits'] += subject.credits
            total_credits_enrolled += subject.credits

            if passed:
                periods_dict[period_key]['credits_passed'] += subject.credits
                total_credits_passed += subject.credits

            if final_grade_value is not None:
                all_grades.append(float(final_grade_value))

        # Calcular promedios por período
        for period_data in periods_dict.values():
            period_grades = [
                s['final_grade'] for s in period_data['subjects']
                if s['final_grade'] is not None
            ]
            if period_grades:
                period_data['period_average'] = sum(period_grades) / len(period_grades)

        # Calcular promedio general
        overall_average = sum(all_grades) / len(all_grades) if all_grades else None

        # Obtener información de la carrera
        career_enrollment = enrollment.student.careerenrollment_set.first()
        career_name = career_enrollment.career.name if career_enrollment else 'N/A'

        # Construir respuesta
        record_data = {
            'student_id': student.id,
            'student_code': student.student_code,
            'student_name': f"{student.user.first_name} {student.user.last_name}",
            'career_name': career_name,
            'overall_average': overall_average,
            'total_credits_enrolled': total_credits_enrolled,
            'total_credits_passed': total_credits_passed,
            'periods': list(periods_dict.values()),
        }

        serializer = AcademicRecordSerializer(record_data)
        return Response(serializer.data)


class GradeTranscriptView(APIView):
    """
    Vista para generar certificado de calificaciones oficial
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id=None):
        """
        Generar certificado de calificaciones
        """
        user = request.user

        # Determinar qué estudiante consultar
        if student_id:
            # Solo admin o profesores pueden generar certificados de otros
            if not (hasattr(user, 'teacher_profile') or user.is_staff):
                return Response(
                    {'error': 'No tiene permiso para generar este certificado'},
                    status=status.HTTP_403_FORBIDDEN
                )
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return Response(
                    {'error': 'Estudiante no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            if not hasattr(user, 'student_profile'):
                return Response(
                    {'error': 'Usuario no es un estudiante'},
                    status=status.HTTP_403_FORBIDDEN
                )
            student = user.student_profile

        # Obtener todas las calificaciones finales aprobadas
        final_grades = FinalGrade.objects.filter(
            student=student,
            passed=True
        ).select_related(
            'subject_group__subject',
            'subject_group__academic_period'
        ).order_by('subject_group__academic_period__start_date', 'subject_group__subject__code')

        subjects_data = []
        total_credits = 0
        all_grades = []

        for fg in final_grades:
            subject = fg.subject_group.subject
            subjects_data.append({
                'subject_code': subject.code,
                'subject_name': subject.name,
                'credits': subject.credits,
                'final_grade': float(fg.final_grade),
                'letter_grade': fg.letter_grade,
                'academic_period': fg.subject_group.academic_period.name,
                'completion_date': fg.graded_at,
            })
            total_credits += subject.credits
            all_grades.append(float(fg.final_grade))

        # Calcular promedio ponderado
        weighted_sum = sum(
            float(fg.final_grade) * fg.subject_group.subject.credits
            for fg in final_grades
        )
        cumulative_gpa = weighted_sum / total_credits if total_credits > 0 else None

        # Información de la carrera
        career_enrollment = student.careerenrollment_set.first()
        career_name = career_enrollment.career.name if career_enrollment else 'N/A'

        transcript_data = {
            'student_id': student.id,
            'student_code': student.student_code,
            'student_name': f"{student.user.first_name} {student.user.last_name}",
            'career_name': career_name,
            'total_credits_completed': total_credits,
            'cumulative_gpa': cumulative_gpa,
            'subjects': subjects_data,
            'generated_at': timezone.now(),
        }

        serializer = GradeTranscriptSerializer(transcript_data)
        return Response(serializer.data)


class ProgressReportView(APIView):
    """
    Vista para generar reporte de progreso académico
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id=None):
        """
        Generar reporte de progreso con tendencias y alertas
        """
        user = request.user

        # Determinar qué estudiante consultar
        if student_id:
            if not (hasattr(user, 'teacher_profile') or user.is_staff):
                return Response(
                    {'error': 'No tiene permiso para ver este reporte'},
                    status=status.HTTP_403_FORBIDDEN
                )
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return Response(
                    {'error': 'Estudiante no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            if not hasattr(user, 'student_profile'):
                return Response(
                    {'error': 'Usuario no es un estudiante'},
                    status=status.HTTP_403_FORBIDDEN
                )
            student = user.student_profile

        # Obtener estadísticas actuales
        current_enrollments = SubjectEnrollment.objects.filter(
            student=student,
            subject_group__academic_period__is_active=True
        ).select_related('subject_group__subject')

        current_subjects_count = current_enrollments.count()
        current_credits = sum(e.subject_group.subject.credits for e in current_enrollments)

        # Calificaciones del período actual
        current_grades = FinalGrade.objects.filter(
            student=student,
            subject_group__academic_period__is_active=True
        ).select_related('subject_group__subject')

        graded_subjects = current_grades.count()
        current_average = None
        if current_grades.exists():
            grades_list = [float(g.final_grade) for g in current_grades]
            current_average = sum(grades_list) / len(grades_list)

        # Tendencias históricas (últimos 3 períodos)
        historical_periods = AcademicPeriod.objects.filter(
            subjectgroup__subject_enrollments__student=student
        ).distinct().order_by('-start_date')[:3]

        trends = []
        for period in historical_periods:
            period_grades = FinalGrade.objects.filter(
                student=student,
                subject_group__academic_period=period
            )
            if period_grades.exists():
                period_avg = sum(float(g.final_grade) for g in period_grades) / period_grades.count()
                passed = period_grades.filter(passed=True).count()
                failed = period_grades.filter(passed=False).count()

                trends.append({
                    'period_name': period.name,
                    'average': period_avg,
                    'subjects_passed': passed,
                    'subjects_failed': failed,
                })

        # Generar alertas
        alerts = []

        # Alerta: Promedio bajo
        if current_average and current_average < 70:
            alerts.append({
                'type': 'warning',
                'severity': 'high',
                'message': f'Tu promedio actual ({current_average:.1f}) está por debajo de 70',
                'recommendation': 'Considera buscar apoyo académico o tutorías'
            })

        # Alerta: Materias en riesgo
        at_risk_subjects = []
        for enrollment in current_enrollments:
            try:
                fg = FinalGrade.objects.get(
                    student=student,
                    subject_group=enrollment.subject_group
                )
                if fg.final_grade and fg.final_grade < 60:
                    at_risk_subjects.append(enrollment.subject_group.subject.name)
            except FinalGrade.DoesNotExist:
                pass

        if at_risk_subjects:
            alerts.append({
                'type': 'danger',
                'severity': 'high',
                'message': f'Tienes {len(at_risk_subjects)} materia(s) en riesgo de reprobar',
                'subjects': at_risk_subjects,
                'recommendation': 'Enfócate en mejorar estas materias prioritariamente'
            })

        # Alerta: Tareas pendientes
        pending_submissions = Submission.objects.filter(
            student=student,
            assignment__subject_group__academic_period__is_active=True,
            status='pending'
        ).count()

        if pending_submissions > 5:
            alerts.append({
                'type': 'warning',
                'severity': 'medium',
                'message': f'Tienes {pending_submissions} tareas pendientes de entregar',
                'recommendation': 'Organiza tu tiempo para completar las entregas pendientes'
            })

        # Tendencia de mejora/declive
        if len(trends) >= 2:
            recent_avg = trends[0]['average']
            previous_avg = trends[1]['average']
            diff = recent_avg - previous_avg

            if diff > 5:
                alerts.append({
                    'type': 'success',
                    'severity': 'low',
                    'message': f'¡Excelente! Tu promedio ha mejorado {diff:.1f} puntos',
                    'recommendation': 'Sigue con el buen trabajo'
                })
            elif diff < -5:
                alerts.append({
                    'type': 'warning',
                    'severity': 'medium',
                    'message': f'Tu promedio ha bajado {abs(diff):.1f} puntos',
                    'recommendation': 'Identifica las áreas que necesitan más atención'
                })

        progress_data = {
            'student_id': student.id,
            'student_name': f"{student.user.first_name} {student.user.last_name}",
            'current_period_subjects': current_subjects_count,
            'current_period_credits': current_credits,
            'current_period_average': current_average,
            'graded_subjects_count': graded_subjects,
            'trends': trends,
            'alerts': alerts,
            'generated_at': timezone.now(),
        }

        serializer = ProgressReportSerializer(progress_data)
        return Response(serializer.data)


# ==================== QUIZ VIEWS (PHASE 4) ====================

class QuizViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de quizzes
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return QuizListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return QuizCreateUpdateSerializer
        return QuizDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Quiz.objects.all()

        # Profesores ven quizzes de sus grupos asignados
        if hasattr(user, 'teacher_profile'):
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(subject_group_id__in=assigned_groups)
        # Estudiantes ven quizzes publicados de sus materias
        elif hasattr(user, 'student_profile'):
            queryset = queryset.filter(
                subject_group__subject_enrollments__student=user.student_profile,
                is_published=True
            )

        # Filtros
        subject_group = self.request.query_params.get('subject_group')
        if subject_group:
            queryset = queryset.filter(subject_group_id=subject_group)

        quiz_type = self.request.query_params.get('quiz_type')
        if quiz_type:
            queryset = queryset.filter(quiz_type=quiz_type)

        # Anotar con información del estudiante si aplica
        if hasattr(user, 'student_profile'):
            from django.db.models import Count, Max
            queryset = queryset.annotate(
                student_attempts_count=Count(
                    'attempts',
                    filter=Q(attempts__student=user.student_profile)
                ),
                student_best_score=Max(
                    'attempts__percentage',
                    filter=Q(attempts__student=user.student_profile)
                )
            )

        return queryset.select_related(
            'subject_group__subject',
            'subject_group__teacher__user',
            'created_by__user'
        ).prefetch_related('questions')

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publicar un quiz"""
        quiz = self.get_object()
        quiz.is_published = True
        quiz.save()

        serializer = self.get_serializer(quiz)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Despublicar un quiz"""
        quiz = self.get_object()
        quiz.is_published = False
        quiz.save()

        serializer = self.get_serializer(quiz)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Obtener estadísticas de un quiz"""
        quiz = self.get_object()

        attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            status='graded'
        )

        total_attempts = attempts.count()
        unique_students = attempts.values('student').distinct().count()
        completed_attempts = attempts.filter(submitted_at__isnull=False).count()

        # Calcular promedios
        avg_score = attempts.aggregate(Avg('percentage'))['percentage__avg']

        # Tasa de aprobación
        passed_attempts = attempts.filter(percentage__gte=quiz.passing_score).count()
        pass_rate = (passed_attempts / total_attempts * 100) if total_attempts > 0 else None

        # Tiempo promedio
        completed = attempts.filter(submitted_at__isnull=False)
        if completed.exists():
            total_seconds = sum(
                (a.submitted_at - a.started_at).total_seconds()
                for a in completed
            )
            avg_time_minutes = total_seconds / completed.count() / 60
        else:
            avg_time_minutes = None

        # Distribución de puntajes
        score_ranges = [
            {'range': '0-59', 'count': 0},
            {'range': '60-69', 'count': 0},
            {'range': '70-79', 'count': 0},
            {'range': '80-89', 'count': 0},
            {'range': '90-100', 'count': 0},
        ]

        for attempt in attempts:
            if attempt.percentage is not None:
                if attempt.percentage < 60:
                    score_ranges[0]['count'] += 1
                elif attempt.percentage < 70:
                    score_ranges[1]['count'] += 1
                elif attempt.percentage < 80:
                    score_ranges[2]['count'] += 1
                elif attempt.percentage < 90:
                    score_ranges[3]['count'] += 1
                else:
                    score_ranges[4]['count'] += 1

        stats_data = {
            'quiz_id': quiz.id,
            'quiz_title': quiz.title,
            'total_attempts': total_attempts,
            'unique_students': unique_students,
            'completed_attempts': completed_attempts,
            'average_score': avg_score,
            'pass_rate': pass_rate,
            'average_time_minutes': avg_time_minutes,
            'score_distribution': score_ranges,
        }

        from .serializers import QuizStatisticsSerializer
        serializer = QuizStatisticsSerializer(stats_data)
        return Response(serializer.data)


class QuestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de preguntas
    """
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            from .serializers import QuestionWithOptionsCreateSerializer
            return QuestionWithOptionsCreateSerializer
        from .serializers import QuestionSerializer
        return QuestionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Question.objects.all()

        # Profesores solo ven preguntas de sus quizzes
        if hasattr(user, 'teacher_profile'):
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(quiz__subject_group_id__in=assigned_groups)

        # Filtrar por quiz
        quiz_id = self.request.query_params.get('quiz')
        if quiz_id:
            queryset = queryset.filter(quiz_id=quiz_id)

        return queryset.select_related('quiz').prefetch_related('options')


class QuestionOptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de opciones de pregunta
    """
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]

    def get_serializer_class(self):
        from .serializers import QuestionOptionSerializer
        return QuestionOptionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = QuestionOption.objects.all()

        # Profesores solo ven opciones de sus preguntas
        if hasattr(user, 'teacher_profile'):
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(question__quiz__subject_group_id__in=assigned_groups)

        # Filtrar por pregunta
        question_id = self.request.query_params.get('question')
        if question_id:
            queryset = queryset.filter(question_id=question_id)

        return queryset.select_related('question__quiz')


class QuizAttemptViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de intentos de quiz
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        from .serializers import QuizAttemptListSerializer, QuizAttemptDetailSerializer
        if self.action == 'list':
            return QuizAttemptListSerializer
        return QuizAttemptDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = QuizAttempt.objects.all()

        # Profesores ven intentos de sus quizzes
        if hasattr(user, 'teacher_profile'):
            assigned_groups = TeacherAssignment.objects.filter(
                teacher=user.teacher_profile,
                status='active'
            ).values_list('subject_group_id', flat=True)
            queryset = queryset.filter(quiz__subject_group_id__in=assigned_groups)
        # Estudiantes solo ven sus propios intentos
        elif hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)

        # Filtros
        quiz_id = self.request.query_params.get('quiz')
        if quiz_id:
            queryset = queryset.filter(quiz_id=quiz_id)

        student_id = self.request.query_params.get('student')
        if student_id and hasattr(user, 'teacher_profile'):
            queryset = queryset.filter(student_id=student_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.select_related(
            'quiz__subject_group',
            'student__user',
            'graded_by__user'
        ).prefetch_related('answers__question__options')

    @action(detail=False, methods=['post'])
    def start(self, request):
        """
        Iniciar un nuevo intento de quiz
        """
        quiz_id = request.data.get('quiz_id')

        if not quiz_id:
            return Response(
                {'error': 'quiz_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response(
                {'error': 'Quiz no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que el quiz esté disponible
        if not quiz.is_available:
            return Response(
                {'error': 'El quiz no está disponible actualmente'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar que el usuario sea estudiante
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {'error': 'Solo estudiantes pueden tomar quizzes'},
                status=status.HTTP_403_FORBIDDEN
            )

        student = request.user.student_profile

        # Verificar número de intentos
        attempts_count = QuizAttempt.objects.filter(
            quiz=quiz,
            student=student
        ).count()

        if attempts_count >= quiz.max_attempts:
            return Response(
                {'error': f'Has alcanzado el máximo de intentos permitidos ({quiz.max_attempts})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar si hay un intento en progreso
        in_progress = QuizAttempt.objects.filter(
            quiz=quiz,
            student=student,
            status='in_progress'
        ).first()

        if in_progress:
            from .serializers import QuizAttemptDetailSerializer
            serializer = QuizAttemptDetailSerializer(in_progress, context={'request': request})
            return Response(serializer.data)

        # Crear nuevo intento
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            attempt_number=attempts_count + 1,
            status='in_progress'
        )

        from .serializers import QuizAttemptDetailSerializer
        serializer = QuizAttemptDetailSerializer(attempt, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Enviar respuestas de un quiz
        """
        attempt = self.get_object()

        # Verificar que el intento pertenece al estudiante
        if hasattr(request.user, 'student_profile'):
            if attempt.student != request.user.student_profile:
                return Response(
                    {'error': 'No tienes permiso para enviar este intento'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Verificar que el intento esté en progreso
        if attempt.status != 'in_progress':
            return Response(
                {'error': 'Este intento ya fue enviado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .serializers import QuizSubmissionSerializer
        serializer = QuizSubmissionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        answers_data = serializer.validated_data['answers']

        # Guardar respuestas
        for answer_data in answers_data:
            question_id = answer_data['question_id']

            try:
                question = Question.objects.get(id=question_id, quiz=attempt.quiz)
            except Question.DoesNotExist:
                continue

            # Crear o actualizar respuesta
            answer, created = QuizAnswer.objects.get_or_create(
                attempt=attempt,
                question=question
            )

            if 'selected_option_id' in answer_data:
                try:
                    option = QuestionOption.objects.get(
                        id=answer_data['selected_option_id'],
                        question=question
                    )
                    answer.selected_option = option
                except QuestionOption.DoesNotExist:
                    pass

            if 'text_answer' in answer_data:
                answer.text_answer = answer_data['text_answer']

            # Verificar respuesta automáticamente si es posible
            answer.check_answer()

        # Marcar intento como enviado
        attempt.status = 'submitted'
        attempt.submitted_at = timezone.now()
        attempt.save()

        # Calcular puntaje
        attempt.calculate_score()

        from .serializers import QuizAttemptDetailSerializer
        serializer = QuizAttemptDetailSerializer(attempt, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def grade_manually(self, request, pk=None):
        """
        Calificar manualmente preguntas de ensayo
        """
        attempt = self.get_object()

        # Solo profesores pueden calificar
        if not hasattr(request.user, 'teacher_profile'):
            return Response(
                {'error': 'Solo profesores pueden calificar'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Calificar respuestas individuales
        manual_grades = request.data.get('grades', [])

        for grade_data in manual_grades:
            answer_id = grade_data.get('answer_id')
            points_earned = grade_data.get('points_earned')
            teacher_feedback = grade_data.get('teacher_feedback', '')

            try:
                answer = QuizAnswer.objects.get(
                    id=answer_id,
                    attempt=attempt
                )

                answer.points_earned = points_earned
                answer.teacher_feedback = teacher_feedback
                answer.is_correct = (
                    points_earned >= answer.question.points * 0.5
                ) if points_earned is not None else None
                answer.save()
            except QuizAnswer.DoesNotExist:
                continue

        # Actualizar feedback general del intento
        if 'teacher_feedback' in request.data:
            attempt.teacher_feedback = request.data['teacher_feedback']

        attempt.graded_by = request.user.teacher_profile
        attempt.calculate_score()

        from .serializers import QuizAttemptDetailSerializer
        serializer = QuizAttemptDetailSerializer(attempt, context={'request': request})
        return Response(serializer.data)
