"""Acceso a Oracle para la app del hospital.

Las operaciones que modifican datos usan `transaccion()`: abren una conexión,
ejecutan todo y hacen COMMIT al final; si algo falla (regla de negocio o error
de Oracle) hacen ROLLBACK y no queda nada a medias.

Config por variables de entorno (no dejar la clave escrita en el código):
    HOSPITAL_USER, HOSPITAL_PASSWORD, HOSPITAL_DSN (ej: localhost:1521/XEPDB1)
"""
import atexit
import os
import re
from contextlib import contextmanager
from datetime import datetime, time, timedelta

import oracledb

USUARIO = os.getenv("HOSPITAL_USER", "hospital")
CLAVE = os.getenv("HOSPITAL_PASSWORD", "hospital")
DSN = os.getenv("HOSPITAL_DSN", "127.0.0.1:1521/XEPDB1")

# Turno -> (nombre, hora de inicio). Cada turno dura 8 horas.
TURNOS = {1: ("Mañana", 6), 2: ("Tarde", 14), 3: ("Noche", 22)}
TABLA_TURNO = {1: "guardia_turno_manana", 2: "guardia_turno_tarde", 3: "guardia_turno_noche"}

_pool = None


class ReglaError(Exception):
    """Una regla del enunciado que valida la app."""


class ErrorTrigger(ReglaError):
    """Error de regla de negocio devuelto por un trigger de Oracle (ORA-20000..20999)."""

    def __init__(self, codigo, mensaje):
        self.codigo = codigo
        super().__init__(mensaje)


def _obtener_pool():
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=USUARIO, password=CLAVE, dsn=DSN,
            min=1, max=4, increment=1)
    return _pool


def cerrar_pool():
    global _pool
    if _pool is not None:
        try:
            _pool.close(force=True)
        except oracledb.Error:
            pass
        _pool = None


atexit.register(cerrar_pool)


def conectar():
    return _obtener_pool().acquire()


@contextmanager
def transaccion():
    """Entrega un cursor; COMMIT si el bloque termina bien, ROLLBACK si falla."""
    cnx = conectar()
    cur = cnx.cursor()
    try:
        yield cur
        cnx.commit()
    except oracledb.DatabaseError as e:
        cnx.rollback()
        err = e.args[0] if e.args else None
        codigo = getattr(err, "code", None)
        if codigo is not None and 20000 <= codigo <= 20999:
            primera = (getattr(err, "message", None) or str(e)).strip().splitlines()[0]
            texto = re.sub(r"^ORA-\d+:\s*", "", primera).strip()
            raise ErrorTrigger(codigo, texto) from e
        raise
    except Exception:
        cnx.rollback()
        raise
    finally:
        cur.close()
        cnx.close()


def consultar(sql, **params):
    with conectar() as cnx:
        with cnx.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Listados (solo lectura)
# ---------------------------------------------------------------------------
def camas_disponibles():
    """Llama al procedure con sus dos cursores: (resumen, detalle)."""
    with conectar() as cnx:
        with cnx.cursor() as cur, cnx.cursor() as c_cant, cnx.cursor() as c_det:
            cur.callproc("pr_camas_disponibles", [c_cant, c_det])
            return c_cant.fetchall(), c_det.fetchall()


def comentarios_internacion(id_internacion, dni):
    with conectar() as cnx:
        with cnx.cursor() as cur, cnx.cursor() as c:
            cur.callproc("pr_comentarios_internacion", [id_internacion, dni, c])
            return c.fetchall()


def listar_pacientes():
    return consultar("""
        SELECT p.dni, pe.apellido, pe.nombre,
               TO_CHAR(p.fecha_nacimiento_paciente, 'YYYY-MM-DD'), p.sexo_paciente
          FROM paciente p JOIN persona pe ON pe.dni = p.dni
         ORDER BY pe.apellido, pe.nombre""")


def listar_medicos():
    return consultar("""
        SELECT m.matricula_medico, m.dni, pe.apellido, pe.nombre,
               m.cuil_cuit, m.cantidad_guardias
          FROM medico m JOIN persona pe ON pe.dni = m.dni
         ORDER BY pe.apellido, pe.nombre""")


def listar_especialidades():
    return [f[0] for f in consultar(
        "SELECT nombre_especialidad FROM especialidad ORDER BY 1")]


def especialidades_de_guardia(matricula):
    return [f[0] for f in consultar(
        """SELECT nombre_especialidad FROM posee
            WHERE matricula_medico = :mat AND hace_guardia = 'S' ORDER BY 1""",
        mat=matricula)]


