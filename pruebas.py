"""Batería interactiva de pruebas del TP Hospital (Procedures, Auditorías, Triggers y Transacciones).

Cada caso ejecuta contra Oracle y finaliza con ROLLBACK automático, por lo que
puede correrse caso por caso o completa todas las veces que sea necesario sin
modificar los datos precargados de 02_inserts.sql.

Uso integrado: se monta como pestaña en app.py.
Uso independiente:
    python pruebas.py
"""
import re
import tkinter as tk
from dataclasses import dataclass
from datetime import date
from tkinter import ttk
from typing import Callable, Optional

import oracledb

import db


@dataclass
class CasoPrueba:
    codigo: str
    grupo: str
    tipo: str          # "OK" o "FALLA"
    nombre: str
    esperado: str
    descripcion: str
    sql_resumen: str
    ejecutor: Callable[[], tuple[bool, str]]


def _limpiar_ora(exc):
    err = exc.args[0] if exc.args else None
    code = getattr(err, "code", None)
    primera = (getattr(err, "message", None) or str(exc)).strip().splitlines()[0]
    texto = re.sub(r"^ORA-\d+:\s*", "", primera).strip()
    return code, texto


def _correr_en_rollback(fn):
    """Abre una conexión del pool, ejecuta fn(cnx, cur) y SIEMPRE hace ROLLBACK."""
    cnx = db.conectar()
    cur = cnx.cursor()
    try:
        return fn(cnx, cur)
    finally:
        try:
            cnx.rollback()
        finally:
            cur.close()
            cnx.close()


def _probar_sql_ok(fn):
    """Espera que fn(cnx, cur) termine sin errores y devuelva un detalle."""
    try:
        detalle = _correr_en_rollback(fn)
        return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
    except oracledb.Error as e:
        code, msg = _limpiar_ora(e)
        return False, f"Falló inesperadamente con ORA-{code}: {msg}"
    except Exception as e:
        return False, f"Error inesperado: {e}"


def _probar_sql_falla(codigo_esperado, fn):
    """Espera que fn(cnx, cur) dispare un error Oracle con codigo_esperado."""
    try:
        _correr_en_rollback(fn)
        return False, f"NO falló: la base aceptó la operación cuando se esperaba ORA-{codigo_esperado:05d}."
    except oracledb.DatabaseError as e:
        code, msg = _limpiar_ora(e)
        if code == codigo_esperado:
            return True, f"Rechazado correctamente por Oracle (ORA-{code:05d}):\n\"{msg}\"\n(ROLLBACK aplicado.)"
        return False, f"Se esperaba ORA-{codigo_esperado:05d}, pero devolvió ORA-{code}: {msg}"
    except Exception as e:
        return False, f"Error inesperado: {e}"


# ---------------------------------------------------------------------------
# Definición de todos los casos de prueba (1 OK + 1 o más FALLA por ítem)
# ---------------------------------------------------------------------------
def _c1a_camas_ok():
    def _run(cnx, cur):
        with cnx.cursor() as c1, cnx.cursor() as c2:
            cur.callproc("pr_camas_disponibles", [c1, c2])
            resumen1 = c1.fetchall()
            detalle1 = c2.fetchall()
        pediatria_ok = any(sec == "Pediatria" and cant == 0 for sec, cant in resumen1)
        total1 = sum(cant for _, cant in resumen1)
        if not detalle1:
            raise RuntimeError("No hay camas libres en la base para probar.")
        _, hab, _, _, cama = detalle1[0]

        v_int = cur.var(int)
        cur.execute("""
            INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
            VALUES (SYSTIMESTAMP - INTERVAL '1' MINUTE, NULL, 1001, '30333333')
            RETURNING id_internacion INTO :id""", id=v_int)
        id_int = int(v_int.getvalue()[0])
        cur.execute("""
            INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama, fecha_terminacion_cama)
            VALUES (:i, SYSTIMESTAMP - INTERVAL '1' MINUTE, :h, :c, NULL)""",
                    i=id_int, h=hab, c=cama)

        with cnx.cursor() as c1, cnx.cursor() as c2:
            cur.callproc("pr_camas_disponibles", [c1, c2])
            resumen2 = c1.fetchall()
            _ = c2.fetchall()
        total2 = sum(cant for _, cant in resumen2)

        if not pediatria_ok or total2 != total1 - 1:
            raise RuntimeError(f"Pediatria=0: {pediatria_ok}; total antes={total1}, después={total2}")
        sectores_txt = ", ".join(f"{s}: {n}" for s, n in resumen1)
        return (f"Sectores iniciales -> {sectores_txt}\n"
                f"Al ocupar Hab {hab} / Cama {cama}, disponibles bajó de {total1} a {total2}.")
    return _probar_sql_ok(_run)


def _c1b_cama_inexistente():
    def _run(_cnx, cur):
        v_int = cur.var(int)
        cur.execute("""
            INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
            VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1001, '30333333')
            RETURNING id_internacion INTO :id""", id=v_int)
        id_int = int(v_int.getvalue()[0])
        cur.execute("""
            INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama, fecha_terminacion_cama)
            VALUES (:i, TIMESTAMP '2028-01-10 09:00:00', 102, 3, NULL)""", i=id_int)
    return _probar_sql_falla(2291, _run)


