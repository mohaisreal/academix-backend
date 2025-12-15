from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from users.models import User
import json

User = get_user_model()


class FormTemplate(models.Model):
    """
    Template for dynamic forms - can be used for enrollment, applications, surveys, etc.
    """
    url_slug = models.SlugField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    requires_authentication = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forms',
        limit_choices_to={'role': 'admin'}
    )

    # Payment configuration
    requires_payment = models.BooleanField(default=False)
    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Base payment amount in currency"
    )
    stripe_product_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)

    # Notification settings
    send_confirmation_email = models.BooleanField(default=True)
    notification_emails = models.JSONField(
        default=list,
        blank=True,
        help_text="List of email addresses to notify on submission"
    )

    # Draft settings
    allow_drafts = models.BooleanField(default=True)
    draft_expiration_days = models.IntegerField(default=30, validators=[MinValueValidator(1)])

    # Submission limits
    max_submissions_per_user = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        help_text="Leave blank for unlimited submissions"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'form_templates'
        verbose_name = 'Form Template'
        verbose_name_plural = 'Form Templates'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['url_slug']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.title} ({self.url_slug})"

    def save(self, *args, **kwargs):
        if not self.url_slug:
            self.url_slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_total_phases(self):
        return self.phases.count()

    def get_submission_count(self):
        return self.submissions.filter(status='completed').count()


class FormPhase(models.Model):
    """
    Phases/Steps of a form - allows multi-step forms
    """
    form_template = models.ForeignKey(
        FormTemplate,
        on_delete=models.CASCADE,
        related_name='phases'
    )
    order = models.IntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    # Navigation settings
    can_skip = models.BooleanField(default=False)
    show_in_progress_bar = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'form_phases'
        verbose_name = 'Form Phase'
        verbose_name_plural = 'Form Phases'
        ordering = ['form_template', 'order']
        unique_together = [['form_template', 'order']]
        indexes = [
            models.Index(fields=['form_template', 'order']),
        ]

    def __str__(self):
        return f"{self.form_template.title} - Phase {self.order}: {self.title}"

    def get_field_count(self):
        return self.fields.count()


class FormField(models.Model):
    """
    Individual fields within a form phase
    """
    FIELD_TYPE_CHOICES = [
        ('text_short', 'Short Text'),
        ('text_long', 'Long Text (Textarea)'),
        ('email', 'Email'),
        ('phone', 'Phone Number'),
        ('number', 'Number'),
        ('date_picker', 'Date Picker'),
        ('single_choice', 'Single Choice (Radio)'),
        ('multiple_choice', 'Multiple Choice (Checkbox)'),
        ('dropdown', 'Dropdown Select'),
        ('autocomplete', 'Autocomplete'),
        ('checkbox', 'Single Checkbox'),
        ('file_upload', 'File Upload'),
        ('course_selector', 'Course Selector'),
        ('schedule_viewer', 'Schedule Viewer'),
        ('accordion_section', 'Accordion Section'),
        ('divider', 'Divider'),
        ('info_text', 'Information Text'),
        ('payment_module', 'Payment Module'),
    ]

    phase = models.ForeignKey(
        FormPhase,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    field_type = models.CharField(max_length=30, choices=FIELD_TYPE_CHOICES)
    order = models.IntegerField(validators=[MinValueValidator(1)])

    # Field configuration
    label = models.CharField(max_length=300)
    placeholder = models.CharField(max_length=200, blank=True, null=True)
    help_text = models.TextField(blank=True, null=True)
    default_value = models.TextField(blank=True, null=True)

    # Validation
    is_required = models.BooleanField(default=False)
    validation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="""JSON object with validation rules. Examples:
        - {"min_length": 5, "max_length": 100}
        - {"pattern": "^[A-Z0-9]+$", "pattern_message": "Only uppercase letters and numbers"}
        - {"min": 0, "max": 100}
        - {"allowed_extensions": ["pdf", "jpg", "png"], "max_size_mb": 5}
        - {"min_date": "2024-01-01", "max_date": "2024-12-31"}
        """
    )

    # Options for choice fields
    options = models.JSONField(
        default=list,
        blank=True,
        help_text="""JSON array for choice fields. Examples:
        - [{"value": "opt1", "label": "Option 1"}, {"value": "opt2", "label": "Option 2"}]
        - For course_selector: fetched dynamically from API
        """
    )

    # Conditional logic
    conditional_logic = models.JSONField(
        default=dict,
        blank=True,
        help_text="""JSON object for conditional display. Example:
        {"show_if": {"field_id": 123, "operator": "equals", "value": "yes"}}
        {"show_if": {"field_id": 124, "operator": "contains", "value": ["option1", "option2"]}}
        """
    )

    # Multiple choice settings
    max_selections = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        help_text="For multiple_choice fields - limit number of selections"
    )

    # File upload settings
    allowed_file_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of allowed file extensions, e.g., ['pdf', 'jpg', 'png']"
    )
    max_file_size_mb = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    # Course selector specific
    filter_by_career = models.BooleanField(default=False)
    check_prerequisites = models.BooleanField(default=True)
    check_schedule_conflicts = models.BooleanField(default=True)
    max_credits = models.IntegerField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'form_fields'
        verbose_name = 'Form Field'
        verbose_name_plural = 'Form Fields'
        ordering = ['phase', 'order']
        unique_together = [['phase', 'order']]
        indexes = [
            models.Index(fields=['phase', 'order']),
        ]

    def __str__(self):
        return f"{self.phase.title} - {self.label} ({self.get_field_type_display()})"


