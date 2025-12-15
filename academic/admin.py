from django.contrib import admin
from .models import Career, Subject, StudyPlan, StudyPlanSubject, AcademicPeriod, Classroom

@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'duration_years', 'total_credits', 'is_active']
    list_filter = ['is_active', 'duration_years']
    search_fields = ['code', 'name']
    ordering = ['name']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'type', 'credits', 'course_year', 'semester', 'is_active']
    list_filter = ['type', 'course_year', 'semester', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['course_year', 'semester', 'name']

@admin.register(StudyPlan)
class StudyPlanAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'career', 'start_year', 'end_year', 'is_active']
    list_filter = ['career', 'is_active', 'start_year']
    search_fields = ['code', 'name', 'career__name']
    ordering = ['-start_year']

@admin.register(StudyPlanSubject)
class StudyPlanSubjectAdmin(admin.ModelAdmin):
    list_display = ['study_plan', 'subject']
    list_filter = ['study_plan__career']
    search_fields = ['study_plan__name', 'subject__name', 'subject__code']
    filter_horizontal = ['prerequisites']

@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'start_date', 'end_date', 'is_active']
    list_filter = ['is_active', 'start_date']
    search_fields = ['code', 'name']
    ordering = ['-start_date']

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'building', 'floor', 'capacity', 'has_projector', 'has_computers', 'is_active']
    list_filter = ['building', 'has_projector', 'has_computers', 'is_active']
    search_fields = ['code', 'name', 'building']
    ordering = ['building', 'floor', 'code']