def _c2a_comentarios_ok():
    def _run(cnx, cur):
        with cnx.cursor() as c:
            cur.callproc("pr_comentarios_internacion", [1, "30111111", c])
            filas = c.fetchall()
        if len(filas) < 2:
            raise RuntimeError(f"Se esperaban >= 2 comentarios, devolvió {len(filas)}.")
        resumen = "\n".join(f"  • [{f[0]}] Turno {f[1]} - {f[2]}, {f[3]}: {f[4]}" for f in filas)
        return f"Devolvió {len(filas)} comentarios de Ana López (I1):\n{resumen}"
    return _probar_sql_ok(_run)


def _c2b_comentarios_dni_ajeno():
    def _run(cnx, cur):
        with cnx.cursor() as c:
            cur.callproc("pr_comentarios_internacion", [1, "30222222", c])
            filas = c.fetchall()
        if filas:
            raise RuntimeError(f"Devolvió {len(filas)} filas para un DNI ajeno.")
        return "Devolvió 0 filas: impide ver comentarios de otro paciente."
    return _probar_sql_ok(_run)


def _c3a_auditoria_ok():
    def _run(_cnx, cur):
        cur.execute("SELECT COUNT(*) FROM auditoria_guardias")
        antes = cur.fetchone()[0]

        cur.execute("UPDATE medico SET cantidad_guardias = cantidad_guardias + 1 WHERE matricula_medico = 1002")
        cur.execute("UPDATE posee SET hace_guardia = 'S' WHERE matricula_medico = 1001 AND nombre_especialidad = 'Cardiologia'")
        cur.execute("INSERT INTO vacacion VALUES (1003, TIMESTAMP '2028-03-01 00:00:00', TIMESTAMP '2028-03-10 23:59:59')")
        v_g = cur.var(int)
        cur.execute("""
            INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
            VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
            RETURNING id_guardia INTO :g""", g=v_g)
        id_g = int(v_g.getvalue()[0])
        cur.execute("INSERT INTO desempena VALUES (1002, 'Cardiologia', :g)", g=id_g)

        cur.execute("""
            SELECT tabla_afectada, operacion, clave_registro
              FROM auditoria_guardias
             ORDER BY id_auditoria DESC
             FETCH FIRST 5 ROWS ONLY""")
        nuevas = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM auditoria_guardias")
        despues = cur.fetchone()[0]
        if despues != antes + 5:
            raise RuntimeError(f"Esperaba +5 registros de auditoría, registró +{despues - antes}.")
        listado = "\n".join(f"  • {t} [{op}] -> {cl}" for t, op, cl in reversed(nuevas))
        return f"Se registraron 5 eventos automáticamente (+5):\n{listado}"
    return _probar_sql_ok(_run)


def _c3b_auditoria_rollback():
    try:
        aud_antes = db.consultar("SELECT COUNT(*) FROM auditoria_guardias")[0][0]
        g_antes = db.consultar("SELECT COUNT(*) FROM guardia")[0][0]
        try:
            db.alta_guardia(1001, "Clinica Medica", date(2026, 11, 25), [1])
            return False, "No disparó error: permitió guardia durante vacaciones."
        except db.ErrorTrigger as e:
            aud_desp = db.consultar("SELECT COUNT(*) FROM auditoria_guardias")[0][0]
            g_desp = db.consultar("SELECT COUNT(*) FROM guardia")[0][0]
            if e.codigo == 20003 and aud_antes == aud_desp and g_antes == g_desp:
                return True, (
                    f"db.alta_guardia() fue frenado por ORA-{e.codigo}: \"{e}\"\n"
                    f"ROLLBACK verificado: GUARDIA ({g_antes} -> {g_desp}) y "
                    f"AUDITORIA_GUARDIAS ({aud_antes} -> {aud_desp}) quedaron intactas.")
            return False, f"Inconsistencia: code={e.codigo}, G={g_antes}->{g_desp}, AUD={aud_antes}->{aud_desp}"
    except Exception as e:
        return False, f"Error inesperado: {e}"


def _c4a_med_pac_ok():
    def _run(_cnx, cur):
        cur.execute("""
            INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
            VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1001, '24444444')""")
        return "Internación del Dr. Díaz (DNI 24444444) con la Dra. Gómez (mat. 1001) aceptada."
    return _probar_sql_ok(_run)


def _c4b_med_pac_fail():
    try:
        db.internar("24444444", 1004, 101, 1)
        return False, "No falló: permitió que el Dr. Díaz sea su propio médico principal."
    except db.ErrorTrigger as e:
        if e.codigo == 20001:
            return True, f"Rechazado vía db.internar() por trigger ORA-{e.codigo}:\n\"{e}\"\n(ROLLBACK automático aplicado.)"
        return False, f"Se esperaba ORA-20001, devolvió ORA-{e.codigo}: {e}"
    except Exception as e:
        return False, f"Error inesperado: {e}"


