from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, BroadcastNotificationView, NotificationStatsView

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
    path('broadcast/', BroadcastNotificationView.as_view(), name='broadcast-notification'),
    path('stats/', NotificationStatsView.as_view(), name='notification-stats'),
]
