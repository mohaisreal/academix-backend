from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import User, Student, Teacher, TeacherQualifiedSubject, TeacherQualifiedCareer
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    StudentSerializer, StudentCreateSerializer, TeacherSerializer,
    TeacherCreateSerializer, PasswordChangeSerializer,
    TeacherQualifiedSubjectSerializer, TeacherQualifiedCareerSerializer
)
from authentication.permissions import IsStudentUser, IsTeacherUser, IsAdminUser


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users
    Only admins can create, update, or delete users
    All authenticated users can view users (for dropdowns, etc.)
    """
    queryset = User.objects.all().select_related('student_profile', 'teacher_profile')
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination for users list

    def get_permissions(self):
        """
        Set permissions based on action
        - list, retrieve: Any authenticated user
        - create, update, partial_update, destroy: Admin only
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role', None)

        if role:
            queryset = queryset.filter(role=role)

        return queryset

    def destroy(self, request, *args, **kwargs):
        """
        Delete user
        """
        instance = self.get_object()

        # Don't allow a user to delete themselves
        if instance.id == request.user.id:
            return Response(
                {'detail': 'No puedes eliminar tu propio usuario.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get user statistics
        """
        total = User.objects.count()
        students = User.objects.filter(role='student').count()
        teachers = User.objects.filter(role='teacher').count()
        admins = User.objects.filter(role='admin').count()

        return Response({
            'total': total,
            'students': students,
            'teachers': teachers,
            'admins': admins
        })


class StudentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing students
    """
    queryset = Student.objects.all().select_related('user')
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination for students list

    def get_serializer_class(self):
        if self.action == 'create':
            return StudentCreateSerializer
        return StudentSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticated, IsAdminUser | IsStudentUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status', None)
        career_id = self.request.query_params.get('career', None)
        search = self.request.query_params.get('search', None)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if career_id:
            from enrollment.models import CareerEnrollment
            enrolled_students = CareerEnrollment.objects.filter(
                career_id=career_id,
                status='active'
            ).values_list('student_id', flat=True)
            queryset = queryset.filter(id__in=enrolled_students)

        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(student_id__icontains=search)
            )

        return queryset.order_by('user__last_name', 'user__first_name')

    def update(self, request, *args, **kwargs):
        """Update student profile"""
        instance = self.get_object()

        # If it's a student updating their own profile
        if hasattr(request.user, 'student_profile') and request.user.student_profile == instance:
            # Only allow updating certain fields
            allowed_fields = ['status'] if request.user.role == 'admin' else []
            for key in list(request.data.keys()):
                if key not in allowed_fields:
                    request.data.pop(key)

        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def academic_record(self, request, pk=None):
        """Get student's complete academic record"""
        student = self.get_object()
        record = student.get_academic_record()

        return Response({
            'student_id': student.id,
            'student_name': student.user.get_full_name(),
            'student_code': student.student_id,
            **record
        })

    @action(detail=True, methods=['get'])
    def current_subjects(self, request, pk=None):
        """Get student's current enrolled subjects"""
        student = self.get_object()
        current_subjects = student.get_current_subjects()

        subjects_data = []
        for enrollment in current_subjects:
            subjects_data.append({
                'enrollment_id': enrollment.id,
                'subject_code': enrollment.subject_group.subject.code,
                'subject_name': enrollment.subject_group.subject.name,
                'credits': enrollment.subject_group.subject.credits,
                'group_code': enrollment.subject_group.code,
                'academic_period': enrollment.subject_group.academic_period.name,
                'enrollment_date': enrollment.enrollment_date,
                'status': enrollment.status
            })

        return Response({
            'student': {
                'id': student.id,
                'name': student.user.get_full_name(),
                'student_id': student.student_id
            },
            'current_subjects': subjects_data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get students statistics"""
        total = Student.objects.count()
        active = Student.objects.filter(status='active').count()
        inactive = Student.objects.filter(status='inactive').count()
        graduated = Student.objects.filter(status='graduated').count()
        suspended = Student.objects.filter(status='suspended').count()

        return Response({
            'total': total,
            'active': active,
            'inactive': inactive,
            'graduated': graduated,
            'suspended': suspended
        })

    @action(detail=False, methods=['get'])
    def my_teachers(self, request):
        """
        Obtener profesores del estudiante actual basado en sus inscripciones
        GET /api/users/students/my_teachers/
        """
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {'error': 'Solo disponible para estudiantes'},
                status=status.HTTP_403_FORBIDDEN
            )

        student = request.user.student_profile

        # Obtener inscripciones activas del estudiante
        from enrollment.models import SubjectEnrollment
        from schedules.models import TeacherAssignment

        enrollments = SubjectEnrollment.objects.filter(
            student=student,
            status='enrolled'
        ).select_related('subject_group__subject', 'subject_group__academic_period')

        # Obtener profesores únicos
        teachers_dict = {}

        for enrollment in enrollments:
            # Obtener el profesor principal del grupo
            teacher_assignment = TeacherAssignment.objects.filter(
                subject_group=enrollment.subject_group,
                is_main_teacher=True,
                status='active'
            ).select_related('teacher__user').first()

            if teacher_assignment:
                teacher = teacher_assignment.teacher
                teacher_id = teacher.id

                if teacher_id not in teachers_dict:
                    teachers_dict[teacher_id] = {
                        'id': teacher.id,
                        'employee_id': teacher.employee_id,
                        'department': teacher.department or 'No especificado',
                        'user': {
                            'first_name': teacher.user.first_name,
                            'last_name': teacher.user.last_name,
                            'email': teacher.user.email,
                        },
                        'subjects': []
                    }

                # Agregar asignatura a la lista del profesor
                teachers_dict[teacher_id]['subjects'].append({
                    'subject_code': enrollment.subject_group.subject.code,
                    'subject_name': enrollment.subject_group.subject.name,
                    'group_code': enrollment.subject_group.code,
                    'academic_period': enrollment.subject_group.academic_period.name
                })

        # Convertir a lista
        teachers_list = list(teachers_dict.values())

        return Response(teachers_list)

    @action(detail=True, methods=['get', 'post'], url_path='career-enrollments')
    def career_enrollments(self, request, pk=None):
        """
        GET: List career enrollments for the student
        POST: Add a career enrollment to the student
        """
        from enrollment.models import CareerEnrollment
        from enrollment.serializers import CareerEnrollmentSerializer

        student = self.get_object()

        if request.method == 'GET':
            enrollments = CareerEnrollment.objects.filter(student=student).select_related('career', 'study_plan')
            serializer = CareerEnrollmentSerializer(enrollments, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            data = request.data.copy()
            serializer = CareerEnrollmentSerializer(data=data)
            if serializer.is_valid():
                serializer.save(student=student)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='career-enrollments/(?P<enrollment_id>[^/.]+)')
    def remove_career_enrollment(self, request, pk=None, enrollment_id=None):
        """Remove a career enrollment from the student"""
        from enrollment.models import CareerEnrollment

        student = self.get_object()
        try:
            enrollment = CareerEnrollment.objects.get(id=enrollment_id, student=student)
            enrollment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CareerEnrollment.DoesNotExist:
            return Response(
                {'detail': 'Matrícula de carrera no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['patch'], url_path='career-enrollments/(?P<enrollment_id>[^/.]+)/status')
    def update_career_enrollment_status(self, request, pk=None, enrollment_id=None):
        """Update the status of a career enrollment"""
        from enrollment.models import CareerEnrollment
        from enrollment.serializers import CareerEnrollmentSerializer

        student = self.get_object()
        try:
            enrollment = CareerEnrollment.objects.get(id=enrollment_id, student=student)
            new_status = request.data.get('status')

            if new_status not in ['active', 'completed', 'dropped', 'suspended']:
                return Response(
                    {'detail': 'Estado inválido'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            enrollment.status = new_status
            enrollment.save()

            serializer = CareerEnrollmentSerializer(enrollment)
            return Response(serializer.data)
        except CareerEnrollment.DoesNotExist:
            return Response(
                {'detail': 'Matrícula de carrera no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )


class TeacherViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing teachers
    """
    queryset = Teacher.objects.all().select_related('user')
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination for teachers list

    def get_serializer_class(self):
        if self.action == 'create':
            return TeacherCreateSerializer
        return TeacherSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticated, IsAdminUser | IsTeacherUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status', None)
        department = self.request.query_params.get('department', None)
        search = self.request.query_params.get('search', None)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if department:
            queryset = queryset.filter(department__icontains=department)

        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(department__icontains=search)
            )

        return queryset.order_by('user__last_name', 'user__first_name')

    def update(self, request, *args, **kwargs):
        """Update teacher profile"""
        instance = self.get_object()

        # If it's a teacher updating their own profile
        if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile == instance:
            # Only allow updating certain fields
            allowed_fields = ['department', 'specialization'] if request.user.role == 'admin' else []
            for key in list(request.data.keys()):
                if key not in allowed_fields:
                    request.data.pop(key)

        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def assignments(self, request, pk=None):
        """Get teacher's current assignments"""
        from schedules.serializers import TeacherAssignmentDetailSerializer

        teacher = self.get_object()
        assignments = teacher.get_assigned_subjects()

        serializer = TeacherAssignmentDetailSerializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Get teacher's current schedule"""
        teacher = self.get_object()
        schedule = teacher.get_current_schedule()

        schedule_data = []
        for item in schedule:
            schedule_data.append({
                'id': item.id,
                'subject_code': item.subject_group.subject.code,
                'subject_name': item.subject_group.subject.name,
                'group_code': item.subject_group.code,
                'day_of_week': item.time_slot.get_day_of_week_display(),
                'start_time': item.time_slot.start_time,
                'end_time': item.time_slot.end_time,
                'classroom': item.classroom.name
            })

        return Response({
            'teacher': {
                'id': teacher.id,
                'name': teacher.user.get_full_name(),
                'employee_id': teacher.employee_id
            },
            'schedule': schedule_data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get teachers statistics"""
        total = Teacher.objects.count()
        active = Teacher.objects.filter(status='active').count()
        inactive = Teacher.objects.filter(status='inactive').count()
        on_leave = Teacher.objects.filter(status='on_leave').count()

        # Get department stats
        from django.db.models import Count
        departments = Teacher.objects.values('department').annotate(
            count=Count('id')
        ).exclude(department__isnull=True).exclude(department='')

        return Response({
            'total': total,
            'active': active,
            'inactive': inactive,
            'on_leave': on_leave,
            'by_department': list(departments)
        })

    @action(detail=True, methods=['get', 'post'], url_path='qualified-subjects')
    def qualified_subjects(self, request, pk=None):
        """
        GET: List qualified subjects for the teacher
        POST: Add an individual subject qualification to the teacher
        """
        teacher = self.get_object()

        if request.method == 'GET':
            qualified = teacher.qualified_subjects.all()
            serializer = TeacherQualifiedSubjectSerializer(qualified, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Don't allow teacher field to be set from request data
            data = request.data.copy()
            serializer = TeacherQualifiedSubjectSerializer(data=data)
            if serializer.is_valid():
                serializer.save(teacher=teacher)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='qualified-subjects/(?P<subject_id>[^/.]+)')
    def remove_qualified_subject(self, request, pk=None, subject_id=None):
        """Remove a subject from the teacher's qualifications"""
        teacher = self.get_object()
        try:
            qualification = teacher.qualified_subjects.get(subject_id=subject_id)
            qualification.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TeacherQualifiedSubject.DoesNotExist:
            return Response(
                {'detail': 'Asignatura no encontrada en las calificaciones'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get', 'post'], url_path='qualified-careers')
    def qualified_careers(self, request, pk=None):
        """
        GET: List qualified careers for the teacher
        POST: Add a career qualification to the teacher (all subjects in the career)
        """
        teacher = self.get_object()

        if request.method == 'GET':
            qualified = teacher.qualified_careers.all()
            serializer = TeacherQualifiedCareerSerializer(qualified, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Don't allow teacher field to be set from request data
            data = request.data.copy()
            print(f"DEBUG - Received data for qualified-careers: {data}")
            serializer = TeacherQualifiedCareerSerializer(data=data)
            if serializer.is_valid():
                serializer.save(teacher=teacher)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            print(f"DEBUG - Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='qualified-careers/(?P<career_id>[^/.]+)')
    def remove_qualified_career(self, request, pk=None, career_id=None):
        """Remove a career from the teacher's qualifications"""
        teacher = self.get_object()
        try:
            qualification = teacher.qualified_careers.get(career_id=career_id)
            qualification.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TeacherQualifiedCareer.DoesNotExist:
            return Response(
                {'detail': 'Carrera no encontrada en las calificaciones'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'], url_path='all-qualified-subjects')
    def all_qualified_subjects(self, request, pk=None):
        """Get all subjects the teacher can teach (individual + from careers)"""
        teacher = self.get_object()
        all_subjects = teacher.get_all_qualified_subjects()

        # Get individual subject IDs to mark source
        individual_subject_ids = set(teacher.qualified_subjects.values_list('subject_id', flat=True))

        subjects_data = [{
            'id': subject.id,
            'code': subject.code,
            'name': subject.name,
            'credits': subject.credits,
            'type': subject.type,
            'source': 'individual' if subject.id in individual_subject_ids else 'career'
        } for subject in all_subjects]

        return Response(subjects_data)


class PasswordChangeView(views.APIView):
    """
    View for changing user password
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Contraseña cambiada exitosamente'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(views.APIView):
    """
    View for getting current user profile
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'phone': user.phone,
            'address': user.address,
            'date_of_birth': user.date_of_birth
        }

        if user.role == 'student' and hasattr(user, 'student_profile'):
            data.update({
                'student_id': user.student_profile.student_id,
                'enrollment_date': user.student_profile.enrollment_date,
                'status': user.student_profile.status
            })
        elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            data.update({
                'employee_id': user.teacher_profile.employee_id,
                'department': user.teacher_profile.department,
                'specialization': user.teacher_profile.specialization,
                'hire_date': user.teacher_profile.hire_date,
                'status': user.teacher_profile.status
            })

        return Response(data)


class AdminDashboardStatsView(views.APIView):
    """
    View for getting admin dashboard statistics
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from enrollment.models import CareerEnrollment, SubjectEnrollment, SubjectGroup
        from academic.models import Career
        from grades.models import FinalGrade

        # Basic counts
        total_students = Student.objects.filter(status='active').count()
        total_teachers = Teacher.objects.filter(status='active').count()

        # Active subject groups (current academic period)
        active_subject_groups = SubjectGroup.objects.filter(
            academic_period__is_active=True
        ).count()

        # Calculate approval rate based on final grades
        final_grades = FinalGrade.objects.filter(
            final_score__isnull=False,
            is_published=True
        )

        if final_grades.exists():
            passed_grades = final_grades.filter(status='passed').count()
            total_final_grades = final_grades.count()
            approval_rate = (passed_grades / total_final_grades * 100) if total_final_grades > 0 else 0
        else:
            approval_rate = 0

        # New registrations this week
        one_week_ago = timezone.now() - timedelta(days=7)
        new_students_this_week = Student.objects.filter(
            enrollment_date__gte=one_week_ago
        ).count()
        new_teachers_this_week = Teacher.objects.filter(
            hire_date__gte=one_week_ago
        ).count()
        new_registrations = new_students_this_week + new_teachers_this_week

        # Active enrollments in current period
        active_enrollments = SubjectEnrollment.objects.filter(
            status='enrolled',
            subject_group__academic_period__is_active=True
        ).count()

        # Overall average grade from published final grades
        average_grade = FinalGrade.objects.filter(
            final_score__isnull=False,
            is_published=True
        ).aggregate(avg=Avg('final_score'))['avg'] or 0

        # Recent activities (limit to 3)
        recent_activities = []

        # Recent teachers
        recent_teachers = Teacher.objects.select_related('user').order_by('-hire_date')[:2]
        for teacher in recent_teachers:
            time_diff = timezone.now() - timezone.make_aware(timezone.datetime.combine(teacher.hire_date, timezone.datetime.min.time())) if teacher.hire_date else timedelta(0)
            hours_ago = int(time_diff.total_seconds() / 3600)

            recent_activities.append({
                'type': 'teacher_registered',
                'title': 'Nuevo profesor registrado',
                'description': f'{teacher.user.get_full_name()} - {teacher.department or "Sin departamento"}',
                'time': f'Hace {hours_ago} horas' if hours_ago < 24 else f'Hace {int(hours_ago/24)} días'
            })

        # Recent subject groups
        recent_subject_groups = SubjectGroup.objects.select_related(
            'subject', 'academic_period'
        ).order_by('-created_at')[:2] if hasattr(SubjectGroup, 'created_at') else []

        for group in recent_subject_groups:
            if hasattr(group, 'created_at'):
                time_diff = timezone.now() - group.created_at
                hours_ago = int(time_diff.total_seconds() / 3600)

                recent_activities.append({
                    'type': 'subject_created',
                    'title': 'Nueva asignatura creada',
                    'description': f'{group.subject.name} - {group.subject.credits} créditos',
                    'time': f'Hace {hours_ago} horas' if hours_ago < 24 else f'Hace {int(hours_ago/24)} días'
                })

        # Career/Department statistics
        career_stats = []
        careers = Career.objects.all()

        for career in careers:
            # Count active students in this career
            career_students = CareerEnrollment.objects.filter(
                career=career,
                status='active'
            ).count()

            # Count teachers in this career's department (if applicable)
            # For now, we'll count all teachers since there's no direct career-teacher relationship
            career_teachers = Teacher.objects.filter(
                status='active',
                department=career.name  # This assumes department matches career name
            ).count()

            # Calculate enrollment percentage
            enrollment_percentage = (career_students / total_students * 100) if total_students > 0 else 0

            career_stats.append({
                'name': career.name,
                'students': career_students,
                'teachers': career_teachers,
                'enrollment_percentage': round(enrollment_percentage, 1)
            })

        # Previous year comparison (mock data for percentage changes)
        # In a real scenario, you would query historical data
        student_growth = 12.0  # This would be calculated from historical data
        teacher_growth = 3.0

        return Response({
            'summary': {
                'total_students': total_students,
                'total_teachers': total_teachers,
                'active_subjects': active_subject_groups,
                'approval_rate': round(approval_rate, 1),
                'student_growth_percentage': student_growth,
                'teacher_growth_count': new_teachers_this_week
            },
            'statistics': {
                'new_registrations': new_registrations,
                'new_registrations_growth': 18,  # Mock data
                'active_enrollments': active_enrollments,
                'enrollment_percentage': round((active_enrollments / total_students * 100) if total_students > 0 else 0, 1),
                'average_grade': round(average_grade, 1),
                'grade_improvement': 0.4  # Mock data
            },
            'recent_activities': recent_activities[:3],  # Limit to 3 most recent
            'career_stats': career_stats[:3],  # Top 3 careers
            'system_alert': {
                'message': 'Todos los sistemas operando normalmente.',
                'type': 'info'
            }
        })
