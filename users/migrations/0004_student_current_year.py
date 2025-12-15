# Generated manually

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_teacherqualifiedcareer_teacherqualifiedsubject'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='current_year',
            field=models.IntegerField(default=1, help_text='Año actual de la carrera del estudiante (1-10)', validators=[MinValueValidator(1), MaxValueValidator(10)]),
        ),
    ]