def _c5a_guardia_ok():
    def _run(_cnx, cur):
        v_g = cur.var(int)
        cur.execute("""
            INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
            VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
            RETURNING id_guardia INTO :g""", g=v_g)
        id_g = int(v_g.getvalue()[0])
        cur.execute("INSERT INTO guardia_turno_manana VALUES (:g)", g=id_g)
        cur.execute("INSERT INTO desempena VALUES (1002, 'Cardiologia', :g)", g=id_g)
        return "Guardia 2028-05-10 (06:00-14:00) asignada a médico 1002 en Cardiología."
    return _probar_sql_ok(_run)


def _c5b_guardia_no_hace():
    def _run(_cnx, cur):
        v_g = cur.var(int)
        cur.execute("""
            INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
            VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
            RETURNING id_guardia INTO :g""", g=v_g)
        cur.execute("INSERT INTO desempena VALUES (1001, 'Cardiologia', :g)", g=int(v_g.getvalue()[0]))
    return _probar_sql_falla(20002, _run)


def _c5c_guardia_vacaciones():
    def _run(_cnx, cur):
        v_g = cur.var(int)
        cur.execute("""
            INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
            VALUES (TIMESTAMP '2026-11-25 06:00:00', TIMESTAMP '2026-11-25 14:00:00')
            RETURNING id_guardia INTO :g""", g=v_g)
        cur.execute("INSERT INTO desempena VALUES (1001, 'Clinica Medica', :g)", g=int(v_g.getvalue()[0]))
    return _probar_sql_falla(20003, _run)


def _c5d_guardia_internado():
    def _run(_cnx, cur):
        v_g = cur.var(int)
        cur.execute("""
            INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
            VALUES (TIMESTAMP '2026-10-15 06:00:00', TIMESTAMP '2026-10-15 14:00:00')
            RETURNING id_guardia INTO :g""", g=v_g)
        cur.execute("INSERT INTO desempena VALUES (1004, 'Clinica Medica', :g)", g=int(v_g.getvalue()[0]))
    return _probar_sql_falla(20004, _run)


def _c5e_guardia_tope():
    try:
        db.alta_guardia(1004, "Clinica Medica", date(2026, 11, 15), [1])
        return False, "No falló: permitió superar el tope mensual (2) del Dr. 1004."
    except db.ErrorTrigger as e:
        if e.codigo == 20005:
            return True, f"Rechazado vía db.alta_guardia() por trigger ORA-{e.codigo}:\n\"{e}\"\n(ROLLBACK automático aplicado.)"
        return False, f"Se esperaba ORA-20005, devolvió ORA-{e.codigo}: {e}"
    except Exception as e:
        return False, f"Error inesperado: {e}"


def _c6a_vacacion_ok():
    def _run(_cnx, cur):
        cur.execute("INSERT INTO vacacion VALUES (1003, TIMESTAMP '2028-03-01 00:00:00', TIMESTAMP '2028-03-15 23:59:59')")
        return "Vacaciones 2028-03-01..2028-03-15 para médico 1003 aceptadas."
    return _probar_sql_ok(_run)


def _c6b_vacacion_solapa():
    def _run(_cnx, cur):
        cur.execute("INSERT INTO vacacion VALUES (1001, TIMESTAMP '2026-11-25 00:00:00', TIMESTAMP '2026-12-10 23:59:59')")
    return _probar_sql_falla(20006, _run)


def _c7a_comentario_ok():
    def _run(_cnx, cur):
        cur.execute("""
            INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
            VALUES (1, 2, 'Comentario válido de prueba.')""")
        return "Comentario en I1 / Recorrido 2 (Hab 101 en Ronda 1) aceptado."
    return _probar_sql_ok(_run)


def _c7b_comentario_propio():
    def _run(_cnx, cur):
        v_rec = cur.var(int)
        cur.execute("""
            INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido)
            VALUES (2, 1004, TIMESTAMP '2026-10-15 10:00:00')
            RETURNING id_recorrido INTO :r""", r=v_rec)
        cur.execute("""
            INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
            VALUES (5, :r, 'Auto-comentario prohibido.')""", r=int(v_rec.getvalue()[0]))
    return _probar_sql_falla(20007, _run)


def _c7c_comentario_fecha():
    def _run(_cnx, cur):
        cur.execute("""
            INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
            VALUES (3, 2, 'Comentario fuera del rango de la internación.')""")
    return _probar_sql_falla(20008, _run)


def _c7d_comentario_ronda():
    def _run(_cnx, cur):
        cur.execute("""
            INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
            VALUES (1, 3, 'Paciente no estaba en habitación de la ronda 2.')""")
    return _probar_sql_falla(20009, _run)


