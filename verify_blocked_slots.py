#!/usr/bin/env python
"""
Script de verificación para el sistema de Franjas Bloqueadas
Ejecutar con: python manage.py shell < verify_blocked_slots.py
"""

print("=" * 80)
print("🔍 VERIFICACIÓN DEL SISTEMA DE FRANJAS BLOQUEADAS")
print("=" * 80)
print()

# 1. Verificar imports
print("1️⃣  Verificando imports...")
try:
    from schedules.models import BlockedTimeSlot
    print("   ✅ BlockedTimeSlot model importado correctamente")
except ImportError as e:
    print(f"   ❌ Error al importar BlockedTimeSlot: {e}")
    exit(1)

try:
    from schedules.serializers import BlockedTimeSlotSerializer, BlockedTimeSlotListSerializer
    print("   ✅ Serializers importados correctamente")
except ImportError as e:
    print(f"   ❌ Error al importar serializers: {e}")
    exit(1)

try:
    from schedules.views import BlockedTimeSlotViewSet
    print("   ✅ ViewSet importado correctamente")
except ImportError as e:
    print(f"   ❌ Error al importar ViewSet: {e}")
    exit(1)

print()

# 2. Verificar modelo
print("2️⃣  Verificando modelo...")
try:
    # Verificar que la tabla existe
    count = BlockedTimeSlot.objects.count()
    print(f"   ✅ Tabla 'blocked_time_slots' existe ({count} registros)")

    # Verificar campos
    fields = [f.name for f in BlockedTimeSlot._meta.get_fields()]
    expected_fields = [
        'id', 'academic_period', 'time_slot', 'block_type',
        'career', 'classroom', 'reason', 'notes', 'is_active',
        'created_at', 'updated_at', 'created_by'
    ]

    missing_fields = set(expected_fields) - set(fields)
    if missing_fields:
        print(f"   ⚠️  Campos faltantes: {missing_fields}")
    else:
        print(f"   ✅ Todos los campos esperados están presentes")

except Exception as e:
    print(f"   ❌ Error al verificar modelo: {e}")
    print("   💡 ¿Ejecutaste las migraciones? python manage.py migrate schedules")

print()

# 3. Verificar opciones de block_type
print("3️⃣  Verificando opciones de block_type...")
try:
    choices = dict(BlockedTimeSlot.BLOCK_TYPE_CHOICES)
    print(f"   ✅ Opciones disponibles:")
    for key, value in choices.items():
        print(f"      - {key}: {value}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# 4. Verificar URLs
print("4️⃣  Verificando URLs...")
try:
    from django.urls import get_resolver
    from django.urls.resolvers import URLPattern, URLResolver

    def get_urls(resolver, prefix=''):
        urls = []
        for pattern in resolver.url_patterns:
            if isinstance(pattern, URLPattern):
                urls.append(prefix + str(pattern.pattern))
            elif isinstance(pattern, URLResolver):
                urls.extend(get_urls(pattern, prefix + str(pattern.pattern)))
        return urls

    resolver = get_resolver()
    all_urls = get_urls(resolver)
    blocked_urls = [url for url in all_urls if 'blocked-time-slots' in url]

    if blocked_urls:
        print(f"   ✅ URLs encontradas:")
        for url in blocked_urls:
            print(f"      - {url}")
    else:
        print("   ⚠️  No se encontraron URLs para blocked-time-slots")
        print("   💡 ¿Reiniciaste el servidor?")

except Exception as e:
    print(f"   ❌ Error al verificar URLs: {e}")

print()

# 5. Verificar serializer
print("5️⃣  Verificando serializers...")
try:
    # Crear instancia del serializer
    serializer = BlockedTimeSlotSerializer()
    fields = list(serializer.fields.keys())
    print(f"   ✅ Campos del serializer ({len(fields)}):")
    for field in fields:
        print(f"      - {field}")
except Exception as e:
    print(f"   ❌ Error al verificar serializer: {e}")

print()

# 6. Verificar permisos
print("6️⃣  Verificando ViewSet y permisos...")
try:
    viewset = BlockedTimeSlotViewSet()
    print(f"   ✅ ViewSet creado correctamente")
    print(f"   ✅ QuerySet: {viewset.queryset.model.__name__}")
    print(f"   ✅ Permisos: {[p.__name__ for p in viewset.permission_classes]}")
except Exception as e:
    print(f"   ❌ Error al verificar ViewSet: {e}")

print()

# 7. Verificar configuración de ScheduleConfiguration
print("7️⃣  Verificando campo max_classes_per_day...")
try:
    from schedules.models import ScheduleConfiguration

    # Verificar que el campo existe
    fields = [f.name for f in ScheduleConfiguration._meta.get_fields()]
    if 'max_classes_per_day' in fields:
        print("   ✅ Campo 'max_classes_per_day' existe en ScheduleConfiguration")

        # Obtener el campo
        field = ScheduleConfiguration._meta.get_field('max_classes_per_day')
        print(f"   ✅ Tipo: {field.get_internal_type()}")
        print(f"   ✅ Default: {field.default}")

        # Verificar validadores
        validators = field.validators
        print(f"   ✅ Validadores: {len(validators)}")
        for v in validators:
            print(f"      - {v.__class__.__name__}")
    else:
        print("   ❌ Campo 'max_classes_per_day' NO existe")
        print("   💡 ¿Ejecutaste las migraciones?")

except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# 8. Test de creación (opcional)
print("8️⃣  Test de creación (simulado)...")
try:
    print("   ℹ️  Verificando si podemos crear una instancia...")
    # No creamos realmente, solo verificamos que no haya errores de sintaxis
    instance = BlockedTimeSlot(
        reason="Test de verificación"
    )
    print("   ✅ Instancia creada correctamente (no guardada)")
except Exception as e:
    print(f"   ❌ Error al crear instancia: {e}")

print()
print("=" * 80)
print("✨ VERIFICACIÓN COMPLETADA")
print("=" * 80)
print()
print("📋 SIGUIENTE PASO:")
print("   Si todo está en verde (✅), reinicia el servidor Django:")
print("   1. Ctrl + C en la terminal del servidor")
print("   2. python manage.py runserver")
print()
print("   Si hay errores (❌):")
print("   - Revisa las migraciones: python manage.py showmigrations schedules")
print("   - Aplica migraciones: python manage.py migrate schedules")
print("   - Verifica imports en los archivos .py")
print()