def camas_libres():
    return consultar("""
        SELECT nro_habitacion, nro_cama, nombre_sector
          FROM vw_cama_disponible ORDER BY nro_habitacion, nro_cama""")


def internaciones_abiertas():
    return consultar("""
        SELECT i.id_internacion, i.dni, pe.apellido || ', ' || pe.nombre,
               i.matricula_medico, o.nro_habitacion, o.nro_cama,
               TO_CHAR(i.fecha_inicio_internacion, 'YYYY-MM-DD HH24:MI')
          FROM internacion i
          JOIN persona pe ON pe.dni = i.dni
          LEFT JOIN ocupa o ON o.id_internacion = i.id_internacion
                           AND o.fecha_terminacion_cama IS NULL
         WHERE i.fecha_terminacion_internacion IS NULL
         ORDER BY i.id_internacion""")


def listar_guardias():
    return consultar("""
        SELECT g.id_guardia, d.matricula_medico, d.nombre_especialidad,
               TO_CHAR(g.fecha_inicio_guardia, 'YYYY-MM-DD HH24:MI'),
               TO_CHAR(g.fecha_fin_guardia, 'YYYY-MM-DD HH24:MI')
          FROM guardia g JOIN desempena d ON d.id_guardia = g.id_guardia
         ORDER BY g.fecha_inicio_guardia DESC
         FETCH FIRST 200 ROWS ONLY""")


def listar_auditoria():
    return consultar("""
        SELECT id_auditoria, TO_CHAR(fecha_hora, 'YYYY-MM-DD HH24:MI:SS'),
               usuario_bd, tabla_afectada, operacion, clave_registro, detalle_cambio
          FROM auditoria_guardias
         ORDER BY id_auditoria DESC
         FETCH FIRST 300 ROWS ONLY""")