def _c8a_ocupa_ok():
    def _run(_cnx, cur):
        v_int = cur.var(int)
        cur.execute("""
            INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
            VALUES (TIMESTAMP '2028-02-01 08:00:00', TIMESTAMP '2028-02-10 12:00:00', 1001, '30333333')
            RETURNING id_internacion INTO :i""", i=v_int)
        id_i = int(v_int.getvalue()[0])
        cur.execute("INSERT INTO ocupa VALUES (:i, TIMESTAMP '2028-02-01 08:00:00', 101, 1, TIMESTAMP '2028-02-04 10:00:00')", i=id_i)
        cur.execute("INSERT INTO ocupa VALUES (:i, TIMESTAMP '2028-02-04 10:00:00', 101, 2, TIMESTAMP '2028-02-07 10:00:00')", i=id_i)
        cur.execute("INSERT INTO ocupa VALUES (:i, TIMESTAMP '2028-02-07 10:00:00', 101, 1, TIMESTAMP '2028-02-10 12:00:00')", i=id_i)
        return "Secuencia 101-1 -> 101-2 -> 101-1 (repitiendo cama sin solapamiento) aceptada."
    return _probar_sql_ok(_run)


def _c8b_ocupa_rango():
    def _run(_cnx, cur):
        cur.execute("INSERT INTO ocupa VALUES (4, TIMESTAMP '2026-09-09 08:00:00', 201, 2, TIMESTAMP '2026-09-10 08:00:00')")
    return _probar_sql_falla(20010, _run)


def _c8c_ocupa_cama_ocupada():
    def _run(_cnx, cur):
        v_int = cur.var(int)
        cur.execute("""
            INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
            VALUES (TIMESTAMP '2026-10-12 08:00:00', TIMESTAMP '2026-10-15 12:00:00', 1002, '30444444')
            RETURNING id_internacion INTO :i""", i=v_int)
        cur.execute(
            "INSERT INTO ocupa VALUES (:i, TIMESTAMP '2026-10-12 09:00:00', 302, 1, TIMESTAMP '2026-10-15 12:00:00')",
            i=int(v_int.getvalue()[0]))
    return _probar_sql_falla(20011, _run)


def _c8d_ocupa_dos_camas():
    def _run(_cnx, cur):
        cur.execute("INSERT INTO ocupa VALUES (4, TIMESTAMP '2026-09-11 09:00:00', 201, 2, TIMESTAMP '2026-09-12 09:00:00')")
    return _probar_sql_falla(20012, _run)


def _c9a_recorrido_ok():
    def _run(_cnx, cur):
        cur.execute("INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido) VALUES (1, 1001, TIMESTAMP '2026-11-10 10:00:00')")
        return "Recorrido del médico 1001 el 2026-11-10 (fuera de vacaciones) aceptado."
    return _probar_sql_ok(_run)


def _c9b_recorrido_vacaciones():
    def _run(_cnx, cur):
        cur.execute("INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido) VALUES (1, 1001, TIMESTAMP '2026-11-25 10:00:00')")
    return _probar_sql_falla(20013, _run)


def _c10a_cambio_guardia_ok():
    def _run(_cnx, cur):
        cur.execute("""
            UPDATE guardia
               SET fecha_inicio_guardia = TIMESTAMP '2026-11-12 06:00:00',
                   fecha_fin_guardia    = TIMESTAMP '2026-11-12 14:00:00'
             WHERE id_guardia = 1""")
        return "Guardia 1 (médico 1001) reprogramada del 2026-11-02 al 2026-11-12 sin conflictos."
    return _probar_sql_ok(_run)


def _c10b_cambio_guardia_vac():
    def _run(_cnx, cur):
        cur.execute("""
            UPDATE guardia
               SET fecha_inicio_guardia = TIMESTAMP '2026-11-25 06:00:00',
                   fecha_fin_guardia    = TIMESTAMP '2026-11-25 14:00:00'
             WHERE id_guardia = 1""")
    return _probar_sql_falla(20003, _run)


def _c10c_cambio_guardia_int():
    def _run(_cnx, cur):
        cur.execute("""
            UPDATE guardia
               SET fecha_inicio_guardia = TIMESTAMP '2026-10-15 14:00:00',
                   fecha_fin_guardia    = TIMESTAMP '2026-10-15 22:00:00'
             WHERE id_guardia = 2""")
    return _probar_sql_falla(20004, _run)


def _c10d_cambio_guardia_tope():
    def _run(_cnx, cur):
        v_g = cur.var(int)
        cur.execute("""
            INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
            VALUES (TIMESTAMP '2028-06-05 06:00:00', TIMESTAMP '2028-06-05 14:00:00')
            RETURNING id_guardia INTO :g""", g=v_g)
        id_g = int(v_g.getvalue()[0])
        cur.execute("INSERT INTO desempena VALUES (1004, 'Clinica Medica', :g)", g=id_g)
        cur.execute("""
            UPDATE guardia
               SET fecha_inicio_guardia = TIMESTAMP '2026-11-15 06:00:00',
                   fecha_fin_guardia    = TIMESTAMP '2026-11-15 14:00:00'
             WHERE id_guardia = :g""", g=id_g)
    return _probar_sql_falla(20005, _run)


