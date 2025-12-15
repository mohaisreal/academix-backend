from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Student, Teacher, TeacherQualifiedSubject, TeacherQualifiedCareer


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    """
    student_id = serializers.CharField(source='student_profile.student_id', read_only=True, allow_null=True)
    employee_id = serializers.CharField(source='teacher_profile.employee_id', read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'address', 'date_of_birth', 'profile_image',
            'student_id', 'employee_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating users
    """
    password = serializers.CharField(write_only=True, required=True)
    student_id = serializers.CharField(required=False, allow_blank=True)
    employee_id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name',
            'role', 'phone', 'address', 'date_of_birth',
            'student_id', 'employee_id'
        ]

    def create(self, validated_data):
        student_id = validated_data.pop('student_id', None)
        employee_id = validated_data.pop('employee_id', None)
        password = validated_data.pop('password')

        # Create user
        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        # Create profile based on role
        if user.role == 'student' and student_id:
            Student.objects.create(
                user=user,
                student_id=student_id
            )
        elif user.role == 'teacher' and employee_id:
            from datetime import date
            Teacher.objects.create(
                user=user,
                employee_id=employee_id,
                hire_date=date.today()
            )

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating users
    """
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name',
            'phone', 'address', 'date_of_birth'
        ]


class StudentSerializer(serializers.ModelSerializer):
    """
    Serializer for Student model
    """
    user = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    career_enrollments = serializers.SerializerMethodField()
    current_academic_record = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'user', 'student_id', 'enrollment_date', 'status', 'status_display',
            'career_enrollments', 'current_academic_record'
        ]
        read_only_fields = ['enrollment_date']

    def get_career_enrollments(self, obj):
        from enrollment.models import CareerEnrollment
        enrollments = CareerEnrollment.objects.filter(student=obj, status='active')
        return [{
            'id': enrollment.id,
            'career_name': enrollment.career.name,
            'career_code': enrollment.career.code,
            'study_plan': enrollment.study_plan.name,
            'enrollment_date': enrollment.enrollment_date
        } for enrollment in enrollments]

    def get_current_academic_record(self, obj):
        record = obj.get_academic_record()
        return {
            'total_credits': record.get('total_credits', 0),
            'average_grade': record.get('average_grade'),
            'completion_rate': record.get('completion_rate', 0),
            'passed_subjects': record.get('passed_subjects', 0),
            'failed_subjects': record.get('failed_subjects', 0)
        }


class StudentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating students
    """
    user_data = serializers.DictField(write_only=True)
    career_id = serializers.IntegerField(write_only=True, required=False)
    study_plan_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Student
        fields = ['student_id', 'user_data', 'career_id', 'study_plan_id']

    def validate_user_data(self, value):
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f'Campo requerido: {field}')

        # Validate password
        try:
            validate_password(value['password'])
        except serializers.ValidationError as e:
            raise serializers.ValidationError({'password': e.messages})

        return value

    def create(self, validated_data):
        user_data = validated_data.pop('user_data')
        career_id = validated_data.pop('career_id', None)
        study_plan_id = validated_data.pop('study_plan_id', None)

        # Create user
        password = user_data.pop('password')
        user = User.objects.create_user(
            role='student',
            password=password,
            **user_data
        )

        # Create student
        student = Student.objects.create(user=user, **validated_data)

        # Create career enrollment if provided
        if career_id and study_plan_id:
            from enrollment.models import CareerEnrollment
            from academic.models import Career, StudyPlan

            try:
                career = Career.objects.get(id=career_id)
                study_plan = StudyPlan.objects.get(id=study_plan_id, career=career)

                CareerEnrollment.objects.create(
                    student=student,
                    career=career,
                    study_plan=study_plan
                )
            except (Career.DoesNotExist, StudyPlan.DoesNotExist):
                pass  # Ignore if not found

        return student