class FormSubmission(models.Model):
    """
    Individual form submissions from users
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('pending_payment', 'Pending Payment'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    form_template = models.ForeignKey(
        FormTemplate,
        on_delete=models.CASCADE,
        related_name='submissions'
    )

    # User can be null for non-authenticated forms
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='form_submissions',
        blank=True,
        null=True
    )
    guest_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email for non-authenticated users"
    )

    # Submission state
    current_phase = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Form data - stored as JSON
    submission_data = models.JSONField(
        default=dict,
        help_text="""JSON object storing all form field values:
        {
            "phase_1": {"field_1": "value", "field_2": "value"},
            "phase_2": {"field_3": "value"},
            ...
        }
        """
    )

    # Files uploaded
    uploaded_files = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object mapping field IDs to file paths"
    )

    # Payment information
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='not_required'
    )
    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True, null=True)
    stripe_checkout_session_id = models.CharField(max_length=200, blank=True, null=True)
    payment_date = models.DateTimeField(blank=True, null=True)

    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'form_submissions'
        verbose_name = 'Form Submission'
        verbose_name_plural = 'Form Submissions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['form_template', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'payment_status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        user_identifier = self.user.get_full_name() if self.user else self.guest_email
        return f"{self.form_template.title} - {user_identifier} ({self.get_status_display()})"

    def get_completion_percentage(self):
        """Calculate completion percentage based on filled fields"""
        if not self.submission_data:
            return 0

        total_fields = FormField.objects.filter(
            phase__form_template=self.form_template,
            is_required=True
        ).count()

        if total_fields == 0:
            return 100

        filled_fields = 0
        for phase_data in self.submission_data.values():
            filled_fields += len([v for v in phase_data.values() if v])

        return min(int((filled_fields / total_fields) * 100), 100)

    def get_submitter_email(self):
        """Get the email of the submitter"""
        if self.user:
            return self.user.email
        return self.guest_email

    def mark_as_completed(self):
        """Mark submission as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class FormSubmissionFile(models.Model):
    """
    Uploaded files associated with form submissions
    """
    submission = models.ForeignKey(
        FormSubmission,
        on_delete=models.CASCADE,
        related_name='files'
    )
    field = models.ForeignKey(
        FormField,
        on_delete=models.CASCADE,
        related_name='uploaded_files'
    )
    file = models.FileField(upload_to='form_submissions/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    content_type = models.CharField(max_length=100)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'form_submission_files'
        verbose_name = 'Form Submission File'
        verbose_name_plural = 'Form Submission Files'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.submission} - {self.original_filename}"

    def get_file_size_display(self):
        """Return human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
