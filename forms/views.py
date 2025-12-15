from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
import stripe

from .models import FormTemplate, FormPhase, FormField, FormSubmission, FormSubmissionFile
from .serializers import (
    FormTemplateListSerializer,
    FormTemplateDetailSerializer,
    FormTemplateCreateSerializer,
    FormPhaseSerializer,
    FormPhaseCreateSerializer,
    FormFieldSerializer,
    FormFieldCreateSerializer,
    FormSubmissionSerializer,
    FormSubmissionCreateSerializer,
    FormSubmissionListSerializer,
    FormSubmissionFileSerializer,
    PaymentIntentSerializer,
)
from authentication.permissions import IsAdminUser, IsAdminOrReadOnly

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class FormTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Form Templates
    - List: All active forms (public) or all forms (admins)
    - Retrieve: Get single form with all phases and fields
    - Create/Update/Delete: Admin only
    """

    def get_permissions(self):
        """
        Allow anonymous access for list and retrieve (public forms)
        Require admin for create, update, delete
        """
        if self.action in ['list', 'retrieve', 'get_by_slug']:
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = FormTemplate.objects.all()

        # Non-admin users only see active forms
        if not self.request.user.is_authenticated or self.request.user.role != 'admin':
            queryset = queryset.filter(is_active=True)

        # Filter by slug if provided
        slug = self.request.query_params.get('slug')
        if slug:
            queryset = queryset.filter(url_slug=slug)

        return queryset.prefetch_related('phases__fields').order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            # If filtering by slug, return detailed info with phases and fields
            if self.request.query_params.get('slug'):
                return FormTemplateDetailSerializer
            return FormTemplateListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return FormTemplateCreateSerializer
        return FormTemplateDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='by-slug')
    def get_by_slug(self, request, pk=None):
        """Get form template by URL slug"""
        form = get_object_or_404(FormTemplate, url_slug=pk, is_active=True)
        serializer = self.get_serializer(form)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def duplicate(self, request, pk=None):
        """Duplicate a form template"""
        original_form = self.get_object()

        # Create a copy of the form
        new_form = FormTemplate.objects.create(
            title=f"{original_form.title} (Copy)",
            description=original_form.description,
            requires_authentication=original_form.requires_authentication,
            requires_payment=original_form.requires_payment,
            payment_amount=original_form.payment_amount,
            send_confirmation_email=original_form.send_confirmation_email,
            allow_drafts=original_form.allow_drafts,
            draft_expiration_days=original_form.draft_expiration_days,
            max_submissions_per_user=original_form.max_submissions_per_user,
            created_by=request.user,
            is_active=False  # Start as inactive
        )

        # Copy phases and fields
        for phase in original_form.phases.all():
            new_phase = FormPhase.objects.create(
                form_template=new_form,
                order=phase.order,
                title=phase.title,
                description=phase.description,
                can_skip=phase.can_skip,
                show_in_progress_bar=phase.show_in_progress_bar
            )

            for field in phase.fields.all():
                FormField.objects.create(
                    phase=new_phase,
                    field_type=field.field_type,
                    order=field.order,
                    label=field.label,
                    placeholder=field.placeholder,
                    help_text=field.help_text,
                    default_value=field.default_value,
                    is_required=field.is_required,
                    validation_rules=field.validation_rules,
                    options=field.options,
                    conditional_logic=field.conditional_logic,
                    max_selections=field.max_selections,
                    allowed_file_types=field.allowed_file_types,
                    max_file_size_mb=field.max_file_size_mb,
                )

        serializer = self.get_serializer(new_form)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FormPhaseViewSet(viewsets.ModelViewSet):
    """ViewSet for Form Phases"""
    queryset = FormPhase.objects.all()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FormPhaseCreateSerializer
        return FormPhaseSerializer

    def get_queryset(self):
        queryset = FormPhase.objects.all()
        form_template_id = self.request.query_params.get('form_template')
        if form_template_id:
            queryset = queryset.filter(form_template_id=form_template_id)
        return queryset.order_by('order')


class FormFieldViewSet(viewsets.ModelViewSet):
    """ViewSet for Form Fields"""
    queryset = FormField.objects.all()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FormFieldCreateSerializer
        return FormFieldSerializer

    def get_queryset(self):
        queryset = FormField.objects.all()
        phase_id = self.request.query_params.get('phase')
        if phase_id:
            queryset = queryset.filter(phase_id=phase_id)
        return queryset.order_by('order')


class FormSubmissionViewSet(viewsets.ModelViewSet):
    """ViewSet for Form Submissions"""
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user

        # Admins can see all submissions
        if user.is_authenticated and user.role == 'admin':
            queryset = FormSubmission.objects.all()
        # Authenticated users see only their submissions
        elif user.is_authenticated:
            queryset = FormSubmission.objects.filter(user=user)
        # Anonymous users can access guest submissions (no user assigned) for detail views
        # but cannot list all submissions
        else:
            # For detail actions (retrieve, update, submit, etc.), allow access to guest submissions
            if self.action in ['retrieve', 'update', 'partial_update', 'save_draft', 'submit', 'recover_draft']:
                queryset = FormSubmission.objects.filter(user__isnull=True)
            else:
                # For list action, return empty queryset
                return FormSubmission.objects.none()

        # Filter by form template
        form_template_id = self.request.query_params.get('form_template')
        if form_template_id:
            queryset = queryset.filter(form_template_id=form_template_id)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by payment status
        payment_status_filter = self.request.query_params.get('payment_status')
        if payment_status_filter:
            queryset = queryset.filter(payment_status=payment_status_filter)

        return queryset.select_related('form_template', 'user').order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return FormSubmissionListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return FormSubmissionCreateSerializer
        return FormSubmissionSerializer

    def perform_create(self, serializer):
        """Create a new form submission"""
        # Set user if authenticated
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def save_draft(self, request, pk=None):
        """Save form data as draft"""
        submission = self.get_object()

        # Verify ownership
        if not self._can_edit_submission(request.user, submission):
            return Response(
                {'error': 'You do not have permission to edit this submission.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update submission data
        submission_data = request.data.get('submission_data', {})
        current_phase = request.data.get('current_phase', submission.current_phase)

        submission.submission_data = submission_data
        submission.current_phase = current_phase
        submission.status = 'draft'
        submission.save()

        serializer = self.get_serializer(submission)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit the form (mark as completed or pending payment)"""
        submission = self.get_object()

        # Verify ownership
        if not self._can_edit_submission(request.user, submission):
            return Response(
                {'error': 'You do not have permission to edit this submission.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update final submission data
        submission_data = request.data.get('submission_data', submission.submission_data)
        submission.submission_data = submission_data

        # Check if payment is required
        if submission.form_template.requires_payment:
            submission.status = 'pending_payment'
            submission.payment_status = 'pending'
            submission.payment_amount = submission.form_template.payment_amount
        else:
            submission.mark_as_completed()

        submission.save()

        serializer = self.get_serializer(submission)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def recover_draft(self, request, pk=None):
        """Recover a draft submission"""
        submission = self.get_object()

        if not self._can_edit_submission(request.user, submission):
            return Response(
                {'error': 'You do not have permission to view this submission.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(submission)
        return Response(serializer.data)

    def _can_edit_submission(self, user, submission):
        """Check if user can edit the submission"""
        # Admin can edit any submission
        if user.is_authenticated and user.role == 'admin':
            return True

        # Owner can edit their submission
        if user.is_authenticated and submission.user == user:
            return True

        # Guest submissions (no user assigned) can be edited by anyone
        # In production, you'd want to add session-based security or token-based auth
        if submission.user is None:
            return True

        return False


class FileUploadView(APIView):
    """Handle file uploads for form submissions"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Upload a file for a form field"""
        submission_id = request.data.get('submission_id')
        field_id = request.data.get('field_id')
        file = request.FILES.get('file')

        if not all([submission_id, field_id, file]):
            return Response(
                {'error': 'submission_id, field_id, and file are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            submission = FormSubmission.objects.get(id=submission_id)
            field = FormField.objects.get(id=field_id)
        except (FormSubmission.DoesNotExist, FormField.DoesNotExist):
            return Response(
                {'error': 'Invalid submission or field ID.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate file type
        file_extension = file.name.split('.')[-1].lower()
        if field.allowed_file_types and file_extension not in field.allowed_file_types:
            return Response(
                {'error': f'File type .{file_extension} not allowed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size
        max_size = field.max_file_size_mb * 1024 * 1024  # Convert MB to bytes
        if file.size > max_size:
            return Response(
                {'error': f'File size exceeds {field.max_file_size_mb}MB limit.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create file record
        uploaded_file = FormSubmissionFile.objects.create(
            submission=submission,
            field=field,
            file=file,
            original_filename=file.name,
            file_size=file.size,
            content_type=file.content_type
        )

        serializer = FormSubmissionFileSerializer(uploaded_file)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreatePaymentIntent(APIView):
    """Create Stripe Checkout Session for payment"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Create a Stripe Checkout Session"""
        serializer = PaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission_id = serializer.validated_data['submission_id']
        return_url = serializer.validated_data['return_url']
        cancel_url = serializer.validated_data['cancel_url']

        try:
            submission = FormSubmission.objects.get(id=submission_id)
        except FormSubmission.DoesNotExist:
            return Response(
                {'error': 'Submission not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create Stripe Checkout Session
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(submission.payment_amount * 100),  # Amount in cents
                        'product_data': {
                            'name': submission.form_template.title,
                            'description': f'Submission #{submission.id}',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=return_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                client_reference_id=str(submission.id),
                metadata={
                    'submission_id': submission.id,
                    'form_template_id': submission.form_template.id,
                }
            )

            # Save session ID to submission
            submission.stripe_checkout_session_id = checkout_session.id
            submission.payment_status = 'processing'
            submission.save()

            return Response({
                'checkout_session_id': checkout_session.id,
                'checkout_url': checkout_session.url,
            })

        except stripe.error.StripeError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StripeWebhookView(APIView):
    """Handle Stripe webhook events"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Process Stripe webhook"""
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

        # Handle checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            self._handle_successful_payment(session)

        # Handle payment_intent.payment_failed event
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self._handle_failed_payment(payment_intent)

        return Response({'status': 'success'})

    def _handle_successful_payment(self, session):
        """Handle successful payment"""
        submission_id = session.get('metadata', {}).get('submission_id')

        if submission_id:
            try:
                submission = FormSubmission.objects.get(id=submission_id)
                submission.payment_status = 'completed'
                submission.payment_date = timezone.now()
                submission.stripe_payment_intent_id = session.get('payment_intent')
                submission.mark_as_completed()
                submission.save()

                # TODO: Send confirmation email

            except FormSubmission.DoesNotExist:
                pass

    def _handle_failed_payment(self, payment_intent):
        """Handle failed payment"""
        # You can extract submission_id from metadata if set
        pass
