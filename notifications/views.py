from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Notification
from .serializers import (
    NotificationSerializer, NotificationCreateSerializer,
    NotificationMarkReadSerializer
)


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return notifications for the current user
        """
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user)

        # Filter by read status
        is_read = self.request.query_params.get('is_read', None)
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')

        # Filter by type
        notification_type = self.request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(type=notification_type)

        # Filter by priority
        priority = self.request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        """
        Only admins can create notifications manually
        """
        if request.user.role != 'admin':
            return Response(
                {'error': 'No tienes permisos para crear notificaciones'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark a single notification as read
        """
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read for the current user
        """
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({
            'message': f'{updated} notificaciones marcadas como leídas',
            'count': updated
        })

    @action(detail=False, methods=['post'])
    def mark_selected_read(self, request):
        """
        Mark selected notifications as read
        """
        serializer = NotificationMarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_ids = serializer.validated_data.get('notification_ids', [])

        if not notification_ids:
            return self.mark_all_read(request)

        updated = Notification.objects.filter(
            recipient=request.user,
            id__in=notification_ids,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

        return Response({
            'message': f'{updated} notificaciones marcadas como leídas',
            'count': updated
        })

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """
        Get count of unread notifications for the current user
        """
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return Response({'unread_count': count})

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent notifications (last 10)
        """
        notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by('-created_at')[:10]

        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['delete'])
    def delete_read(self, request):
        """
        Delete all read notifications for the current user
        """
        deleted_count, _ = Notification.objects.filter(
            recipient=request.user,
            is_read=True
        ).delete()

        return Response({
            'message': f'{deleted_count} notificaciones eliminadas',
            'count': deleted_count
        })


class NotificationService:
    """
    Service class for creating and managing notifications
    """

    @staticmethod
    def create_notification(recipient, title, message, notification_type='general', priority='medium'):
        """
        Create a single notification
        """
        notification = Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            type=notification_type,
            priority=priority
        )
        return notification

    @staticmethod
    def create_bulk_notifications(recipients, title, message, notification_type='general', priority='medium'):
        """
        Create multiple notifications at once
        """
        notifications = [
            Notification(
                recipient=recipient,
                title=title,
                message=message,
                type=notification_type,
                priority=priority
            )
            for recipient in recipients
        ]
        Notification.objects.bulk_create(notifications)
        return len(notifications)

    @staticmethod
    def notify_enrollment_confirmed(student, subject_name, academic_period):
        """
        Notify student about enrollment confirmation
        """
        return NotificationService.create_notification(
            recipient=student.user,
            title='Inscripción Confirmada',
            message=f'Tu inscripción en {subject_name} para el período {academic_period} ha sido confirmada.',
            notification_type='enrollment_confirmed',
            priority='medium'
        )

    @staticmethod
    def notify_grade_published(student, subject_name, grade):
        """
        Notify student about published grade
        """
        return NotificationService.create_notification(
            recipient=student.user,
            title='Nueva Calificación Publicada',
            message=f'Tu calificación final para {subject_name} ha sido publicada: {grade}',
            notification_type='grade_published',
            priority='medium'
        )

    @staticmethod
    def notify_enrollment_deadline(students, deadline_date):
        """
        Notify students about enrollment deadline
        """
        title = 'Recordatorio: Fecha Límite de Inscripción'
        message = f'Recordatorio: La fecha límite para inscripciones es {deadline_date}. No olvides completar tu proceso de inscripción.'

        return NotificationService.create_bulk_notifications(
            recipients=[student.user for student in students],
            title=title,
            message=message,
            notification_type='deadline_reminder',
            priority='high'
        )

    @staticmethod
    def notify_schedule_change(students, subject_name, new_schedule):
        """
        Notify students about schedule changes
        """
        title = 'Cambio de Horario'
        message = f'El horario de {subject_name} ha cambiado. Nuevo horario: {new_schedule}'

        return NotificationService.create_bulk_notifications(
            recipients=[student.user for student in students],
            title=title,
            message=message,
            notification_type='schedule_change',
            priority='high'
        )

    @staticmethod
    def notify_waiting_list_enrolled(student, subject_name):
        """
        Notify student when they are enrolled from waiting list
        """
        return NotificationService.create_notification(
            recipient=student.user,
            title='Inscripción desde Lista de Espera',
            message=f'Has sido inscrito en {subject_name} desde la lista de espera. ¡Felicidades!',
            notification_type='subject_enrolled',
            priority='high'
        )

    @staticmethod
    def notify_evaluation_created(students, evaluation_name, subject_name, evaluation_date):
        """
        Notify students about new evaluation
        """
        title = 'Nueva Evaluación Programada'
        message = f'Se ha programado una nueva evaluación "{evaluation_name}" para {subject_name}'
        if evaluation_date:
            message += f' el día {evaluation_date}'

        return NotificationService.create_bulk_notifications(
            recipients=[student.user for student in students],
            title=title,
            message=message,
            notification_type='evaluation_created',
            priority='medium'
        )


class BroadcastNotificationView(views.APIView):
    """
    View for sending broadcast notifications (Admin only)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Send broadcast notification"""
        if request.user.role != 'admin':
            return Response(
                {'error': 'No tienes permisos para enviar notificaciones masivas'},
                status=status.HTTP_403_FORBIDDEN
            )

        title = request.data.get('title')
        message = request.data.get('message')
        notification_type = request.data.get('type', 'general')
        priority = request.data.get('priority', 'medium')
        recipient_roles = request.data.get('recipient_roles', ['student', 'teacher'])

        if not title or not message:
            return Response(
                {'error': 'Título y mensaje son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from users.models import User
        recipients = User.objects.filter(role__in=recipient_roles, is_active=True)

        count = NotificationService.create_bulk_notifications(
            recipients=recipients,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority
        )

        return Response({
            'message': f'Notificación enviada a {count} usuarios',
            'count': count
        })


class NotificationStatsView(views.APIView):
    """
    View for notification statistics (Admin only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get notification statistics"""
        if request.user.role != 'admin':
            return Response(
                {'error': 'No tienes permisos para ver estadísticas'},
                status=status.HTTP_403_FORBIDDEN
            )

        from django.db.models import Count, Q
        from datetime import date, timedelta

        # Total notifications
        total = Notification.objects.count()

        # By status
        unread = Notification.objects.filter(is_read=False).count()
        read = Notification.objects.filter(is_read=True).count()

        # By type
        by_type = Notification.objects.values('type').annotate(
            count=Count('id')
        ).order_by('-count')

        # By priority
        by_priority = Notification.objects.values('priority').annotate(
            count=Count('id')
        ).order_by('priority')

        # Recent activity (last 7 days)
        week_ago = date.today() - timedelta(days=7)
        recent_count = Notification.objects.filter(
            created_at__date__gte=week_ago
        ).count()

        # Most active recipients
        top_recipients = Notification.objects.values(
            'recipient__first_name', 'recipient__last_name', 'recipient__role'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        return Response({
            'total': total,
            'unread': unread,
            'read': read,
            'by_type': list(by_type),
            'by_priority': list(by_priority),
            'recent_count': recent_count,
            'top_recipients': list(top_recipients)
        })