class TeacherQualifiedSubjectSerializer(serializers.ModelSerializer):
    """
    Serializer for TeacherQualifiedSubject model
    """
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = TeacherQualifiedSubject
        fields = ['id', 'teacher', 'subject', 'subject_code', 'subject_name', 'qualification_date', 'notes']
        read_only_fields = ['qualification_date', 'teacher']
        validators = []  # Disable unique_together validation at serializer level


class TeacherQualifiedCareerSerializer(serializers.ModelSerializer):
    """
    Serializer for TeacherQualifiedCareer model
    """
    career_code = serializers.CharField(source='career.code', read_only=True)
    career_name = serializers.CharField(source='career.name', read_only=True)

    class Meta:
        model = TeacherQualifiedCareer
        fields = ['id', 'teacher', 'career', 'career_code', 'career_name', 'qualification_date', 'notes']
        read_only_fields = ['qualification_date', 'teacher']
        validators = []  # Disable unique_together validation at serializer level


class TeacherSerializer(serializers.ModelSerializer):
    """
    Serializer for Teacher model
    """
    user = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_assignments = serializers.SerializerMethodField()
    current_schedule = serializers.SerializerMethodField()
    qualified_subjects_count = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            'id', 'user', 'employee_id', 'department', 'specialization',
            'hire_date', 'status', 'status_display', 'current_assignments',
            'current_schedule', 'qualified_subjects_count'
        ]

    def get_current_assignments(self, obj):
        from schedules.models import TeacherAssignment
        from academic.models import AcademicPeriod
        from datetime import date

        # Get current academic period
        today = date.today()
        current_period = AcademicPeriod.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()

        if not current_period:
            return []

        assignments = TeacherAssignment.objects.filter(
            teacher=obj,
            subject_group__academic_period=current_period,
            status='active'
        ).select_related('subject_group__subject')

        return [{
            'id': assignment.id,
            'subject_name': assignment.subject_group.subject.name,
            'subject_code': assignment.subject_group.subject.code,
            'group_code': assignment.subject_group.code,
            'is_main_teacher': assignment.is_main_teacher,
            'student_count': assignment.subject_group.current_enrollment
        } for assignment in assignments]

    def get_current_schedule(self, obj):
        from academic.models import AcademicPeriod
        from datetime import date

        # Get current academic period
        today = date.today()
        current_period = AcademicPeriod.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()

        if current_period:
            schedules = obj.get_current_schedule(current_period)
            return [{
                'id': schedule.id,
                'subject_name': schedule.subject_group.subject.name,
                'day_of_week': schedule.time_slot.get_day_of_week_display(),
                'start_time': schedule.time_slot.start_time,
                'end_time': schedule.time_slot.end_time,
                'classroom': schedule.classroom.name
            } for schedule in schedules]

        return []

    def get_qualified_subjects_count(self, obj):
        """
        Get the total count of qualified subjects.
        """
        try:
            return obj.get_all_qualified_subjects().count()
        except Exception:
            return 0


class TeacherCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating teachers
    """
    user_data = serializers.DictField(write_only=True)

    class Meta:
        model = Teacher
        fields = ['employee_id', 'department', 'specialization', 'hire_date', 'user_data']

    def validate_user_data(self, value):
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f'Campo requerido: {field}')

        # Validate password
        try:
            validate_password(value['password'])
        except serializers.ValidationError as e:
            raise serializers.ValidationError({'password': e.messages})

        return value

    def create(self, validated_data):
        user_data = validated_data.pop('user_data')

        # Create user
        password = user_data.pop('password')
        user = User.objects.create_user(
            role='teacher',
            password=password,
            **user_data
        )

        # Create teacher
        teacher = Teacher.objects.create(user=user, **validated_data)

        return teacher


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing password
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Contraseña actual incorrecta.")
        return value

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def save(self, **kwargs):
        password = self.validated_data['new_password']
        user = self.context['request'].user
        user.set_password(password)
        user.save()
        return user
