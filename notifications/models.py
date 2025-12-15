from django.db import models
from users.models import User

class Notification(models.Model):
    """
    Model for system notifications
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('grade_published', 'Calificación Publicada'),
        ('enrollment_confirmed', 'Matriculación Confirmada'),
        ('subject_enrolled', 'Inscripción a Asignatura'),
        ('deadline_reminder', 'Recordatorio de Fecha Límite'),
        ('schedule_change', 'Cambio de Horario'),
        ('evaluation_created', 'Evaluación Creada'),
        ('general', 'General'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', '-created_at']),
        ]

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"

    def mark_as_read(self):
        """Mark the notification as read"""
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
