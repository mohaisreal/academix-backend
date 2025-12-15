from django.contrib import admin
from .models import User, Student, Teacher, TeacherQualifiedSubject, TeacherQualifiedCareer

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-created_at']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'user', 'status', 'enrollment_date']
    list_filter = ['status', 'enrollment_date']
    search_fields = ['student_id', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    ordering = ['-enrollment_date']

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'user', 'department', 'status', 'hire_date']
    list_filter = ['status', 'department', 'hire_date']
    search_fields = ['employee_id', 'user__username', 'user__email', 'user__first_name', 'user__last_name', 'department']
    ordering = ['-hire_date']

@admin.register(TeacherQualifiedSubject)
class TeacherQualifiedSubjectAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'qualification_date']
    list_filter = ['qualification_date']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'subject__name', 'subject__code']
    ordering = ['-qualification_date']
    autocomplete_fields = ['teacher', 'subject']

@admin.register(TeacherQualifiedCareer)
class TeacherQualifiedCareerAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'career', 'qualification_date']
    list_filter = ['qualification_date']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'career__name', 'career__code']
    ordering = ['-qualification_date']
    autocomplete_fields = ['teacher', 'career']