CASOS: list[CasoPrueba] = [
    CasoPrueba(
        "1A", "1. Procedure camas", "OK",
        "Camas disponibles (sector en 0 + baja al ocupar)",
        "OK (total - 1)",
        "Llama a pr_camas_disponibles, verifica que Pediatría aparezca con 0 camas y que al ocupar una cama libre el total baje en 1.",
        "CALL pr_camas_disponibles(:cant, :det); INSERT internacion + ocupa; CALL pr_camas_disponibles(...);",
        _c1a_camas_ok),
    CasoPrueba(
        "1B", "1. Procedure camas", "FALLA",
        "Ocupar cama inexistente 102-3 (numeración con hueco)",
        "ORA-02291",
        "La habitación 102 tiene camas 1, 2 y 4 (sin cama 3). Intentar ocupar 102-3 debe fallar por FK fk_ocupa_cama.",
        "INSERT INTO ocupa (..., nro_habitacion=102, nro_cama=3, ...);",
        _c1b_cama_inexistente),
    CasoPrueba(
        "2A", "2. Procedure comentarios", "OK",
        "Comentarios de internación con DNI correcto",
        "OK (>= 2 filas)",
        "Llama a pr_comentarios_internacion(1, '30111111') para Ana López y devuelve sus comentarios con fecha, turno y médico.",
        "CALL pr_comentarios_internacion(1, '30111111', :cur);",
        _c2a_comentarios_ok),
    CasoPrueba(
        "2B", "2. Procedure comentarios", "FALLA",
        "Comentarios de internación con DNI de otro paciente",
        "0 filas",
        "Llama a pr_comentarios_internacion(1, '30222222'): como I1 no pertenece a ese DNI, debe devolver cursor vacío.",
        "CALL pr_comentarios_internacion(1, '30222222', :cur);",
        _c2b_comentarios_dni_ajeno),
    CasoPrueba(
        "3A", "3. Auditoría y TX", "OK",
        "Disparo de los 5 triggers de auditoría",
        "OK (+5 filas)",
        "Modifica MEDICO, POSEE, VACACION, GUARDIA y DESEMPENA y comprueba que se graban exactamente 5 filas en auditoria_guardias.",
        "UPDATE medico; UPDATE posee; INSERT vacacion; INSERT guardia; INSERT desempena;",
        _c3a_auditoria_ok),
    CasoPrueba(
        "3B", "3. Auditoría y TX", "FALLA",
        "Atomicidad: db.alta_guardia() falla y hace ROLLBACK total",
        "ORA-20003 + 0 huérf.",
        "Llama directo a db.alta_guardia(1001, 'Clinica Medica', 2026-11-25, [1]). Falla en DESEMPENA y revierte GUARDIA y su auditoría.",
        "db.alta_guardia(1001, 'Clinica Medica', 2026-11-25, [1]) -> ROLLBACK",
        _c3b_auditoria_rollback),
    CasoPrueba(
        "4A", "4. Trg médico-paciente", "OK",
        "Médico internado atendido por otro médico principal",
        "OK",
        "Interna al Dr. Díaz (DNI 24444444) designando a la Dra. Gómez (mat. 1001) como médico principal.",
        "INSERT INTO internacion (..., matricula_medico=1001, dni='24444444');",
        _c4a_med_pac_ok),
    CasoPrueba(
        "4B", "4. Trg médico-paciente", "FALLA",
        "Médico como su propio médico principal (vía db.internar)",
        "ORA-20001",
        "Llama a db.internar('24444444', 1004, 101, 1). Debe disparar trg_internacion_medico_paciente (ORA-20001).",
        "db.internar(dni='24444444', matricula=1004, nro_hab=101, nro_cama=1)",
        _c4b_med_pac_fail),
    CasoPrueba(
        "5A", "5. Trg asignación guardia", "OK",
        "Guardia válida (hace_guardia='S', sin conflictos)",
        "OK",
        "Asigna al médico 1002 en Cardiología el 2028-05-10 (06:00-14:00), respetando todas las reglas.",
        "INSERT guardia (2028-05-10 06:00..14:00); INSERT desempena (1002, 'Cardiologia', :g);",
        _c5a_guardia_ok),
    CasoPrueba(
        "5B", "5. Trg asignación guardia", "FALLA",
        "Especialidad con hace_guardia = 'N'",
        "ORA-20002",
        "La Dra. 1001 tiene Cardiología pero con hace_guardia = 'N'. Debe disparar ORA-20002.",
        "INSERT desempena (1001, 'Cardiologia', :g);",
        _c5b_guardia_no_hace),
    CasoPrueba(
        "5C", "5. Trg asignación guardia", "FALLA",
        "Guardia durante vacaciones del médico",
        "ORA-20003",
        "La Dra. 1001 está de vacaciones del 2026-11-20 al 2026-12-04. Asignarla el 2026-11-25 dispara ORA-20003.",
        "INSERT guardia (2026-11-25 06:00..14:00); INSERT desempena (1001, 'Clinica Medica', :g);",
        _c5c_guardia_vacaciones),
    CasoPrueba(
        "5D", "5. Trg asignación guardia", "FALLA",
        "Guardia mientras el médico está internado como paciente",
        "ORA-20004",
        "El Dr. 1004 estuvo internado del 2026-10-10 al 2026-10-20 (I5). Asignarle guardia el 2026-10-15 dispara ORA-20004.",
        "INSERT guardia (2026-10-15 06:00..14:00); INSERT desempena (1004, 'Clinica Medica', :g);",
        _c5d_guardia_internado),
    CasoPrueba(
        "5E", "5. Trg asignación guardia", "FALLA",
        "Supera tope mensual de guardias (vía db.alta_guardia)",
        "ORA-20005",
        "El Dr. 1004 tiene tope=2 y ya posee 2 guardias en nov-2026. Una 3ª vía db.alta_guardia dispara ORA-20005.",
        "db.alta_guardia(1004, 'Clinica Medica', 2026-11-15, [1])",
        _c5e_guardia_tope),
    CasoPrueba(
        "6A", "6. Trg vacaciones", "OK",
        "Nuevo período de vacaciones sin superposición",
        "OK",
        "Registra vacaciones para la Dra. 1003 en marzo 2028 (sin solapamiento).",
        "INSERT INTO vacacion VALUES (1003, 2028-03-01, 2028-03-15);",
        _c6a_vacacion_ok),
    CasoPrueba(
        "6B", "6. Trg vacaciones", "FALLA",
        "Período de vacaciones superpuesto del mismo médico",
        "ORA-20006",
        "La Dra. 1001 ya tiene vacaciones 2026-11-20..2026-12-04. Insertar 2026-11-25..2026-12-10 dispara ORA-20006.",
        "INSERT INTO vacacion VALUES (1001, 2026-11-25, 2026-12-10);",
        _c6b_vacacion_solapa),
    CasoPrueba(
        "7A", "7. Trg comentario", "OK",
        "Comentario válido (paciente en habitación de la ronda)",
        "OK",
        "Registra comentario sobre I1 en recorrido 2 (ronda 1 visita hab 101, donde Ana estaba el 2026-10-20 16:00).",
        "INSERT INTO comentario (id_internacion=1, id_recorrido=2, texto='...');",
        _c7a_comentario_ok),
    CasoPrueba(
        "7B", "7. Trg comentario", "FALLA",
        "Médico comenta su propia internación",
        "ORA-20007",
        "Crea recorrido del Dr. 1004 el 2026-10-15 y trata de comentar sobre I5 (propia internación del Dr. 1004).",
        "INSERT recorrido (ronda=2, med=1004, 2026-10-15); INSERT comentario (I5, :rec, '...');",
        _c7b_comentario_propio),
    CasoPrueba(
        "7C", "7. Trg comentario", "FALLA",
        "Recorrido fuera del período de la internación",
        "ORA-20008",
        "I3 terminó el 2026-10-08; el recorrido 2 es del 2026-10-20. Debe disparar ORA-20008.",
        "INSERT INTO comentario (id_internacion=3, id_recorrido=2, texto='...');",
        _c7c_comentario_fecha),
    CasoPrueba(
        "7D", "7. Trg comentario", "FALLA",
        "Paciente en habitación que no pertenece a la ronda",
        "ORA-20009",
        "El 2026-10-21 I1 ocupaba hab 101, pero el recorrido 3 (ronda 2) solo visita 301 y 302. Dispara ORA-20009.",
        "INSERT INTO comentario (id_internacion=1, id_recorrido=3, texto='...');",
        _c7d_comentario_ronda),
    CasoPrueba(
        "8A", "8. Trg ocupa camas", "OK",
        "Cambio y repetición de cama dentro de la internación",
        "OK",
        "Paciente pasa 101-1 -> 101-2 -> 101-1 sin solapar intervalos y dentro de las fechas de su internación.",
        "INSERT internacion (2028-02-01..10); INSERT ocupa 101-1 -> 101-2 -> 101-1;",
        _c8a_ocupa_ok),
    CasoPrueba(
        "8B", "8. Trg ocupa camas", "FALLA",
        "Ocupación fuera del rango de fechas de la internación",
        "ORA-20010",
        "I4 comienza el 2026-09-10 09:00; intentar ocupar una cama el 2026-09-09 dispara ORA-20010.",
        "INSERT INTO ocupa VALUES (4, 2026-09-09 08:00, 201, 2, 2026-09-10 08:00);",
        _c8b_ocupa_rango),
    CasoPrueba(
        "8C", "8. Trg ocupa camas", "FALLA",
        "Cama ya ocupada por otro paciente en ese intervalo",
        "ORA-20011",
        "La cama 302-1 fue ocupada por I5 del 2026-10-10 al 2026-10-20. Asignarla a otra internación el 10-12 dispara ORA-20011.",
        "INSERT internacion (10-12..10-15); INSERT ocupa (..., 302, 1, 10-12..10-15);",
        _c8c_ocupa_cama_ocupada),
    CasoPrueba(
        "8D", "8. Trg ocupa camas", "FALLA",
        "Un mismo internado ocupando dos camas simultáneamente",
        "ORA-20012",
        "I4 ya ocupa 201-1 del 2026-09-10 al 2026-09-15; asignarle además 201-2 el 09-11 dispara ORA-20012.",
        "INSERT INTO ocupa VALUES (4, 2026-09-11 09:00, 201, 2, 2026-09-12 09:00);",
        _c8d_ocupa_dos_camas),
    CasoPrueba(
        "9A", "9. Trg recorrido", "OK",
        "Recorrido fuera de vacaciones del médico",
        "OK",
        "La Dra. 1001 realiza un recorrido el 2026-11-10 (fuera de su período de vacaciones).",
        "INSERT INTO recorrido (id_ronda=1, matricula=1001, fecha=2026-11-10);",
        _c9a_recorrido_ok),
    CasoPrueba(
        "9B", "9. Trg recorrido", "FALLA",
        "Recorrido durante vacaciones del médico",
        "ORA-20013",
        "La Dra. 1001 está de vacaciones el 2026-11-25. Insertar un recorrido en esa fecha dispara ORA-20013.",
        "INSERT INTO recorrido (id_ronda=1, matricula=1001, fecha=2026-11-25);",
        _c9b_recorrido_vacaciones),
    CasoPrueba(
        "10A", "10. Trg cambio guardia", "OK",
        "Reprogramar guardia a otra fecha válida del mismo mes",
        "OK",
        "Mueve la guardia 1 (asignada a 1001) del 2026-11-02 al 2026-11-12 sin conflictos.",
        "UPDATE guardia SET inicio=2026-11-12 06:00, fin=14:00 WHERE id_guardia=1;",
        _c10a_cambio_guardia_ok),
    CasoPrueba(
        "10B", "10. Trg cambio guardia", "FALLA",
        "Reprogramar guardia a vacaciones del médico asignado",
        "ORA-20003",
        "Mueve la guardia 1 (médico 1001) al 2026-11-25 (en sus vacaciones). Dispara ORA-20003.",
        "UPDATE guardia SET inicio=2026-11-25 06:00, fin=14:00 WHERE id_guardia=1;",
        _c10b_cambio_guardia_vac),
    CasoPrueba(
        "10C", "10. Trg cambio guardia", "FALLA",
        "Reprogramar guardia a internación del médico asignado",
        "ORA-20004",
        "Mueve la guardia 2 (asignada a 1004) al 2026-10-15 (durante su internación I5). Dispara ORA-20004.",
        "UPDATE guardia SET inicio=2026-10-15 14:00, fin=22:00 WHERE id_guardia=2;",
        _c10c_cambio_guardia_int),
    CasoPrueba(
        "10D", "10. Trg cambio guardia", "FALLA",
        "Reprogramar guardia a otro mes superando tope mensual",
        "ORA-20005",
        "Crea una guardia en junio 2028 para el Dr. 1004 y la mueve a nov-2026 donde ya tiene 2/2. Dispara ORA-20005.",
        "INSERT guardia+desempena (2028-06, 1004); UPDATE guardia SET inicio=2026-11-15;",
        _c10d_cambio_guardia_tope),
]


