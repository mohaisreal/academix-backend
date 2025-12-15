from rest_framework import serializers
from .models import FormTemplate, FormPhase, FormField, FormSubmission, FormSubmissionFile
from users.models import User


class FormFieldSerializer(serializers.ModelSerializer):
    """Serializer for form fields"""

    class Meta:
        model = FormField
        fields = [
            'id',
            'phase',
            'field_type',
            'order',
            'label',
            'placeholder',
            'help_text',
            'default_value',
            'is_required',
            'validation_rules',
            'options',
            'conditional_logic',
            'max_selections',
            'allowed_file_types',
            'max_file_size_mb',
            'filter_by_career',
            'check_prerequisites',
            'check_schedule_conflicts',
            'max_credits',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FormFieldCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating form fields"""
    id = serializers.IntegerField(required=False)

    class Meta:
        model = FormField
        fields = [
            'id',
            'field_type',
            'order',
            'label',
            'placeholder',
            'help_text',
            'default_value',
            'is_required',
            'validation_rules',
            'options',
            'conditional_logic',
            'max_selections',
            'allowed_file_types',
            'max_file_size_mb',
            'filter_by_career',
            'check_prerequisites',
            'check_schedule_conflicts',
            'max_credits',
        ]


class FormPhaseSerializer(serializers.ModelSerializer):
    """Serializer for form phases with nested fields"""
    fields = FormFieldSerializer(many=True, read_only=True)
    field_count = serializers.IntegerField(source='get_field_count', read_only=True)

    class Meta:
        model = FormPhase
        fields = [
            'id',
            'form_template',
            'order',
            'title',
            'description',
            'can_skip',
            'show_in_progress_bar',
            'fields',
            'field_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'field_count', 'created_at', 'updated_at']


class FormPhaseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating form phases with nested fields"""
    id = serializers.IntegerField(required=False)
    fields = FormFieldCreateSerializer(many=True, required=False)

    class Meta:
        model = FormPhase
        fields = [
            'id',
            'order',
            'title',
            'description',
            'can_skip',
            'show_in_progress_bar',
            'fields',
        ]

    def create(self, validated_data):
        fields_data = validated_data.pop('fields', [])
        phase = FormPhase.objects.create(**validated_data)

        for field_data in fields_data:
            FormField.objects.create(phase=phase, **field_data)

        return phase


class FormTemplateListSerializer(serializers.ModelSerializer):
    """Serializer for listing form templates"""
    total_phases = serializers.IntegerField(source='get_total_phases', read_only=True)
    submission_count = serializers.IntegerField(source='get_submission_count', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = FormTemplate
        fields = [
            'id',
            'url_slug',
            'title',
            'description',
            'is_active',
            'requires_authentication',
            'requires_payment',
            'payment_amount',
            'total_phases',
            'submission_count',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'total_phases', 'submission_count', 'created_by_name']


class FormTemplateDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed form template with all phases and fields"""
    phases = FormPhaseSerializer(many=True, read_only=True)
    total_phases = serializers.IntegerField(source='get_total_phases', read_only=True)
    submission_count = serializers.IntegerField(source='get_submission_count', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = FormTemplate
        fields = [
            'id',
            'url_slug',
            'title',
            'description',
            'is_active',
            'requires_authentication',
            'requires_payment',
            'payment_amount',
            'stripe_product_id',
            'stripe_price_id',
            'send_confirmation_email',
            'notification_emails',
            'allow_drafts',
            'draft_expiration_days',
            'max_submissions_per_user',
            'phases',
            'total_phases',
            'submission_count',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'phases', 'total_phases', 'submission_count', 'created_by_name']


class FormTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating form templates with nested phases"""
    phases = FormPhaseCreateSerializer(many=True, required=False)

    class Meta:
        model = FormTemplate
        fields = [
            'title',
            'url_slug',
            'description',
            'is_active',
            'requires_authentication',
            'requires_payment',
            'payment_amount',
            'stripe_product_id',
            'stripe_price_id',
            'send_confirmation_email',
            'notification_emails',
            'allow_drafts',
            'draft_expiration_days',
            'max_submissions_per_user',
            'phases',
        ]

    def create(self, validated_data):
        phases_data = validated_data.pop('phases', [])
        form_template = FormTemplate.objects.create(**validated_data)

        for phase_data in phases_data:
            fields_data = phase_data.pop('fields', [])
            phase = FormPhase.objects.create(form_template=form_template, **phase_data)

            for field_data in fields_data:
                FormField.objects.create(phase=phase, **field_data)

        return form_template

    def update(self, instance, validated_data):
        phases_data = validated_data.pop('phases', [])

        # Update the form template fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Track existing phases by ID to determine what to keep/update/delete
        existing_phases = {phase.id: phase for phase in instance.phases.all()}
        updated_phase_ids = []

        # Process each phase in the update data
        for phase_data in phases_data:
            fields_data = phase_data.pop('fields', [])
            phase_id = phase_data.get('id')

            if phase_id and phase_id in existing_phases:
                # Update existing phase
                phase = existing_phases[phase_id]
                for attr, value in phase_data.items():
                    if attr != 'id':  # Don't set the id attribute
                        setattr(phase, attr, value)
                phase.save()
                updated_phase_ids.append(phase_id)
            else:
                # Create new phase - remove id from data if present
                phase_data_copy = {k: v for k, v in phase_data.items() if k != 'id'}
                phase = FormPhase.objects.create(form_template=instance, **phase_data_copy)
                updated_phase_ids.append(phase.id)

            # Handle fields for this phase
            # Simple approach: delete all existing fields and recreate them
            # This avoids any unique constraint issues
            phase.fields.all().delete()

            # Create all fields from the update data
            for field_data in fields_data:
                # Remove id from data if present (we're creating fresh)
                field_data_copy = {k: v for k, v in field_data.items() if k != 'id'}
                FormField.objects.create(phase=phase, **field_data_copy)

        # Delete phases that were not in the update data
        for phase_id, phase in existing_phases.items():
            if phase_id not in updated_phase_ids:
                phase.delete()

        return instance


class FormSubmissionFileSerializer(serializers.ModelSerializer):
    """Serializer for uploaded files"""
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)

    class Meta:
        model = FormSubmissionFile
        fields = [
            'id',
            'submission',
            'field',
            'file',
            'original_filename',
            'file_size',
            'file_size_display',
            'content_type',
            'uploaded_at',
        ]
        read_only_fields = ['id', 'file_size_display', 'uploaded_at']


class FormSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for form submissions"""
    completion_percentage = serializers.IntegerField(source='get_completion_percentage', read_only=True)
    submitter_email = serializers.EmailField(source='get_submitter_email', read_only=True)
    form_template_title = serializers.CharField(source='form_template.title', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = FormSubmission
        fields = [
            'id',
            'form_template',
            'form_template_title',
            'user',
            'user_full_name',
            'guest_email',
            'submitter_email',
            'current_phase',
            'status',
            'submission_data',
            'uploaded_files',
            'payment_status',
            'payment_amount',
            'stripe_payment_intent_id',
            'stripe_checkout_session_id',
            'payment_date',
            'completion_percentage',
            'created_at',
            'updated_at',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'completion_percentage',
            'submitter_email',
            'form_template_title',
            'user_full_name',
            'created_at',
            'updated_at',
            'completed_at',
        ]


class FormSubmissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating form submissions"""

    class Meta:
        model = FormSubmission
        fields = [
            'id',
            'form_template',
            'user',
            'guest_email',
            'current_phase',
            'status',
            'submission_data',
            'uploaded_files',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        """Validate that either user or guest_email is provided"""
        user = data.get('user')
        guest_email = data.get('guest_email')
        form_template = data.get('form_template')

        # Forms that require authentication must have a user
        if form_template and form_template.requires_authentication:
            if not user:
                raise serializers.ValidationError(
                    "This form requires authentication. Please log in."
                )

        # For public forms, submissions are allowed without user or email

        return data


class FormSubmissionListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing submissions"""
    completion_percentage = serializers.IntegerField(source='get_completion_percentage', read_only=True)
    submitter_email = serializers.EmailField(source='get_submitter_email', read_only=True)
    form_template_title = serializers.CharField(source='form_template.title', read_only=True)

    class Meta:
        model = FormSubmission
        fields = [
            'id',
            'form_template',
            'form_template_title',
            'submitter_email',
            'status',
            'payment_status',
            'completion_percentage',
            'current_phase',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class PaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating Stripe payment intents"""
    submission_id = serializers.IntegerField(required=True)
    return_url = serializers.URLField(required=True)
    cancel_url = serializers.URLField(required=True)

    def validate_submission_id(self, value):
        """Validate that submission exists and requires payment"""
        try:
            submission = FormSubmission.objects.get(id=value)
        except FormSubmission.DoesNotExist:
            raise serializers.ValidationError("Submission not found.")

        if not submission.form_template.requires_payment:
            raise serializers.ValidationError("This form does not require payment.")

        if submission.payment_status == 'completed':
            raise serializers.ValidationError("Payment already completed for this submission.")

        return value
