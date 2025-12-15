"""
System information views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import connection
from django.conf import settings
from django.contrib.auth import get_user_model
from users.models import Student, Teacher
from academic.models import Career, Subject
from enrollment.models import CareerEnrollment, SubjectEnrollment
from grades.models import Assignment
from schedules.models import Schedule
import sys
import django
import os
from datetime import datetime

User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_info(request):
    """
    Returns comprehensive system information
    """
    # Only allow admin users
    if not request.user.is_staff:
        return Response({"error": "No tienes permisos para ver esta información"}, status=403)

    # Database information
    db_config = settings.DATABASES['default']
    db_engine = db_config['ENGINE'].split('.')[-1]

    # Get database connection status
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Count statistics
    total_users = User.objects.count()
    total_students = Student.objects.count()
    total_teachers = Teacher.objects.count()
    total_careers = Career.objects.count()
    total_subjects = Subject.objects.count()
    total_enrollments = SubjectEnrollment.objects.count()
    total_assignments = Assignment.objects.count()
    total_schedules = Schedule.objects.count()

    # Calculate media storage usage
    media_root = settings.MEDIA_ROOT
    total_size = 0
    file_count = 0

    if os.path.exists(media_root):
        for dirpath, dirnames, filenames in os.walk(media_root):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
                    file_count += 1

    # Convert bytes to GB
    total_size_gb = total_size / (1024 ** 3)

    # System versions
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    django_version = django.get_version()

    # Database version (try to get it)
    db_version = "Unknown"
    try:
        if 'postgresql' in db_engine.lower():
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version_string = cursor.fetchone()[0]
                # Extract version number from string like "PostgreSQL 15.3..."
                db_version = version_string.split()[1]
        elif 'sqlite' in db_engine.lower():
            import sqlite3
            db_version = sqlite3.sqlite_version
    except Exception:
        pass

    return Response({
        "status": "operational",
        "system": {
            "version": "1.0.0",
            "environment": "development" if settings.DEBUG else "production",
            "debug_mode": settings.DEBUG
        },
        "backend": {
            "framework": "Django",
            "version": django_version,
            "python_version": python_version,
            "status": "active"
        },
        "database": {
            "engine": "PostgreSQL" if 'postgresql' in db_engine.lower() else "SQLite",
            "version": db_version,
            "status": db_status
        },
        "storage": {
            "total_files": file_count,
            "used_gb": round(total_size_gb, 2),
            "media_root": str(media_root)
        },
        "statistics": {
            "total_users": total_users,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_careers": total_careers,
            "total_subjects": total_subjects,
            "total_enrollments": total_enrollments,
            "total_assignments": total_assignments,
            "total_schedules": total_schedules
        },
        "last_backup": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "uptime": "Sistema operacional"
    })
