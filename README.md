# Sistema de Gestión Hospitalaria — Aplicación Host

Aplicación de escritorio en Python (`Tkinter` + `python-oracledb`) para la gestión hospitalaria sobre Oracle Database.

## Organización de la aplicación

La aplicación sigue una arquitectura **MVC + Capa de Persistencia**:

```text
bd-tp-hospital/
├── app.py                              # Punto de entrada principal (Tkinter)
├── pruebas.py                          # Punto de entrada standalone de la batería de pruebas
├── requirements.txt                    # Dependencias Python
├── .env.example                        # Ejemplo de variables de entorno para conexión Oracle
├── hospital/
│   ├── config.py                       # Configuración de conexión (.env / variables de entorno)
│   ├── models/                         # Modelo: entidades y excepciones de dominio
│   │   ├── entities.py
│   │   └── exceptions.py
│   ├── persistence/                    # Capa de persistencia: pool, transacciones y DAOs SQL
│   │   ├── connection.py
│   │   ├── persona_dao.py
│   │   ├── paciente_dao.py
│   │   ├── medico_dao.py
│   │   ├── cama_dao.py
│   │   ├── internacion_dao.py
│   │   ├── ronda_dao.py
│   │   ├── guardia_dao.py
│   │   ├── reportes_dao.py
│   │   ├── auditoria_dao.py
│   │   └── pruebas_dao.py
│   ├── controllers/                    # Controladores: lógica de aplicación y transacciones
│   │   ├── container.py
│   │   ├── _validadores.py
│   │   ├── paciente_controller.py
│   │   ├── medico_controller.py
│   │   ├── internacion_controller.py
│   │   ├── ronda_controller.py
│   │   ├── guardia_controller.py
│   │   ├── reportes_controller.py
│   │   └── pruebas_controller.py
│   └── views/                          # Vistas Tkinter por pestaña
│       ├── widgets.py
│       ├── main_window.py
│       ├── camas_view.py
│       ├── comentarios_view.py
│       ├── pacientes_view.py
│       ├── medicos_view.py
│       ├── internaciones_view.py
│       ├── rondas_view.py
│       ├── guardias_view.py
│       ├── auditoria_view.py
│       └── pruebas_view.py
└── tests/                              # Pruebas automatizadas (pytest)
    └── test_mvc_and_controllers.py
```

## Cómo levantar la aplicación

### 1. Crear el entorno virtual e instalar dependencias

En Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

*(Si falla por certificados SSL en Windows, agregar `--use-feature=truststore` al comando `pip install`.)*

### 2. Configurar la conexión a Oracle (opcional)

- Si no se crea un archivo `.env`, al iniciar la aplicación se abre una ventana de inicio de sesión solicitando **Usuario** y **Contraseña** (DSN por defecto: `localhost:1521/FREEPDB1`).
- Para guardar la configuración o cambiar el DSN (por ejemplo `localhost:1521/XEPDB1`), copiar `.env.example` a `.env` y completar `HOSPITAL_USER`, `HOSPITAL_PASSWORD` y `HOSPITAL_DSN`.

### 3. Ejecutar

Aplicación principal:

```powershell
.\.venv\Scripts\python.exe app.py
```

Batería interactiva de pruebas (standalone):

```powershell
.\.venv\Scripts\python.exe pruebas.py
```

Pruebas automatizadas (`pytest`):

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
