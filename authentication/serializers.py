from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.models import Student, Teacher

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Basic serializer for User model
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'role', 'phone', 'address', 'date_of_birth', 'profile_image',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for new user registration
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    # Optional fields for creating extended profiles
    student_id = serializers.CharField(required=False, allow_blank=True)
    employee_id = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)
    specialization = serializers.CharField(required=False, allow_blank=True)
    hire_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name',
                  'last_name', 'role', 'phone', 'address', 'date_of_birth',
                  'student_id', 'employee_id', 'department', 'specialization', 'hire_date']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})

        # Validate fields based on role
        if attrs.get('role') == 'student' and not attrs.get('student_id'):
            raise serializers.ValidationError({"student_id": "El ID de estudiante es requerido para estudiantes."})

        if attrs.get('role') == 'teacher' and not attrs.get('employee_id'):
            raise serializers.ValidationError({"employee_id": "El ID de empleado es requerido para profesores."})

        return attrs

    def create(self, validated_data):
        # Extract fields that don't belong to User model
        validated_data.pop('password2')
        student_id = validated_data.pop('student_id', None)
        employee_id = validated_data.pop('employee_id', None)
        department = validated_data.pop('department', None)
        specialization = validated_data.pop('specialization', None)
        hire_date = validated_data.pop('hire_date', None)

        # Create user
        user = User.objects.create_user(**validated_data)

        # Create extended profile based on role
        if user.role == 'student' and student_id:
            Student.objects.create(
                user=user,
                student_id=student_id
            )
        elif user.role == 'teacher' and employee_id:
            Teacher.objects.create(
                user=user,
                employee_id=employee_id,
                department=department or '',
                specialization=specialization or '',
                hire_date=hire_date
            )

        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer to include additional user information in the token
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom fields to token
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.get_full_name()

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Add additional user information to response
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
        }

        return data


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Las contraseñas nuevas no coinciden."})
        return attrs


class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for student profile
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'user', 'student_id', 'enrollment_date', 'status']
        read_only_fields = ['id', 'enrollment_date']


class TeacherProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for teacher profile
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = Teacher
        fields = ['id', 'user', 'employee_id', 'department', 'specialization',
                  'hire_date', 'status']
        read_only_fields = ['id']