# ---------------------------------------------------------------------------
# Panel interactivo Tkinter (se puede embeber en app.py o abrir standalone)
# ---------------------------------------------------------------------------
class PanelPruebas(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.resultados: dict[str, tuple[Optional[bool], str]] = {}
        self._construir_ui()

    def _construir_ui(self):
        barra = ttk.Frame(self)
        barra.pack(fill="x", padx=10, pady=8)

        ttk.Button(barra, text="Ejecutar seleccionada",
                   command=self.ejecutar_seleccionada).pack(side="left", padx=4)
        ttk.Button(barra, text="Ejecutar grupo",
                   command=self.ejecutar_grupo).pack(side="left", padx=4)
        ttk.Button(barra, text="Ejecutar toda la batería",
                   command=self.ejecutar_todas).pack(side="left", padx=4)
        ttk.Button(barra, text="Limpiar",
                   command=self.limpiar).pack(side="left", padx=4)

        self.lbl_resumen = ttk.Label(
            barra, text=f"0 / {len(CASOS)} ejecutadas (cada prueba hace ROLLBACK automático)")
        self.lbl_resumen.pack(side="right", padx=6)

        marco_tabla = ttk.Frame(self)
        marco_tabla.pack(expand=True, fill="both", padx=10)

        cols = ("codigo", "grupo", "tipo", "caso", "esperado", "estado")
        self.tabla = ttk.Treeview(marco_tabla, columns=cols, show="headings", height=14)
        anchos = {"codigo": 55, "grupo": 175, "tipo": 65, "caso": 370, "esperado": 130, "estado": 90}
        titulos = {"codigo": "#", "grupo": "Grupo / Requerimiento", "tipo": "Tipo",
                   "caso": "Caso de prueba", "esperado": "Esperado", "estado": "Estado"}
        for c in cols:
            self.tabla.heading(c, text=titulos[c])
            self.tabla.column(c, width=anchos[c], anchor="center" if c in ("codigo", "tipo", "estado") else "w")

        self.tabla.tag_configure("pass", background="#dff5e1")
        self.tabla.tag_configure("fail", background="#fadbd8")
        self.tabla.tag_configure("pend", background="")

        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", expand=True, fill="both")
        scroll.pack(side="right", fill="y")

        self.tabla.bind("<<TreeviewSelect>>", self._mostrar_detalle)
        self.tabla.bind("<Double-1>", lambda _e: self.ejecutar_seleccionada())

        marco_det = ttk.LabelFrame(self, text="Detalle del caso (doble clic en una fila para ejecutarla)")
        marco_det.pack(fill="x", padx=10, pady=8)
        self.txt_detalle = tk.Text(marco_det, height=8, wrap="word", state="disabled", font=("Consolas", 9))
        self.txt_detalle.pack(fill="both", expand=True, padx=6, pady=4)

        self._cargar_filas()

    def _cargar_filas(self):
        self.tabla.delete(*self.tabla.get_children())
        for c in CASOS:
            self.tabla.insert("", "end", iid=c.codigo,
                              values=(c.codigo, c.grupo, c.tipo, c.nombre, c.esperado, "Pendiente"),
                              tags=("pend",))

    def _caso_por_id(self, codigo) -> Optional[CasoPrueba]:
        for c in CASOS:
            if c.codigo == codigo:
                return c
        return None

    def _correr_caso(self, caso: CasoPrueba):
        ok, detalle = caso.ejecutor()
        self.resultados[caso.codigo] = (ok, detalle)
        estado = "PASS" if ok else "FAIL"
        tag = "pass" if ok else "fail"
        self.tabla.item(
            caso.codigo,
            values=(caso.codigo, caso.grupo, caso.tipo, caso.nombre, caso.esperado, estado),
            tags=(tag,))

    def _actualizar_resumen(self):
        ejecutadas = len(self.resultados)
        ok_n = sum(1 for ok, _ in self.resultados.values() if ok)
        fail_n = ejecutadas - ok_n
        self.lbl_resumen.config(
            text=f"Ejecutadas: {ejecutadas}/{len(CASOS)} | PASS: {ok_n} | FAIL: {fail_n} (base intacta con ROLLBACK)")

    def _mostrar_detalle(self, _event=None):
        sel = self.tabla.selection()
        if not sel:
            return
        caso = self._caso_por_id(sel[0])
        if not caso:
            return
        res = self.resultados.get(caso.codigo)
        lineas = [
            f"[{caso.codigo}] {caso.grupo} — {caso.nombre} ({caso.tipo})",
            f"Descripción: {caso.descripcion}",
            f"Operación  : {caso.sql_resumen}",
            f"Esperado   : {caso.esperado}",
            "-" * 80,
        ]
        if res is None:
            lineas.append("Estado: Pendiente (hacé doble clic o presioná 'Ejecutar seleccionada').")
        else:
            ok, detalle = res
            lineas.append(f"Resultado: {'PASS' if ok else 'FAIL'}")
            lineas.append(detalle)

        self.txt_detalle.config(state="normal")
        self.txt_detalle.delete("1.0", "end")
        self.txt_detalle.insert("1.0", "\n".join(lineas))
        self.txt_detalle.config(state="disabled")

    def ejecutar_seleccionada(self):
        sel = self.tabla.selection()
        if not sel:
            self.tabla.selection_set(CASOS[0].codigo)
            sel = (CASOS[0].codigo,)
        caso = self._caso_por_id(sel[0])
        if caso:
            self._correr_caso(caso)
            self._actualizar_resumen()
            self._mostrar_detalle()

    def ejecutar_grupo(self):
        sel = self.tabla.selection()
        if not sel:
            self.tabla.selection_set(CASOS[0].codigo)
            sel = (CASOS[0].codigo,)
        actual = self._caso_por_id(sel[0])
        if not actual:
            return
        for c in CASOS:
            if c.grupo == actual.grupo:
                self._correr_caso(c)
                self.update_idletasks()
        self._actualizar_resumen()
        self._mostrar_detalle()

    def ejecutar_todas(self):
        for c in CASOS:
            self._correr_caso(c)
            self.update_idletasks()
        self._actualizar_resumen()
        if not self.tabla.selection():
            self.tabla.selection_set(CASOS[0].codigo)
        self._mostrar_detalle()

    def limpiar(self):
        self.resultados.clear()
        self._cargar_filas()
        self.lbl_resumen.config(
            text=f"0 / {len(CASOS)} ejecutadas (cada prueba hace ROLLBACK automático)")
        self.txt_detalle.config(state="normal")
        self.txt_detalle.delete("1.0", "end")
        self.txt_detalle.config(state="disabled")


if __name__ == "__main__":
    ventana = tk.Tk()
    ventana.title("Hospital - Batería de pruebas")
    ventana.geometry("1120x680")
    PanelPruebas(ventana).pack(expand=True, fill="both")
    ventana.mainloop()