# ---------------------------------------------------------------------------
# Helpers de validación
# ---------------------------------------------------------------------------
def _contar(cur, sql, **params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _exigir_dni(dni):
    if not re.fullmatch(r"[0-9]{6,9}", dni or ""):
        raise ReglaError("El DNI debe tener entre 6 y 9 dígitos numéricos.")


def _exigir_texto(valor, nombre):
    if not (valor or "").strip():
        raise ReglaError(f"Falta completar: {nombre}.")


def _asegurar_persona(cur, dni, nombre, apellido):
    """PERSONA es compartida: un médico que también es paciente reutiliza el DNI."""
    if _contar(cur, "SELECT COUNT(*) FROM persona WHERE dni = :dni", dni=dni) == 0:
        _exigir_texto(nombre, "nombre")
        _exigir_texto(apellido, "apellido")
        cur.execute(
            "INSERT INTO persona (dni, nombre, apellido) VALUES (:dni, :nom, :ape)",
            dni=dni, nom=nombre.strip(), ape=apellido.strip())


# ---------------------------------------------------------------------------
# Pacientes y médicos
# ---------------------------------------------------------------------------
def alta_paciente(dni, nombre, apellido, fecha_nacimiento, sexo):
    _exigir_dni(dni)
    if sexo not in ("F", "M", "X"):
        raise ReglaError("El sexo debe ser F, M o X.")
    with transaccion() as cur:
        if _contar(cur, "SELECT COUNT(*) FROM paciente WHERE dni = :dni", dni=dni):
            raise ReglaError("Ya existe un paciente con ese DNI.")
        _asegurar_persona(cur, dni, nombre, apellido)
        cur.execute(
            """INSERT INTO paciente (dni, fecha_nacimiento_paciente, sexo_paciente)
               VALUES (:dni, :nac, :sexo)""",
            dni=dni, nac=fecha_nacimiento, sexo=sexo)


def alta_medico(matricula, dni, nombre, apellido, cuil, fecha_ingreso,
                max_guardias, foto, especialidades):
    """especialidades: lista de (nombre_especialidad, hace_guardia: bool)."""
    _exigir_dni(dni)
    if not re.fullmatch(r"[0-9]{11}", cuil or ""):
        raise ReglaError("El CUIL/CUIT debe tener 11 dígitos.")
    if max_guardias < 0:
        raise ReglaError("El máximo de guardias por mes no puede ser negativo.")
    with transaccion() as cur:
        if _contar(cur, "SELECT COUNT(*) FROM medico WHERE matricula_medico = :m", m=matricula):
            raise ReglaError("Ya existe un médico con esa matrícula.")
        if _contar(cur, "SELECT COUNT(*) FROM medico WHERE dni = :dni", dni=dni):
            raise ReglaError("Ya existe un médico con ese DNI.")
        if _contar(cur, "SELECT COUNT(*) FROM medico WHERE cuil_cuit = :c", c=cuil):
            raise ReglaError("Ya existe un médico con ese CUIL/CUIT.")
        _asegurar_persona(cur, dni, nombre, apellido)

        with cur.connection.cursor() as cur_med:   # cursor propio por el BLOB
            if foto:
                cur_med.setinputsizes(foto=oracledb.DB_TYPE_BLOB)
            cur_med.execute(
                """INSERT INTO medico (matricula_medico, dni, foto, cuil_cuit,
                                       fecha_de_ingreso, cantidad_guardias)
                   VALUES (:mat, :dni, :foto, :cuil, :ing, :maxg)""",
                mat=matricula, dni=dni, foto=foto or None, cuil=cuil,
                ing=fecha_ingreso, maxg=max_guardias)

        for esp, hace_guardia in especialidades:
            if _contar(cur, "SELECT COUNT(*) FROM especialidad WHERE nombre_especialidad = :e",
                       e=esp) == 0:
                cur.execute("INSERT INTO especialidad (nombre_especialidad) VALUES (:e)", e=esp)
            cur.execute(
                """INSERT INTO posee (matricula_medico, nombre_especialidad, hace_guardia)
                   VALUES (:mat, :esp, :hg)""",
                mat=matricula, esp=esp, hg="S" if hace_guardia else "N")


# ---------------------------------------------------------------------------
# Internaciones y camas
# ---------------------------------------------------------------------------
def _tomar_cama(cur, nro_hab, nro_cama):
    """Bloquea la fila de la cama para serializar asignaciones concurrentes.

    El FOR UPDATE evita que dos usuarios le asignen la misma cama a la vez:
    el segundo espera al COMMIT/ROLLBACK del primero y luego el trigger
    trg_validar_ocupa (ORA-20011) detecta si quedó ocupada.
    """
    cur.execute(
        "SELECT 1 FROM cama WHERE nro_habitacion = :h AND nro_cama = :c FOR UPDATE",
        h=nro_hab, c=nro_cama)
    if cur.fetchone() is None:
        raise ReglaError("La cama indicada no existe.")


def _asignar_cama(cur, id_internacion, nro_hab, nro_cama, ahora):
    cur.execute(
        """INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama)
           VALUES (:i, :ahora, :h, :c)""",
        i=id_internacion, ahora=ahora, h=nro_hab, c=nro_cama)


def internar(dni, matricula, nro_hab, nro_cama):
    """Transacción: crea la INTERNACION y le asigna la primera cama.

    Delega en triggers de Oracle:
      - trg_internacion_medico_paciente (ORA-20001): médico principal <> paciente
      - trg_validar_ocupa (ORA-20010..20012): rango y no solapamiento de camas
    """
    ahora = datetime.now()
    with transaccion() as cur:
        cur.execute("SELECT 1 FROM paciente WHERE dni = :dni FOR UPDATE", dni=dni)
        if cur.fetchone() is None:
            raise ReglaError("El DNI no corresponde a un paciente registrado.")
        cur.execute("SELECT 1 FROM medico WHERE matricula_medico = :m", m=matricula)
        if cur.fetchone() is None:
            raise ReglaError("La matrícula no corresponde a un médico registrado.")
        if _contar(cur, """SELECT COUNT(*) FROM internacion
                            WHERE dni = :dni AND fecha_terminacion_internacion IS NULL""",
                   dni=dni):
            raise ReglaError("El paciente ya tiene una internación en curso.")

        _tomar_cama(cur, nro_hab, nro_cama)

        nuevo_id = cur.var(int)
        cur.execute(
            """INSERT INTO internacion (fecha_inicio_internacion, matricula_medico, dni)
               VALUES (:ini, :mat, :dni) RETURNING id_internacion INTO :nuevo_id""",
            ini=ahora, mat=matricula, dni=dni, nuevo_id=nuevo_id)
        id_internacion = int(nuevo_id.getvalue()[0])
        _asignar_cama(cur, id_internacion, nro_hab, nro_cama, ahora)
        return id_internacion


def _bloquear_internacion_abierta(cur, id_internacion):
    cur.execute(
        """SELECT fecha_terminacion_internacion FROM internacion
            WHERE id_internacion = :i FOR UPDATE""", i=id_internacion)
    fila = cur.fetchone()
    if fila is None:
        raise ReglaError("La internación no existe.")
    if fila[0] is not None:
        raise ReglaError("La internación ya tiene el alta.")


def cambiar_cama(id_internacion, nro_hab, nro_cama):
    """Transacción: cierra la ocupación actual y abre la nueva en el mismo instante."""
    ahora = datetime.now()
    with transaccion() as cur:
        _bloquear_internacion_abierta(cur, id_internacion)
        cur.execute(
            """SELECT nro_habitacion, nro_cama FROM ocupa
                WHERE id_internacion = :i AND fecha_terminacion_cama IS NULL FOR UPDATE""",
            i=id_internacion)
        actual = cur.fetchone()
        if actual and (int(actual[0]), int(actual[1])) == (nro_hab, nro_cama):
            raise ReglaError("El paciente ya está en esa cama.")
        _tomar_cama(cur, nro_hab, nro_cama)
        if actual:
            cur.execute(
                """UPDATE ocupa SET fecha_terminacion_cama = :ahora
                    WHERE id_internacion = :i AND fecha_terminacion_cama IS NULL""",
                ahora=ahora, i=id_internacion)
        _asignar_cama(cur, id_internacion, nro_hab, nro_cama, ahora)


def dar_alta(id_internacion):
    """Transacción: libera la cama actual y cierra la internación."""
    ahora = datetime.now()
    with transaccion() as cur:
        _bloquear_internacion_abierta(cur, id_internacion)
        cur.execute(
            """UPDATE ocupa SET fecha_terminacion_cama = :ahora
                WHERE id_internacion = :i AND fecha_terminacion_cama IS NULL""",
            ahora=ahora, i=id_internacion)
        cur.execute(
            """UPDATE internacion SET fecha_terminacion_internacion = :ahora
                WHERE id_internacion = :i""", ahora=ahora, i=id_internacion)


# ---------------------------------------------------------------------------
# Guardias
# ---------------------------------------------------------------------------
def calcular_intervalo(dia, turnos):
    """Devuelve (turnos ordenados, inicio, fin). Los turnos deben ser contiguos."""
    turnos = sorted(set(turnos))
    if not turnos:
        raise ReglaError("Elegí al menos un turno.")
    if turnos != list(range(turnos[0], turnos[-1] + 1)):
        raise ReglaError("Los turnos de una misma guardia tienen que ser contiguos.")
    inicio = datetime.combine(dia, time(TURNOS[turnos[0]][1]))
    fin = datetime.combine(dia, time(TURNOS[turnos[-1]][1])) + timedelta(hours=8)
    return turnos, inicio, fin


def alta_guardia(matricula, especialidad, dia, turnos):
    """Transacción: crea GUARDIA, sus turnos y asigna DESEMPENA.

    Delega en trg_validar_asignacion_guardia (ORA-20002..20005):
      - hace_guardia = 'S', vacaciones, internación del médico y tope mensual.
    Si el trigger rechaza el INSERT en DESEMPENA, transaccion() hace ROLLBACK
    revirtiendo GUARDIA, los turnos y el registro de auditoría de esa operación.
    """
    turnos, inicio, fin = calcular_intervalo(dia, turnos)
    with transaccion() as cur:
        cur.execute("SELECT 1 FROM medico WHERE matricula_medico = :m FOR UPDATE", m=matricula)
        if cur.fetchone() is None:
            raise ReglaError("El médico no existe.")

        if not _contar(cur, """SELECT COUNT(*) FROM posee
                                WHERE matricula_medico = :m AND nombre_especialidad = :e""",
                       m=matricula, e=especialidad):
            raise ReglaError("El médico no posee esa especialidad.")

        if _contar(cur, """SELECT COUNT(*) FROM desempena d JOIN guardia g ON g.id_guardia = d.id_guardia
                            WHERE d.nombre_especialidad = :e
                              AND g.fecha_inicio_guardia < :fin AND g.fecha_fin_guardia > :ini""",
                   e=especialidad, ini=inicio, fin=fin):
            raise ReglaError("Ya hay un médico asignado a esa especialidad en ese horario.")

        nuevo_id = cur.var(int)
        cur.execute(
            """INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
               VALUES (:ini, :fin) RETURNING id_guardia INTO :nuevo_id""",
            ini=inicio, fin=fin, nuevo_id=nuevo_id)
        id_guardia = int(nuevo_id.getvalue()[0])
        for t in turnos:
            cur.execute(f"INSERT INTO {TABLA_TURNO[t]} (id_guardia) VALUES (:g)", g=id_guardia)
        cur.execute(
            """INSERT INTO desempena (matricula_medico, nombre_especialidad, id_guardia)
               VALUES (:m, :e, :g)""", m=matricula, e=especialidad, g=id_guardia)
