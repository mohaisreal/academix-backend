from django.contrib import admin
from .models import CareerEnrollment, SubjectGroup, SubjectEnrollment, WaitingList

@admin.register(CareerEnrollment)
class CareerEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'career', 'study_plan', 'status', 'enrollment_date']
    list_filter = ['status', 'career', 'enrollment_date']
    search_fields = ['student__student_id', 'student__user__username', 'career__name']
    ordering = ['-enrollment_date']

@admin.register(SubjectGroup)
class SubjectGroupAdmin(admin.ModelAdmin):
    list_display = ['subject', 'code', 'academic_period', 'current_enrollment', 'max_capacity', 'is_active']
    list_filter = ['academic_period', 'is_active', 'subject']
    search_fields = ['code', 'subject__code', 'subject__name']
    ordering = ['subject', 'code']

@admin.register(SubjectEnrollment)
class SubjectEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject_group', 'career_enrollment', 'status', 'enrollment_date']
    list_filter = ['status', 'enrollment_date', 'subject_group__academic_period']
    search_fields = ['student__student_id', 'student__user__username', 'subject_group__subject__name']
    ordering = ['-enrollment_date']

@admin.register(WaitingList)
class WaitingListAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject_group', 'position', 'status', 'created_at']
    list_filter = ['status', 'subject_group__academic_period']
    search_fields = ['student__student_id', 'student__user__username', 'subject_group__subject__name']
    ordering = ['subject_group', 'position']
