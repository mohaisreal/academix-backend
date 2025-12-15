# API de Autenticación JWT - AcademiX

Sistema completo de autenticación basado en JWT (JSON Web Tokens) para el proyecto AcademiX.

## Endpoints Disponibles

### 1. Registro de Usuario
**POST** `/api/auth/register/`

Registra un nuevo usuario en el sistema.

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "password2": "string",
  "first_name": "string",
  "last_name": "string",
  "role": "student|teacher|admin",
  "phone": "string (opcional)",
  "address": "string (opcional)",
  "date_of_birth": "YYYY-MM-DD (opcional)",

  // Para estudiantes (si role = "student"):
  "student_id": "string (requerido para estudiantes)",

  // Para profesores (si role = "teacher"):
  "employee_id": "string (requerido para profesores)",
  "department": "string (opcional)",
  "specialization": "string (opcional)",
  "hire_date": "YYYY-MM-DD (opcional)"
}
```

**Response (201 Created):**
```json
{
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "student",
    "phone": "123456789",
    "address": "Calle Example 123",
    "date_of_birth": "2000-01-01",
    "profile_image": null,
    "created_at": "2025-10-09T12:00:00Z",
    "updated_at": "2025-10-09T12:00:00Z"
  },
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "message": "Usuario registrado exitosamente"
}
```

---

### 2. Login (Obtener Tokens)
**POST** `/api/auth/login/`

Inicia sesión y obtiene los tokens de acceso y refresh.

**Request Body:**
```json
{
  "username": "johndoe",
  "password": "mypassword123"
}
```

**Response (200 OK):**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "student"
  }
}
```

---

### 3. Refresh Token
**POST** `/api/auth/token/refresh/`

Obtiene un nuevo access token usando el refresh token.

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..." // Nuevo refresh token (rotación activada)
}
```

---

### 4. Logout
**POST** `/api/auth/logout/`

Cierra la sesión del usuario agregando el refresh token a la lista negra.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "message": "Sesión cerrada exitosamente"
}
```

---

### 5. Verificar Token
**GET** `/api/auth/verify/`

Verifica si el token de acceso es válido.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "valid": true,
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "role": "student"
  }
}
```

---

### 6. Obtener Perfil de Usuario
**GET** `/api/auth/profile/`

Obtiene la información completa del usuario autenticado.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "student",
  "phone": "123456789",
  "address": "Calle Example 123",
  "date_of_birth": "2000-01-01",
  "profile_image": null,
  "created_at": "2025-10-09T12:00:00Z",
  "updated_at": "2025-10-09T12:00:00Z",
  "student_profile": {
    "id": 1,
    "student_id": "EST-2024-001",
    "enrollment_date": "2024-01-15",
    "status": "active"
  }
}
```

---

### 7. Actualizar Perfil de Usuario
**PUT/PATCH** `/api/auth/profile/`

Actualiza la información del usuario autenticado.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body (PATCH - actualización parcial):**
```json
{
  "first_name": "John Updated",
  "phone": "987654321",
  "address": "Nueva Dirección 456"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "John Updated",
  "last_name": "Doe",
  "role": "student",
  "phone": "987654321",
  "address": "Nueva Dirección 456",
  "date_of_birth": "2000-01-01",
  "profile_image": null,
  "created_at": "2025-10-09T12:00:00Z",
  "updated_at": "2025-10-09T12:30:00Z"
}
```

---

### 8. Cambiar Contraseña
**POST** `/api/auth/change-password/`

Cambia la contraseña del usuario autenticado.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "old_password": "currentpassword",
  "new_password": "newpassword123",
  "new_password2": "newpassword123"
}
```

**Response (200 OK):**
```json
{
  "message": "Contraseña cambiada exitosamente"
}
```

---

### 9. Listar Usuarios
**GET** `/api/auth/users/`

Lista todos los usuarios (solo administradores ven todos, otros usuarios solo ven su propio perfil).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "student",
    "phone": "123456789",
    "address": "Calle Example 123",
    "date_of_birth": "2000-01-01",
    "profile_image": null,
    "created_at": "2025-10-09T12:00:00Z",
    "updated_at": "2025-10-09T12:00:00Z"
  }
]
```

---

### 10. Detalle de Usuario
**GET/PUT/PATCH/DELETE** `/api/auth/users/<id>/`

Operaciones sobre un usuario específico (solo administradores o el propio usuario).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (GET - 200 OK):**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "student",
  "phone": "123456789",
  "address": "Calle Example 123",
  "date_of_birth": "2000-01-01",
  "profile_image": null,
  "created_at": "2025-10-09T12:00:00Z",
  "updated_at": "2025-10-09T12:00:00Z"
}
```

---

## Permisos Personalizados

El sistema incluye varios permisos personalizados:

- **IsAdminUser**: Solo usuarios con rol de administrador
- **IsTeacherUser**: Solo usuarios con rol de profesor
- **IsStudentUser**: Solo usuarios con rol de estudiante
- **IsOwnerOrAdmin**: El propietario del recurso o un administrador
- **IsAdminOrReadOnly**: Solo lectura para todos, escritura solo para administradores
- **IsTeacherOrAdmin**: Profesores y administradores

---

## Configuración JWT

- **Access Token Lifetime**: 1 hora
- **Refresh Token Lifetime**: 7 días
- **Token Rotation**: Activada (se genera un nuevo refresh token al renovar)
- **Blacklist**: Activada (los tokens pueden ser invalidados al cerrar sesión)
- **Algorithm**: HS256

---

## CORS

El backend está configurado para aceptar peticiones desde:
- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:5173`
- `http://127.0.0.1:5173`

---

## Uso en el Frontend

### Ejemplo de Login:

```javascript
const login = async (username, password) => {
  const response = await fetch('http://localhost:8000/api/auth/login/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  });

  const data = await response.json();

  // Guardar tokens en localStorage
  localStorage.setItem('access_token', data.access);
  localStorage.setItem('refresh_token', data.refresh);

  return data;
};
```

### Ejemplo de Request Autenticado:

```javascript
const getUserProfile = async () => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/auth/profile/', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  return await response.json();
};
```

### Ejemplo de Refresh Token:

```javascript
const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem('refresh_token');

  const response = await fetch('http://localhost:8000/api/auth/token/refresh/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  const data = await response.json();

  // Actualizar tokens
  localStorage.setItem('access_token', data.access);
  localStorage.setItem('refresh_token', data.refresh);

  return data;
};
```

---

## Códigos de Estado HTTP

- **200 OK**: Operación exitosa
- **201 Created**: Recurso creado exitosamente
- **400 Bad Request**: Error en los datos enviados
- **401 Unauthorized**: Token inválido o no proporcionado
- **403 Forbidden**: No tiene permisos para realizar esta acción
- **404 Not Found**: Recurso no encontrado

---

## Notas Importantes

1. Todos los endpoints excepto `/register/` y `/login/` requieren autenticación
2. Los tokens de acceso expiran cada hora, usa el refresh token para renovarlos
3. Al cerrar sesión, el refresh token se agrega a la lista negra y no puede ser reutilizado
4. Las contraseñas son validadas usando los validadores de Django
5. Los usuarios con rol de estudiante deben proporcionar un `student_id` al registrarse
6. Los usuarios con rol de profesor deben proporcionar un `employee_id` al registrarse
