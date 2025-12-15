from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Career(models.Model):
    """
    Model for careers/degrees
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    duration_years = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    total_credits = models.IntegerField(validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'careers'
        verbose_name = 'Career'
        verbose_name_plural = 'Careers'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Subject(models.Model):
    """
    Model for subjects/courses
    """
    SUBJECT_TYPE_CHOICES = [
        ('mandatory', 'Obligatoria'),
        ('elective', 'Optativa'),
        ('core', 'Troncal'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    credits = models.IntegerField(validators=[MinValueValidator(1)])
    type = models.CharField(max_length=20, choices=SUBJECT_TYPE_CHOICES, default='mandatory')
    course_year = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    semester = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subjects'
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering = ['course_year', 'semester', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class StudyPlan(models.Model):
    """
    Model for study plans/curricula
    """
    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name='study_plans')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    start_year = models.IntegerField()
    end_year = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'study_plans'
        verbose_name = 'Study Plan'
        verbose_name_plural = 'Study Plans'
        ordering = ['-start_year']

    def __str__(self):
        return f"{self.career.name} - {self.name} ({self.start_year})"


class StudyPlanSubject(models.Model):
    """
    Relationship between study plans and subjects
    """
    study_plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name='subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='study_plans')
    prerequisites = models.ManyToManyField(Subject, blank=True, related_name='is_prerequisite_of')

    class Meta:
        db_table = 'study_plan_subjects'
        verbose_name = 'Study Plan Subject'
        verbose_name_plural = 'Study Plan Subjects'
        unique_together = [['study_plan', 'subject']]

    def __str__(self):
        return f"{self.study_plan.name} - {self.subject.name}"


class AcademicPeriod(models.Model):
    """
    Model for academic periods/semesters
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    enrollment_start = models.DateField()
    enrollment_end = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'academic_periods'
        verbose_name = 'Academic Period'
        verbose_name_plural = 'Academic Periods'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"


class Classroom(models.Model):
    """
    Model for classrooms
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100, blank=True, null=True)
    floor = models.IntegerField(blank=True, null=True)
    capacity = models.IntegerField(validators=[MinValueValidator(1)])
    has_projector = models.BooleanField(default=False)
    has_computers = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'classrooms'
        verbose_name = 'Classroom'
        verbose_name_plural = 'Classrooms'
        ordering = ['building', 'floor', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"
