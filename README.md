# TP Hospital — Grupo 3

Trabajo práctico de bases de datos: esquema Oracle para un hospital (pacientes, médicos, camas, internaciones, rondas y guardias) más una aplicación de escritorio en Python que lo consume.

## `docs/`

Material de diseño y entregas:

| Archivo | Contenido |
|---|---|
| `Presentacion_TP.pdf` | Diapositivas de la presentación del TP |
| `1era_Entrega_Informe_Grupo3.pdf` | Informe de la primera entrega |
| `DER_Grupo_3.png` | Diagrama entidad-relación |
| `Presentacion_MongoDB.pdf` | Presentación sobre MongoDB |

## `sql/`

Scripts Oracle, pensados para ejecutarse en orden numérico:

| Script | Contenido |
|---|---|
| `user.sql` | Crea el usuario Oracle del TP |
| `00_drops.sql` | Elimina tablas del esquema |
| `01_1tablas_ddl.sql` | DDL: tablas, PKs, FKs y constraints |
| `01_2_auditorias.sql` | Tabla y triggers de auditoría de guardias |
| `02_inserts.sql` | Datos de prueba |
| `03_casos_de_uso.sql` | Casos de uso válidos |
| `04_casos_de_uso_invalidos.sql` | Casos que deben fallar (constraints / reglas de negocio) |
| `05_procedures.sql` | Vistas y procedures |
| `06_triggers.sql` | Triggers de reglas de negocio |
| `07_bateria_pruebas.sql` | Batería de pruebas (SAVEPOINT + ROLLBACK; no altera datos) |

## Aplicación Python

Cliente de escritorio (`Tkinter` + `python-oracledb`) con arquitectura **MVC + capa de persistencia**:

- **`app.py`** — entrada principal
- **`hospital/models`** — entidades y excepciones de dominio
- **`hospital/persistence`** — pool de conexiones y DAOs
- **`hospital/controllers`** — lógica de aplicación y transacciones
- **`hospital/views`** — interfaz por pestañas (pacientes, médicos, internaciones, rondas, guardias, reportes, auditoría, pruebas)

### Cómo levantarla

1. **Entorno e instalación**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. **Conexión a Oracle** (opcional)

Copiar `.env.example` a `.env` y completar `HOSPITAL_USER`, `HOSPITAL_PASSWORD` y `HOSPITAL_DSN`.  
Si no hay `.env`, al iniciar se pide usuario y contraseña (DSN por defecto: `localhost:1521/FREEPDB1`).

3. **Ejecutar**

```bash
python app.py
```

Otras entradas:

```bash
python pruebas.py          # batería interactiva de pruebas
python -m pytest -v        # tests automatizados
```
