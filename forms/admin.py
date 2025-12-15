from django.contrib import admin
from django.utils.html import format_html
from .models import FormTemplate, FormPhase, FormField, FormSubmission, FormSubmissionFile


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 1
    fields = ('order', 'field_type', 'label', 'is_required', 'placeholder')
    ordering = ['order']


class FormPhaseInline(admin.StackedInline):
    model = FormPhase
    extra = 1
    fields = ('order', 'title', 'description', 'can_skip', 'show_in_progress_bar')
    ordering = ['order']
    show_change_link = True


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'url_slug',
        'is_active',
        'requires_authentication',
        'requires_payment',
        'submission_count',
        'created_at'
    )
    list_filter = ('is_active', 'requires_authentication', 'requires_payment', 'created_at')
    search_fields = ('title', 'url_slug', 'description')
    readonly_fields = ('created_at', 'updated_at', 'submission_count')
    prepopulated_fields = {'url_slug': ('title',)}

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'url_slug', 'description', 'is_active', 'created_by')
        }),
        ('Access Control', {
            'fields': ('requires_authentication', 'max_submissions_per_user')
        }),
        ('Payment Settings', {
            'fields': ('requires_payment', 'payment_amount', 'stripe_product_id', 'stripe_price_id'),
            'classes': ('collapse',)
        }),
        ('Draft Settings', {
            'fields': ('allow_drafts', 'draft_expiration_days'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('send_confirmation_email', 'notification_emails'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [FormPhaseInline]

    def submission_count(self, obj):
        count = obj.get_submission_count()
        return format_html('<strong>{}</strong>', count)
    submission_count.short_description = 'Submissions'


@admin.register(FormPhase)
class FormPhaseAdmin(admin.ModelAdmin):
    list_display = ('form_template', 'order', 'title', 'field_count', 'can_skip', 'show_in_progress_bar')
    list_filter = ('form_template', 'can_skip', 'show_in_progress_bar')
    search_fields = ('title', 'description', 'form_template__title')
    ordering = ['form_template', 'order']

    inlines = [FormFieldInline]

    def field_count(self, obj):
        return obj.get_field_count()
    field_count.short_description = 'Fields'


@admin.register(FormField)
class FormFieldAdmin(admin.ModelAdmin):
    list_display = (
        'label',
        'phase',
        'field_type',
        'order',
        'is_required',
        'conditional_display'
    )
    list_filter = ('field_type', 'is_required', 'phase__form_template')
    search_fields = ('label', 'help_text', 'phase__title')
    ordering = ['phase', 'order']

    fieldsets = (
        ('Basic Configuration', {
            'fields': ('phase', 'order', 'field_type', 'label', 'placeholder', 'help_text', 'default_value')
        }),
        ('Validation', {
            'fields': ('is_required', 'validation_rules')
        }),
        ('Options & Choices', {
            'fields': ('options', 'max_selections'),
            'classes': ('collapse',)
        }),
        ('File Upload Settings', {
            'fields': ('allowed_file_types', 'max_file_size_mb'),
            'classes': ('collapse',)
        }),
        ('Course Selector Settings', {
            'fields': ('filter_by_career', 'check_prerequisites', 'check_schedule_conflicts', 'max_credits'),
            'classes': ('collapse',)
        }),
        ('Conditional Logic', {
            'fields': ('conditional_logic',),
            'classes': ('collapse',)
        }),
    )

    def conditional_display(self, obj):
        if obj.conditional_logic:
            return format_html('<span style="color: orange;">Yes</span>')
        return '-'
    conditional_display.short_description = 'Has Conditions'


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'form_template',
        'submitter',
        'status_badge',
        'payment_status_badge',
        'completion_percentage',
        'current_phase',
        'created_at'
    )
    list_filter = ('status', 'payment_status', 'form_template', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'guest_email')
    readonly_fields = (
        'created_at',
        'updated_at',
        'completed_at',
        'completion_percentage',
        'get_submitter_email',
        'ip_address',
        'user_agent'
    )
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Form Information', {
            'fields': ('form_template', 'status', 'current_phase')
        }),
        ('Submitter', {
            'fields': ('user', 'guest_email', 'get_submitter_email')
        }),
        ('Form Data', {
            'fields': ('submission_data', 'uploaded_files'),
            'classes': ('collapse',)
        }),
        ('Payment Information', {
            'fields': (
                'payment_status',
                'payment_amount',
                'stripe_payment_intent_id',
                'stripe_checkout_session_id',
                'payment_date'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_completed', 'mark_payment_completed']

    def submitter(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.guest_email
    submitter.short_description = 'Submitter'

    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'in_progress': 'blue',
            'pending_payment': 'orange',
            'completed': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def payment_status_badge(self, obj):
        colors = {
            'not_required': 'gray',
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'purple',
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment'

    def completion_percentage(self, obj):
        percentage = obj.get_completion_percentage()
        color = 'green' if percentage == 100 else 'orange' if percentage > 50 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            percentage
        )
    completion_percentage.short_description = 'Completion'

    def mark_as_completed(self, request, queryset):
        updated = 0
        for submission in queryset:
            if submission.status != 'completed':
                submission.mark_as_completed()
                updated += 1
        self.message_user(request, f'{updated} submission(s) marked as completed.')
    mark_as_completed.short_description = 'Mark selected as completed'

    def mark_payment_completed(self, request, queryset):
        updated = queryset.update(payment_status='completed')
        self.message_user(request, f'{updated} payment(s) marked as completed.')
    mark_payment_completed.short_description = 'Mark payment as completed'


@admin.register(FormSubmissionFile)
class FormSubmissionFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'submission', 'field', 'file_size_display', 'uploaded_at')
    list_filter = ('uploaded_at', 'content_type')
    search_fields = ('original_filename', 'submission__user__email', 'submission__guest_email')
    readonly_fields = ('uploaded_at', 'file_size_display')

    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'File Size'
