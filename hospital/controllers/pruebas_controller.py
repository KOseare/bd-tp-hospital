"""Controlador de la batería interactiva de pruebas (42 casos sobre Oracle con ROLLBACK).

Separa la lógica de los casos de prueba (antes mezclada con Tkinter en `pruebas.py`)
de la vista `PruebasView`. Cada caso revierte con ROLLBACK para dejar intactos los
datos precargados de `02_inserts.sql`.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable

import oracledb

from hospital.controllers.guardia_controller import GuardiaController
from hospital.controllers.internacion_controller import InternacionController
from hospital.controllers.medico_controller import MedicoController
from hospital.controllers.paciente_controller import PacienteController
from hospital.controllers.reportes_controller import ReportesController
from hospital.controllers.ronda_controller import RondaController
from hospital.models.entities import CasoPrueba
from hospital.models.exceptions import AppError, ErrorConcurrencia, ErrorTrigger, ReglaError
from hospital.persistence import pruebas_dao
from hospital.persistence.connection import ConnectionManager


def _limpiar_ora(exc: Exception) -> tuple[int | None, str]:
    err = exc.args[0] if getattr(exc, "args", None) else None
    code = getattr(err, "code", None)
    primera = (getattr(err, "message", None) or str(exc)).strip().splitlines()[0]
    texto = re.sub(r"^ORA-\d+:\s*", "", primera).strip()
    return code, texto


class PruebasController:
    """Construye y ejecuta los 42 casos de prueba contra Oracle sin acoplamiento a Tkinter."""

    def __init__(
        self,
        db: ConnectionManager,
        internacion_ctrl: InternacionController,
        guardia_ctrl: GuardiaController,
        reportes_ctrl: ReportesController,
        ronda_ctrl: RondaController | None = None,
        paciente_ctrl: PacienteController | None = None,
        medico_ctrl: MedicoController | None = None,
    ) -> None:
        self._db = db
        self._internaciones = internacion_ctrl
        self._guardias = guardia_ctrl
        self._reportes = reportes_ctrl
        self._rondas = ronda_ctrl or RondaController(db)
        self._pacientes = paciente_ctrl or PacienteController(db)
        self._medicos = medico_ctrl or MedicoController(db)
        self._casos = self._construir_casos()

    @property
    def casos(self) -> list[CasoPrueba]:
        return list(self._casos)

    def obtener_caso(self, codigo: str) -> CasoPrueba | None:
        for c in self._casos:
            if c.codigo == codigo:
                return c
        return None

    def ejecutar_caso(self, caso: CasoPrueba) -> tuple[bool, str]:
        return caso.ejecutor()

    def _probar_sql_ok(self, fn: Callable[[Any, Any], str]) -> tuple[bool, str]:
        try:
            detalle = pruebas_dao.ejecutar_en_rollback(self._db, fn)
            return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
        except oracledb.Error as e:
            code, msg = _limpiar_ora(e)
            return False, f"Falló inesperadamente con ORA-{code}: {msg}"
        except AppError as e:
            return False, f"Falló inesperadamente: {e}"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _probar_sql_falla(
        self,
        codigo_esperado: int,
        fn: Callable[[Any, Any], Any],
    ) -> tuple[bool, str]:
        try:
            pruebas_dao.ejecutar_en_rollback(self._db, fn)
            return (
                False,
                f"NO falló: la base aceptó la operación cuando se esperaba ORA-{codigo_esperado:05d}.",
            )
        except oracledb.DatabaseError as e:
            code, msg = _limpiar_ora(e)
            if code == codigo_esperado:
                return (
                    True,
                    f"Rechazado correctamente por Oracle (ORA-{code:05d}):\n\"{msg}\"\n(ROLLBACK aplicado.)",
                )
            return (
                False,
                f"Se esperaba ORA-{codigo_esperado:05d}, pero devolvió ORA-{code}: {msg}",
            )
        except Exception as e:
            return False, f"Error inesperado: {e}"

    # ------------------------------------------------------------------
    # Casos de prueba (1A..10D)
    # ------------------------------------------------------------------
    def _c1a_camas_ok(self) -> tuple[bool, str]:
        def _run(cnx: Any, cur: Any) -> str:
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
            cur.execute(
                """
                INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
                VALUES (SYSTIMESTAMP - INTERVAL '1' MINUTE, NULL, 1001, '30333333')
                RETURNING id_internacion INTO :id
                """,
                id=v_int,
            )
            id_int = int(v_int.getvalue()[0])
            cur.execute(
                """
                INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama, fecha_terminacion_cama)
                VALUES (:i, SYSTIMESTAMP - INTERVAL '1' MINUTE, :h, :c, NULL)
                """,
                i=id_int,
                h=hab,
                c=cama,
            )

            with cnx.cursor() as c1, cnx.cursor() as c2:
                cur.callproc("pr_camas_disponibles", [c1, c2])
                resumen2 = c1.fetchall()
                _ = c2.fetchall()
            total2 = sum(cant for _, cant in resumen2)

            if not pediatria_ok or total2 != total1 - 1:
                raise RuntimeError(
                    f"Pediatria=0: {pediatria_ok}; total antes={total1}, después={total2}"
                )
            sectores_txt = ", ".join(f"{s}: {n}" for s, n in resumen1)
            return (
                f"Sectores iniciales -> {sectores_txt}\n"
                f"Al ocupar Hab {hab} / Cama {cama}, disponibles bajó de {total1} a {total2}."
            )

        return self._probar_sql_ok(_run)

    def _c1b_cama_inexistente(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_int = cur.var(int)
            cur.execute(
                """
                INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
                VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1001, '30333333')
                RETURNING id_internacion INTO :id
                """,
                id=v_int,
            )
            id_int = int(v_int.getvalue()[0])
            cur.execute(
                """
                INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama, fecha_terminacion_cama)
                VALUES (:i, TIMESTAMP '2028-01-10 09:00:00', 102, 3, NULL)
                """,
                i=id_int,
            )

        return self._probar_sql_falla(2291, _run)

    def _c2a_comentarios_ok(self) -> tuple[bool, str]:
        def _run(cnx: Any, cur: Any) -> str:
            with cnx.cursor() as c:
                cur.callproc("pr_comentarios_internacion", [1, "30111111", c])
                filas = c.fetchall()
            if len(filas) < 2:
                raise RuntimeError(f"Se esperaban >= 2 comentarios, devolvió {len(filas)}.")
            resumen = "\n".join(
                f"  - [{f[0]}] Turno {f[1]} - {f[2]}, {f[3]}: {f[4]}" for f in filas
            )
            return f"Devolvió {len(filas)} comentarios de Ana López (I1):\n{resumen}"

        return self._probar_sql_ok(_run)

    def _c2b_comentarios_dni_ajeno(self) -> tuple[bool, str]:
        def _run(cnx: Any, cur: Any) -> str:
            with cnx.cursor() as c:
                cur.callproc("pr_comentarios_internacion", [1, "30222222", c])
                filas = c.fetchall()
            if filas:
                raise RuntimeError(f"Devolvió {len(filas)} filas para un DNI ajeno.")
            return "Devolvió 0 filas: impide ver comentarios de otro paciente."

        return self._probar_sql_ok(_run)

    def _c3a_auditoria_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            cur.execute("SELECT COUNT(*) FROM auditoria_guardias")
            antes = int(cur.fetchone()[0])

            cur.execute(
                "UPDATE medico SET cantidad_guardias = cantidad_guardias + 1 WHERE matricula_medico = 1002"
            )
            cur.execute(
                "UPDATE posee SET hace_guardia = 'S' WHERE matricula_medico = 1001 AND nombre_especialidad = 'Cardiologia'"
            )
            cur.execute(
                "INSERT INTO vacacion VALUES (1003, TIMESTAMP '2028-03-01 00:00:00', TIMESTAMP '2028-03-10 23:59:59')"
            )
            v_g = cur.var(int)
            cur.execute(
                """
                INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
                VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
                RETURNING id_guardia INTO :g
                """,
                g=v_g,
            )
            id_g = int(v_g.getvalue()[0])
            cur.execute("INSERT INTO desempena VALUES (1002, 'Cardiologia', :g)", g=id_g)

            cur.execute(
                """
                SELECT tabla_afectada, operacion, clave_registro
                  FROM auditoria_guardias
                 ORDER BY id_auditoria DESC
                 FETCH FIRST 5 ROWS ONLY
                """
            )
            nuevas = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM auditoria_guardias")
            despues = int(cur.fetchone()[0])
            if despues != antes + 5:
                raise RuntimeError(
                    f"Esperaba +5 registros de auditoría, registró +{despues - antes}."
                )
            listado = "\n".join(f"  - {t} [{op}] -> {cl}" for t, op, cl in reversed(nuevas))
            return f"Se registraron 5 eventos automáticamente (+5):\n{listado}"

        return self._probar_sql_ok(_run)

    def _c3b_auditoria_rollback(self) -> tuple[bool, str]:
        """Prueba la transacción real `GuardiaController.alta_guardia` buscando un día libre dentro de vacaciones de 1001."""
        try:
            aud_antes = int(self._db.consultar("SELECT COUNT(*) FROM auditoria_guardias")[0][0])
            g_antes = int(self._db.consultar("SELECT COUNT(*) FROM guardia")[0][0])

            # Vacaciones de 1001 en 02_inserts.sql: 2026-11-20..2026-12-04
            dia_base = date(2026, 11, 25)
            ultimo_error = None
            for offset in range(10):
                dia_prueba = dia_base + timedelta(days=offset)
                try:
                    self._guardias.alta_guardia(1001, "Clinica Medica", dia_prueba, [1])
                    return False, "No disparó error: permitió guardia durante vacaciones."
                except ErrorTrigger as e:
                    aud_desp = int(
                        self._db.consultar("SELECT COUNT(*) FROM auditoria_guardias")[0][0]
                    )
                    g_desp = int(self._db.consultar("SELECT COUNT(*) FROM guardia")[0][0])
                    if e.codigo == 20003 and aud_antes == aud_desp and g_antes == g_desp:
                        return True, (
                            f"alta_guardia({dia_prueba}) fue frenado por ORA-{e.codigo}: \"{e}\"\n"
                            f"ROLLBACK verificado: GUARDIA ({g_antes} -> {g_desp}) y "
                            f"AUDITORIA_GUARDIAS ({aud_antes} -> {aud_desp}) quedaron intactas."
                        )
                    return (
                        False,
                        f"Inconsistencia: code={e.codigo}, G={g_antes}->{g_desp}, AUD={aud_antes}->{aud_desp}",
                    )
                except ReglaError as e:
                    # Si justo ese día ya estaba cubierto por otra guardia en Clinica Medica, probamos el siguiente
                    ultimo_error = e
                    continue
            return False, f"No se encontró un día libre en el período de vacaciones para probar ORA-20003: {ultimo_error}"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c4a_med_pac_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            cur.execute(
                """
                INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
                VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1001, '24444444')
                """
            )
            return "Internación del Dr. Díaz (DNI 24444444) con la Dra. Gómez (mat. 1001) aceptada."

        return self._probar_sql_ok(_run)

    def _c4b_med_pac_fail(self) -> tuple[bool, str]:
        """Prueba `InternacionController.internar` eligiendo una cama libre actual (resiliente al estado de 101-1)."""
        try:
            libres = self._reportes.listar_camas_libres()
            hab, cama = (libres[0][0], libres[0][1]) if libres else (101, 1)
            self._internaciones.internar("24444444", 1004, hab, cama)
            return False, "No falló: permitió que el Dr. Díaz sea su propio médico principal."
        except ErrorTrigger as e:
            if e.codigo == 20001:
                return (
                    True,
                    f"Rechazado vía internar() (Hab {hab}/Cama {cama}) por trigger ORA-{e.codigo}:\n\"{e}\"\n(ROLLBACK automático aplicado.)",
                )
            return False, f"Se esperaba ORA-20001, devolvió ORA-{e.codigo}: {e}"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c5a_guardia_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            v_g = cur.var(int)
            cur.execute(
                """
                INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
                VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
                RETURNING id_guardia INTO :g
                """,
                g=v_g,
            )
            id_g = int(v_g.getvalue()[0])
            cur.execute("INSERT INTO guardia_turno_manana VALUES (:g)", g=id_g)
            cur.execute("INSERT INTO desempena VALUES (1002, 'Cardiologia', :g)", g=id_g)
            return "Guardia 2028-05-10 (06:00-14:00) asignada a médico 1002 en Cardiología."

        return self._probar_sql_ok(_run)

    def _c5b_guardia_no_hace(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_g = cur.var(int)
            cur.execute(
                """
                INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
                VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
                RETURNING id_guardia INTO :g
                """,
                g=v_g,
            )
            cur.execute(
                "INSERT INTO desempena VALUES (1001, 'Cardiologia', :g)",
                g=int(v_g.getvalue()[0]),
            )

        return self._probar_sql_falla(20002, _run)

    def _c5c_guardia_vacaciones(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_g = cur.var(int)
            cur.execute(
                """
                INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
                VALUES (TIMESTAMP '2026-11-25 06:00:00', TIMESTAMP '2026-11-25 14:00:00')
                RETURNING id_guardia INTO :g
                """,
                g=v_g,
            )
            cur.execute(
                "INSERT INTO desempena VALUES (1001, 'Clinica Medica', :g)",
                g=int(v_g.getvalue()[0]),
            )

        return self._probar_sql_falla(20003, _run)

    def _c5d_guardia_internado(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_g = cur.var(int)
            cur.execute(
                """
                INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
                VALUES (TIMESTAMP '2026-10-15 06:00:00', TIMESTAMP '2026-10-15 14:00:00')
                RETURNING id_guardia INTO :g
                """,
                g=v_g,
            )
            cur.execute(
                "INSERT INTO desempena VALUES (1004, 'Clinica Medica', :g)",
                g=int(v_g.getvalue()[0]),
            )

        return self._probar_sql_falla(20004, _run)

    def _c5e_guardia_tope(self) -> tuple[bool, str]:
        try:
            dia_base = date(2026, 11, 15)
            ultimo_error = None
            for offset in range(15):
                dia_prueba = dia_base + timedelta(days=offset)
                try:
                    self._guardias.alta_guardia(1004, "Clinica Medica", dia_prueba, [1])
                    return False, "No falló: permitió superar el tope mensual (2) del Dr. 1004."
                except ErrorTrigger as e:
                    if e.codigo == 20005:
                        return (
                            True,
                            f"Rechazado vía alta_guardia({dia_prueba}) por trigger ORA-{e.codigo}:\n\"{e}\"\n(ROLLBACK automático aplicado.)",
                        )
                    return False, f"Se esperaba ORA-20005, devolvió ORA-{e.codigo}: {e}"
                except ReglaError as e:
                    ultimo_error = e
                    continue
            return False, f"No se encontró un día libre en nov-2026 para probar ORA-20005: {ultimo_error}"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c6a_vacacion_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            cur.execute(
                "INSERT INTO vacacion VALUES (1003, TIMESTAMP '2028-03-01 00:00:00', TIMESTAMP '2028-03-15 23:59:59')"
            )
            return "Vacaciones 2028-03-01..2028-03-15 para médico 1003 aceptadas."

        return self._probar_sql_ok(_run)

    def _c6b_vacacion_solapa(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                "INSERT INTO vacacion VALUES (1001, TIMESTAMP '2026-11-25 00:00:00', TIMESTAMP '2026-12-10 23:59:59')"
            )

        return self._probar_sql_falla(20006, _run)

    def _c7a_comentario_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            cur.execute(
                """
                INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
                VALUES (1, 2, 'Comentario válido de prueba.')
                """
            )
            return "Comentario en I1 / Recorrido 2 (Hab 101 en Ronda 1) aceptado."

        return self._probar_sql_ok(_run)

    def _c7b_comentario_propio(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_rec = cur.var(int)
            cur.execute(
                """
                INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido)
                VALUES (2, 1004, TIMESTAMP '2026-10-15 10:00:00')
                RETURNING id_recorrido INTO :r
                """,
                r=v_rec,
            )
            cur.execute(
                """
                INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
                VALUES (5, :r, 'Auto-comentario prohibido.')
                """,
                r=int(v_rec.getvalue()[0]),
            )

        return self._probar_sql_falla(20007, _run)

    def _c7c_comentario_fecha(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                """
                INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
                VALUES (3, 2, 'Comentario fuera del rango de la internación.')
                """
            )

        return self._probar_sql_falla(20008, _run)

    def _c7d_comentario_ronda(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                """
                INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
                VALUES (1, 3, 'Paciente no estaba en habitación de la ronda 2.')
                """
            )

        return self._probar_sql_falla(20009, _run)

    def _c8a_ocupa_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            v_int = cur.var(int)
            cur.execute(
                """
                INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
                VALUES (TIMESTAMP '2028-02-01 08:00:00', TIMESTAMP '2028-02-10 12:00:00', 1001, '30333333')
                RETURNING id_internacion INTO :i
                """,
                i=v_int,
            )
            id_i = int(v_int.getvalue()[0])
            cur.execute(
                "INSERT INTO ocupa VALUES (:i, TIMESTAMP '2028-02-01 08:00:00', 101, 1, TIMESTAMP '2028-02-04 10:00:00')",
                i=id_i,
            )
            cur.execute(
                "INSERT INTO ocupa VALUES (:i, TIMESTAMP '2028-02-04 10:00:00', 101, 2, TIMESTAMP '2028-02-07 10:00:00')",
                i=id_i,
            )
            cur.execute(
                "INSERT INTO ocupa VALUES (:i, TIMESTAMP '2028-02-07 10:00:00', 101, 1, TIMESTAMP '2028-02-10 12:00:00')",
                i=id_i,
            )
            return "Secuencia 101-1 -> 101-2 -> 101-1 (repitiendo cama sin solapamiento) aceptada."

        return self._probar_sql_ok(_run)

    def _c8b_ocupa_rango(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                "INSERT INTO ocupa VALUES (4, TIMESTAMP '2026-09-09 08:00:00', 201, 2, TIMESTAMP '2026-09-10 08:00:00')"
            )

        return self._probar_sql_falla(20010, _run)

    def _c8c_ocupa_cama_ocupada(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_int = cur.var(int)
            cur.execute(
                """
                INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
                VALUES (TIMESTAMP '2026-10-12 08:00:00', TIMESTAMP '2026-10-15 12:00:00', 1002, '30444444')
                RETURNING id_internacion INTO :i
                """,
                i=v_int,
            )
            cur.execute(
                "INSERT INTO ocupa VALUES (:i, TIMESTAMP '2026-10-12 09:00:00', 302, 1, TIMESTAMP '2026-10-15 12:00:00')",
                i=int(v_int.getvalue()[0]),
            )

        return self._probar_sql_falla(20011, _run)

    def _c8d_ocupa_dos_camas(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                "INSERT INTO ocupa VALUES (4, TIMESTAMP '2026-09-11 09:00:00', 201, 2, TIMESTAMP '2026-09-12 09:00:00')"
            )

        return self._probar_sql_falla(20012, _run)

    def _c9a_recorrido_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            cur.execute(
                "INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido) VALUES (1, 1001, TIMESTAMP '2026-11-10 10:00:00')"
            )
            return "Recorrido del médico 1001 el 2026-11-10 (fuera de vacaciones) aceptado."

        return self._probar_sql_ok(_run)

    def _c9b_recorrido_vacaciones(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                "INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido) VALUES (1, 1001, TIMESTAMP '2026-11-25 10:00:00')"
            )

        return self._probar_sql_falla(20013, _run)

    def _c10a_cambio_guardia_ok(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> str:
            cur.execute(
                """
                UPDATE guardia
                   SET fecha_inicio_guardia = TIMESTAMP '2026-11-12 06:00:00',
                       fecha_fin_guardia    = TIMESTAMP '2026-11-12 14:00:00'
                 WHERE id_guardia = 1
                """
            )
            return "Guardia 1 (médico 1001) reprogramada del 2026-11-02 al 2026-11-12 sin conflictos."

        return self._probar_sql_ok(_run)

    def _c10b_cambio_guardia_vac(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                """
                UPDATE guardia
                   SET fecha_inicio_guardia = TIMESTAMP '2026-11-25 06:00:00',
                       fecha_fin_guardia    = TIMESTAMP '2026-11-25 14:00:00'
                 WHERE id_guardia = 1
                """
            )

        return self._probar_sql_falla(20003, _run)

    def _c10c_cambio_guardia_int(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            cur.execute(
                """
                UPDATE guardia
                   SET fecha_inicio_guardia = TIMESTAMP '2026-10-15 14:00:00',
                       fecha_fin_guardia    = TIMESTAMP '2026-10-15 22:00:00'
                 WHERE id_guardia = 2
                """
            )

        return self._probar_sql_falla(20004, _run)

    def _c10d_cambio_guardia_tope(self) -> tuple[bool, str]:
        def _run(_cnx: Any, cur: Any) -> None:
            v_g = cur.var(int)
            cur.execute(
                """
                INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
                VALUES (TIMESTAMP '2028-06-05 06:00:00', TIMESTAMP '2028-06-05 14:00:00')
                RETURNING id_guardia INTO :g
                """,
                g=v_g,
            )
            id_g = int(v_g.getvalue()[0])
            cur.execute("INSERT INTO desempena VALUES (1004, 'Clinica Medica', :g)", g=id_g)
            cur.execute(
                """
                UPDATE guardia
                   SET fecha_inicio_guardia = TIMESTAMP '2026-11-15 06:00:00',
                       fecha_fin_guardia    = TIMESTAMP '2026-11-15 14:00:00'
                 WHERE id_guardia = :g
                """,
                g=id_g,
            )

        return self._probar_sql_falla(20005, _run)

    # ------------------------------------------------------------------
    # Casos de prueba de capa de aplicación, transacciones y concurrencia (11A..15A)
    # ------------------------------------------------------------------
    def _buscar_paciente_sin_internacion_activa(self, db: ConnectionManager | None = None) -> str | None:
        origen = db or self._db
        filas = origen.consultar(
            """
            SELECT p.dni
              FROM paciente p
             WHERE NOT EXISTS (
                   SELECT 1
                     FROM internacion i
                    WHERE i.dni = p.dni
                      AND i.fecha_terminacion_internacion IS NULL
             )
             ORDER BY p.dni
             FETCH FIRST 1 ROWS ONLY
            """
        )
        return str(filas[0][0]) if filas else None

    def _c11a_ciclo_internacion_completo(self) -> tuple[bool, str]:
        """Ciclo completo vía InternacionController: internar -> cambiar -> repetir -> dar_alta."""
        try:
            def _run(db_a: ConnectionManager) -> str:
                ic = InternacionController(db_a)
                rep = ReportesController(db_a)
                pc = PacienteController(db_a)
                libres = rep.listar_camas_libres()
                if len(libres) < 2:
                    raise RuntimeError("Se necesitan al menos 2 camas libres para probar el traslado.")
                hab1, cama1 = libres[0][0], libres[0][1]
                hab2, cama2 = libres[1][0], libres[1][1]

                dni = self._buscar_paciente_sin_internacion_activa(db_a)
                if dni is None:
                    dni = "99999901"
                    pc.alta(dni, "Paciente", "Prueba", date(1992, 5, 10), "X")

                t0 = datetime(2028, 4, 1, 8, 0, 0)
                t1 = datetime(2028, 4, 2, 10, 0, 0)
                t2 = datetime(2028, 4, 3, 10, 0, 0)
                t3 = datetime(2028, 4, 4, 12, 0, 0)

                id_int = ic.internar(dni, 1001, hab1, cama1, fecha_inicio=t0)
                ic.cambiar_cama(id_int, hab2, cama2, fecha_cambio=t1)
                ic.cambiar_cama(id_int, hab1, cama1, fecha_cambio=t2)
                ic.dar_alta(id_int, fecha_alta=t3)

                ocups = ic.listar_ocupaciones(id_int)
                secuencia = [(o.nro_habitacion, o.nro_cama) for o in ocups]
                esperada = [(hab1, cama1), (hab2, cama2), (hab1, cama1)]
                if secuencia != esperada:
                    raise RuntimeError(f"Secuencia esperada {esperada}, obtenida {secuencia}.")
                if any(o.fecha_terminacion is None for o in ocups):
                    raise RuntimeError("Quedó alguna ocupación sin fecha de terminación tras el alta.")

                libres_final = {(h, c) for h, c, _ in rep.listar_camas_libres()}
                if (hab1, cama1) not in libres_final:
                    raise RuntimeError(f"La cama {hab1}-{cama1} no quedó libre tras el alta.")

                return (
                    f"Internación #{id_int} (DNI {dni}) completó el ciclo {hab1}-{cama1} -> "
                    f"{hab2}-{cama2} -> {hab1}-{cama1} -> Alta.\n"
                    f"Historial OCUPA: 3 filas cerradas y cama {hab1}-{cama1} nuevamente disponible."
                )

            detalle = pruebas_dao.ejecutar_controladores_en_rollback(self._db, _run)
            return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
        except Exception as e:
            return False, f"Falló inesperadamente: {e}"

    def _c11b_internar_doble_activa(self) -> tuple[bool, str]:
        """Rechaza internar a un paciente que ya tiene una internación en curso."""
        try:
            activas = self._db.consultar(
                "SELECT dni FROM internacion WHERE fecha_terminacion_internacion IS NULL FETCH FIRST 1 ROWS ONLY"
            )
            dni_activo = str(activas[0][0]) if activas else "30111111"
            int_antes = int(self._db.consultar("SELECT COUNT(*) FROM internacion")[0][0])
            libres = self._reportes.listar_camas_libres()
            hab, cama = (libres[0][0], libres[0][1]) if libres else (101, 1)
            try:
                self._internaciones.internar(
                    dni_activo, 1001, hab, cama, fecha_inicio=datetime(2028, 4, 1, 8, 0, 0)
                )
                return False, f"No falló: permitió abrir una segunda internación activa para {dni_activo}."
            except ReglaError as e:
                int_desp = int(self._db.consultar("SELECT COUNT(*) FROM internacion")[0][0])
                if "en curso" in str(e).lower() and int_antes == int_desp:
                    return True, (
                        f"Rechazado correctamente para DNI {dni_activo} por regla de aplicación:\n\"{e}\"\n"
                        f"INTERNACION sin cambios ({int_antes} -> {int_desp})."
                    )
                return False, f"Error o estado inesperado: {e} (INT {int_antes}->{int_desp})"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c11c_internar_cama_ocupada_rollback(self) -> tuple[bool, str]:
        """Atomicidad de internar(): al fallar OCUPA por ORA-20011 revierte INTERNACION."""
        try:
            int_antes = int(self._db.consultar("SELECT COUNT(*) FROM internacion")[0][0])
            oc_antes = int(self._db.consultar("SELECT COUNT(*) FROM ocupa")[0][0])

            ocupadas = [c for c in self._reportes.listar_todas_las_camas() if c.ocupada]
            hab_oc, cama_oc = (ocupadas[0].nro_habitacion, ocupadas[0].nro_cama) if ocupadas else (102, 2)
            dni = self._buscar_paciente_sin_internacion_activa()
            if dni is None:
                return False, "No hay ningún paciente sin internación activa disponible para ejecutar la prueba."

            try:
                self._internaciones.internar(
                    dni,
                    1001,
                    hab_oc,
                    cama_oc,
                    fecha_inicio=datetime(2028, 4, 1, 8, 0, 0),
                )
                return False, f"No falló: permitió ocupar la cama ya ocupada {hab_oc}-{cama_oc}."
            except ErrorTrigger as e:
                int_desp = int(self._db.consultar("SELECT COUNT(*) FROM internacion")[0][0])
                oc_desp = int(self._db.consultar("SELECT COUNT(*) FROM ocupa")[0][0])
                if e.codigo == 20011 and int_antes == int_desp and oc_antes == oc_desp:
                    return True, (
                        f"internar(DNI {dni}) sobre cama ocupada {hab_oc}-{cama_oc} fue frenado por ORA-{e.codigo}:\n"
                        f"\"{e}\"\n"
                        f"ROLLBACK verificado: INTERNACION ({int_antes} -> {int_desp}) y "
                        f"OCUPA ({oc_antes} -> {oc_desp}) sin filas huérfanas."
                    )
                return False, (
                    f"Inconsistencia: code={e.codigo}, INT={int_antes}->{int_desp}, OCUPA={oc_antes}->{oc_desp}"
                )
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c12a_guardia_turnos_no_contiguos(self) -> tuple[bool, str]:
        """Turnos [1, 3] (Mañana + Noche) rechazados por GuardiaController."""
        try:
            g_antes = int(self._db.consultar("SELECT COUNT(*) FROM guardia")[0][0])
            try:
                self._guardias.alta_guardia(1002, "Cardiologia", date(2028, 7, 10), [1, 3])
                return False, "No falló: permitió asignar turnos no contiguos [1, 3]."
            except ReglaError as e:
                g_desp = int(self._db.consultar("SELECT COUNT(*) FROM guardia")[0][0])
                if "contiguos" in str(e).lower() and g_antes == g_desp:
                    return True, (
                        f"Rechazado correctamente por regla de aplicación:\n\"{e}\"\n"
                        f"GUARDIA sin cambios ({g_antes} -> {g_desp})."
                    )
                return False, f"Error inesperado: {e} (GUARDIA {g_antes}->{g_desp})"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c12b_guardia_solapa_mismo_medico(self) -> tuple[bool, str]:
        """Mismo médico (1002) en dos especialidades en el mismo horario debe fallar."""
        try:
            def _run(db_a: ConnectionManager) -> str:
                gc = GuardiaController(db_a)
                id_g1 = gc.alta_guardia(1002, "Cardiologia", date(2028, 7, 10), [1])
                g_tras_1 = int(db_a.consultar("SELECT COUNT(*) FROM guardia")[0][0])
                try:
                    gc.alta_guardia(1002, "Terapia Intensiva", date(2028, 7, 10), [1])
                    raise RuntimeError("No falló: permitió al médico 1002 dos guardias simultáneas.")
                except ReglaError as e:
                    g_tras_2 = int(db_a.consultar("SELECT COUNT(*) FROM guardia")[0][0])
                    if "otra guardia asignada" not in str(e).lower() or g_tras_1 != g_tras_2:
                        raise RuntimeError(
                            f"Error o conteo inesperado: {e} (GUARDIA {g_tras_1}->{g_tras_2})"
                        ) from e
                    return (
                        f"Guardia #{id_g1} creada para médico 1002 (Cardiologia 2028-07-10 Mañana).\n"
                        f"2do intento (Terapia Intensiva mismo horario) rechazado: \"{e}\"\n"
                        f"Sin filas huérfanas ({g_tras_1} -> {g_tras_2})."
                    )

            detalle = pruebas_dao.ejecutar_controladores_en_rollback(self._db, _run)
            return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
        except Exception as e:
            return False, f"Falló inesperadamente: {e}"

    def _c12c_guardia_solapa_especialidad(self) -> tuple[bool, str]:
        """Dos médicos distintos (1001 y 1004) en Clinica Medica en el mismo horario debe fallar."""
        try:
            def _run(db_a: ConnectionManager) -> str:
                gc = GuardiaController(db_a)
                id_g1 = gc.alta_guardia(1001, "Clinica Medica", date(2028, 7, 12), [2])
                g_tras_1 = int(db_a.consultar("SELECT COUNT(*) FROM guardia")[0][0])
                try:
                    gc.alta_guardia(1004, "Clinica Medica", date(2028, 7, 12), [2])
                    raise RuntimeError("No falló: permitió dos médicos en Clinica Medica en el mismo horario.")
                except ReglaError as e:
                    g_tras_2 = int(db_a.consultar("SELECT COUNT(*) FROM guardia")[0][0])
                    if "ya hay un médico asignado" not in str(e).lower() or g_tras_1 != g_tras_2:
                        raise RuntimeError(
                            f"Error o conteo inesperado: {e} (GUARDIA {g_tras_1}->{g_tras_2})"
                        ) from e
                    return (
                        f"Guardia #{id_g1} creada para médico 1001 (Clinica Medica 2028-07-12 Tarde).\n"
                        f"2do intento (médico 1004 misma especialidad/horario) rechazado: \"{e}\"\n"
                        f"Sin filas huérfanas ({g_tras_1} -> {g_tras_2})."
                    )

            detalle = pruebas_dao.ejecutar_controladores_en_rollback(self._db, _run)
            return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
        except Exception as e:
            return False, f"Falló inesperadamente: {e}"

    def _c13a_recorrido_dia_incorrecto(self) -> tuple[bool, str]:
        """registrar_recorrido() en miércoles para la Ronda 1 (MARTES) debe fallar."""
        try:
            rec_antes = int(self._db.consultar("SELECT COUNT(*) FROM recorrido")[0][0])
            try:
                # 2028-07-12 es miércoles; Ronda 1 es MARTES
                self._rondas.registrar_recorrido(1, 1001, datetime(2028, 7, 12, 10, 0, 0))
                return False, "No falló: permitió registrar un recorrido de Ronda 1 (MARTES) en miércoles."
            except ReglaError as e:
                rec_desp = int(self._db.consultar("SELECT COUNT(*) FROM recorrido")[0][0])
                if "martes" in str(e).lower() and rec_antes == rec_desp:
                    return True, (
                        f"Rechazado correctamente por validación de día:\n\"{e}\"\n"
                        f"RECORRIDO sin cambios ({rec_antes} -> {rec_desp})."
                    )
                return False, f"Error inesperado: {e} (RECORRIDO {rec_antes}->{rec_desp})"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c13b_recorrido_vacaciones_via_ctrl(self) -> tuple[bool, str]:
        """registrar_recorrido() en vacaciones de 1001 (martes 2026-11-24) debe llegar a ORA-20013."""
        try:
            rec_antes = int(self._db.consultar("SELECT COUNT(*) FROM recorrido")[0][0])
            try:
                # 2026-11-24 es MARTES (coincide con Ronda 1) y cae dentro de vacaciones de 1001 (11-20..12-04)
                self._rondas.registrar_recorrido(1, 1001, datetime(2026, 11, 24, 10, 0, 0))
                return False, "No falló: permitió recorrido en vacaciones de la Dra. 1001."
            except ErrorTrigger as e:
                rec_desp = int(self._db.consultar("SELECT COUNT(*) FROM recorrido")[0][0])
                if e.codigo == 20013 and rec_antes == rec_desp:
                    return True, (
                        f"registrar_recorrido() llegó limpio al trigger ORA-{e.codigo}:\n\"{e}\"\n"
                        f"ROLLBACK verificado: RECORRIDO ({rec_antes} -> {rec_desp})."
                    )
                return False, f"Se esperaba ORA-20013, devolvió ORA-{e.codigo}: {e}"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c13c_comentarios_tope_ronda(self) -> tuple[bool, str]:
        """registrar_comentario() superando el total de camas de la ronda debe fallar."""
        try:
            def _run(db_a: ConnectionManager) -> str:
                rc = RondaController(db_a)
                # Recorrido 3 pertenece a Ronda 2 (habs 301 y 302 = 3 camas totales) y visita I2 en hab 301
                max_camas = int(
                    db_a.consultar(
                        """
                        SELECT COUNT(*)
                          FROM es_visitada ev
                          JOIN cama c ON c.nro_habitacion = ev.nro_habitacion
                         WHERE ev.id_ronda = 2
                        """
                    )[0][0]
                )
                actuales = len(rc.listar_comentarios_de_recorrido(3))
                agregados = 0
                for idx in range(max_camas - actuales):
                    rc.registrar_comentario(3, 2, f"Control clínico de prueba #{idx + 1}.")
                    agregados += 1

                try:
                    rc.registrar_comentario(3, 2, "Comentario excediendo el tope de la ronda.")
                    raise RuntimeError("No falló al superar el máximo de comentarios del recorrido.")
                except ReglaError as e:
                    if "alcanzó el máximo" not in str(e).lower():
                        raise RuntimeError(f"Error inesperado al superar tope: {e}") from e
                    return (
                        f"Ronda 2 posee {max_camas} camas; Recorrido 3 tenía {actuales} comentario(s).\n"
                        f"Se completaron {agregados} hasta llegar a {max_camas}/{max_camas} y el siguiente fue rechazado:\n"
                        f"\"{e}\""
                    )

            detalle = pruebas_dao.ejecutar_controladores_en_rollback(self._db, _run)
            return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
        except Exception as e:
            return False, f"Falló inesperadamente: {e}"

    def _c14a_baja_medico_paciente_conserva_persona(self) -> tuple[bool, str]:
        """Alta y baja de un médico como paciente: elimina PACIENTE pero conserva PERSONA y MEDICO."""
        try:
            def _run(db_a: ConnectionManager) -> str:
                pc = PacienteController(db_a)
                mc = MedicoController(db_a)

                # Busca un médico que todavía no sea paciente (en 02_inserts.sql: 1001, 1002, 1003)
                filas = db_a.consultar(
                    """
                    SELECT m.matricula_medico, m.dni, pe.nombre, pe.apellido
                      FROM medico m
                      JOIN persona pe ON pe.dni = m.dni
                     WHERE NOT EXISTS (SELECT 1 FROM paciente p WHERE p.dni = m.dni)
                     ORDER BY m.matricula_medico
                     FETCH FIRST 1 ROWS ONLY
                    """
                )
                if not filas:
                    raise RuntimeError("Todos los médicos ya están registrados como pacientes.")
                mat, dni, nom, ape = int(filas[0][0]), str(filas[0][1]), str(filas[0][2]), str(filas[0][3])

                pc.alta(dni, nom, ape, date(1985, 6, 15), "F")
                pc.eliminar(dni)

                med = mc.obtener(mat)
                try:
                    pc.obtener(dni)
                    raise RuntimeError(f"El paciente {dni} sigue existiendo tras eliminar().")
                except ReglaError:
                    pass

                return (
                    f"Alta y baja de paciente DNI {dni} completadas.\n"
                    f"PACIENTE eliminado correctamente y médico #{med.matricula} ({med.nombre_completo}) "
                    f"conservado intacto en PERSONA y MEDICO."
                )

            detalle = pruebas_dao.ejecutar_controladores_en_rollback(self._db, _run)
            return True, f"Éxito (cambios revertidos con ROLLBACK).\n{detalle}"
        except Exception as e:
            return False, f"Falló inesperadamente: {e}"

    def _c14b_baja_paciente_con_internaciones(self) -> tuple[bool, str]:
        """Eliminar paciente con internaciones registradas debe ser rechazado."""
        try:
            filas = self._db.consultar(
                "SELECT dni FROM internacion FETCH FIRST 1 ROWS ONLY"
            )
            dni = str(filas[0][0]) if filas else "30111111"
            try:
                self._pacientes.eliminar(dni)
                return False, f"No falló: permitió eliminar al paciente {dni} con internaciones."
            except ReglaError as e:
                sigue = self._pacientes.obtener(dni)
                if "internaciones registradas" in str(e).lower() and sigue.dni == dni:
                    return True, (
                        f"Rechazado correctamente:\n\"{e}\"\n"
                        f"Paciente {sigue.dni} ({sigue.nombre_completo}) intacto."
                    )
                return False, f"Error inesperado: {e}"
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c14c_editar_medico_rollback_fk(self) -> tuple[bool, str]:
        """Quitar especialidad con guardias dispara ORA-02292 y revierte PERSONA, MEDICO y AUDITORIA."""
        try:
            antes = self._medicos.obtener(1001)
            aud_antes = int(self._db.consultar("SELECT COUNT(*) FROM auditoria_guardias")[0][0])
            esps_sin_clinica = [
                (e.nombre_especialidad, e.hace_guardia)
                for e in antes.especialidades
                if e.nombre_especialidad != "Clinica Medica"
            ]
            try:
                self._medicos.editar(
                    1001,
                    "NombreTemporalRollback",
                    antes.apellido,
                    antes.cuil_cuit,
                    antes.fecha_ingreso,
                    antes.cantidad_guardias + 50,
                    especialidades=esps_sin_clinica,
                )
                return False, "No falló: permitió quitar 'Clinica Medica' al médico 1001 pese a tener guardias."
            except ReglaError as e:
                despues = self._medicos.obtener(1001)
                aud_desp = int(self._db.consultar("SELECT COUNT(*) FROM auditoria_guardias")[0][0])
                if (
                    e.codigo_ora == 2292
                    and despues.nombre == antes.nombre
                    and despues.cantidad_guardias == antes.cantidad_guardias
                    and aud_antes == aud_desp
                ):
                    return True, (
                        f"Rechazado por Oracle ORA-02292 (FK_DESEMPENA_POSEE):\n\"{e}\"\n"
                        f"ROLLBACK verificado: nombre='{despues.nombre}', tope={despues.cantidad_guardias} y "
                        f"AUDITORIA_GUARDIAS ({aud_antes} -> {aud_desp}) intactos."
                    )
                return False, (
                    f"Inconsistencia tras fallo: code={e.codigo_ora}, "
                    f"nombre={antes.nombre}->{despues.nombre}, "
                    f"tope={antes.cantidad_guardias}->{despues.cantidad_guardias}, "
                    f"AUD={aud_antes}->{aud_desp}"
                )
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _c15a_concurrencia_cama_wait5(self) -> tuple[bool, str]:
        """Prueba real con 2 conexiones: Cnx1 bloquea cama (FOR UPDATE) y Cnx2 recibe ORA-30006."""
        try:
            libres = self._reportes.listar_camas_libres()
            hab, cama = (libres[0][0], libres[0][1]) if libres else (101, 1)
            dni = self._buscar_paciente_sin_internacion_activa()
            if dni is None:
                return False, "No hay ningún paciente sin internación activa disponible para ejecutar la prueba."

            int_antes = int(self._db.consultar("SELECT COUNT(*) FROM internacion")[0][0])
            inicio = time.monotonic()

            def _intentar_en_cnx2() -> None:
                self._internaciones.internar(
                    dni,
                    1001,
                    hab,
                    cama,
                    fecha_inicio=datetime(2028, 4, 1, 8, 0, 0),
                )

            try:
                pruebas_dao.ejecutar_con_cama_bloqueada(self._db, hab, cama, _intentar_en_cnx2)
                return False, f"No falló: Cnx2 pudo tomar la cama {hab}-{cama} mientras Cnx1 la mantenía bloqueada."
            except ErrorConcurrencia as e:
                duracion = time.monotonic() - inicio
                int_desp = int(self._db.consultar("SELECT COUNT(*) FROM internacion")[0][0])
                if e.codigo_ora in (54, 30006) and int_antes == int_desp:
                    return True, (
                        f"Cnx1 bloqueó cama {hab}-{cama} y Cnx2 (DNI {dni}) falló limpiamente tras {duracion:.1f}s "
                        f"con ORA-{e.codigo_ora:05d}:\n\"{e}\"\n"
                        f"Ambas conexiones revertidas con ROLLBACK: INTERNACION ({int_antes} -> {int_desp})."
                    )
                return False, (
                    f"ErrorConcurrencia inesperado: code={e.codigo_ora}, INT={int_antes}->{int_desp}"
                )
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def _construir_casos(self) -> list[CasoPrueba]:
        return [
            CasoPrueba(
                "1A", "1. Procedure camas", "OK",
                "Camas disponibles (sector en 0 + baja al ocupar)",
                "OK (total - 1)",
                "Llama a pr_camas_disponibles, verifica que Pediatría aparezca con 0 camas y que al ocupar una cama libre el total baje en 1.",
                "CALL pr_camas_disponibles(:cant, :det); INSERT internacion + ocupa; CALL pr_camas_disponibles(...);",
                self._c1a_camas_ok,
            ),
            CasoPrueba(
                "1B", "1. Procedure camas", "FALLA",
                "Ocupar cama inexistente 102-3 (numeración con hueco)",
                "ORA-02291",
                "La habitación 102 tiene camas 1, 2 y 4 (sin cama 3). Intentar ocupar 102-3 debe fallar por FK fk_ocupa_cama.",
                "INSERT INTO ocupa (..., nro_habitacion=102, nro_cama=3, ...);",
                self._c1b_cama_inexistente,
            ),
            CasoPrueba(
                "2A", "2. Procedure comentarios", "OK",
                "Comentarios de internación con DNI correcto",
                "OK (>= 2 filas)",
                "Llama a pr_comentarios_internacion(1, '30111111') para Ana López y devuelve sus comentarios con fecha, turno y médico.",
                "CALL pr_comentarios_internacion(1, '30111111', :cur);",
                self._c2a_comentarios_ok,
            ),
            CasoPrueba(
                "2B", "2. Procedure comentarios", "FALLA",
                "Comentarios de internación con DNI de otro paciente",
                "0 filas",
                "Llama a pr_comentarios_internacion(1, '30222222'): como I1 no pertenece a ese DNI, debe devolver cursor vacío.",
                "CALL pr_comentarios_internacion(1, '30222222', :cur);",
                self._c2b_comentarios_dni_ajeno,
            ),
            CasoPrueba(
                "3A", "3. Auditoría y TX", "OK",
                "Disparo de los 5 triggers de auditoría",
                "OK (+5 filas)",
                "Modifica MEDICO, POSEE, VACACION, GUARDIA y DESEMPENA y comprueba que se graban exactamente 5 filas en auditoria_guardias.",
                "UPDATE medico; UPDATE posee; INSERT vacacion; INSERT guardia; INSERT desempena;",
                self._c3a_auditoria_ok,
            ),
            CasoPrueba(
                "3B", "3. Auditoría y TX", "FALLA",
                "Atomicidad: alta_guardia() falla y hace ROLLBACK total",
                "ORA-20003 + 0 huérf.",
                "Llama a GuardiaController.alta_guardia() en vacaciones de 1001. Falla en DESEMPENA y revierte GUARDIA y su auditoría.",
                "guardia_ctrl.alta_guardia(1001, 'Clinica Medica', 2026-11-25, [1]) -> ROLLBACK",
                self._c3b_auditoria_rollback,
            ),
            CasoPrueba(
                "4A", "4. Trg médico-paciente", "OK",
                "Médico internado atendido por otro médico principal",
                "OK",
                "Interna al Dr. Díaz (DNI 24444444) designando a la Dra. Gómez (mat. 1001) como médico principal.",
                "INSERT INTO internacion (..., matricula_medico=1001, dni='24444444');",
                self._c4a_med_pac_ok,
            ),
            CasoPrueba(
                "4B", "4. Trg médico-paciente", "FALLA",
                "Médico como su propio médico principal (vía internar)",
                "ORA-20001",
                "Llama a InternacionController.internar('24444444', 1004, ...). Debe disparar trg_internacion_medico_paciente (ORA-20001).",
                "internacion_ctrl.internar(dni='24444444', matricula=1004, cama_libre)",
                self._c4b_med_pac_fail,
            ),
            CasoPrueba(
                "5A", "5. Trg asignación guardia", "OK",
                "Guardia válida (hace_guardia='S', sin conflictos)",
                "OK",
                "Asigna al médico 1002 en Cardiología el 2028-05-10 (06:00-14:00), respetando todas las reglas.",
                "INSERT guardia (2028-05-10 06:00..14:00); INSERT desempena (1002, 'Cardiologia', :g);",
                self._c5a_guardia_ok,
            ),
            CasoPrueba(
                "5B", "5. Trg asignación guardia", "FALLA",
                "Especialidad con hace_guardia = 'N'",
                "ORA-20002",
                "La Dra. 1001 tiene Cardiología pero con hace_guardia = 'N'. Debe disparar ORA-20002.",
                "INSERT desempena (1001, 'Cardiologia', :g);",
                self._c5b_guardia_no_hace,
            ),
            CasoPrueba(
                "5C", "5. Trg asignación guardia", "FALLA",
                "Guardia durante vacaciones del médico",
                "ORA-20003",
                "La Dra. 1001 está de vacaciones del 2026-11-20 al 2026-12-04. Asignarla el 2026-11-25 dispara ORA-20003.",
                "INSERT guardia (2026-11-25 06:00..14:00); INSERT desempena (1001, 'Clinica Medica', :g);",
                self._c5c_guardia_vacaciones,
            ),
            CasoPrueba(
                "5D", "5. Trg asignación guardia", "FALLA",
                "Guardia mientras el médico está internado como paciente",
                "ORA-20004",
                "El Dr. 1004 estuvo internado del 2026-10-10 al 2026-10-20 (I5). Asignarle guardia el 2026-10-15 dispara ORA-20004.",
                "INSERT guardia (2026-10-15 06:00..14:00); INSERT desempena (1004, 'Clinica Medica', :g);",
                self._c5d_guardia_internado,
            ),
            CasoPrueba(
                "5E", "5. Trg asignación guardia", "FALLA",
                "Supera tope mensual de guardias (vía alta_guardia)",
                "ORA-20005",
                "El Dr. 1004 tiene tope=2 y ya posee 2 guardias en nov-2026. Una 3ra vía alta_guardia dispara ORA-20005.",
                "guardia_ctrl.alta_guardia(1004, 'Clinica Medica', 2026-11-15, [1])",
                self._c5e_guardia_tope,
            ),
            CasoPrueba(
                "6A", "6. Trg vacaciones", "OK",
                "Nuevo período de vacaciones sin superposición",
                "OK",
                "Registra vacaciones para la Dra. 1003 en marzo 2028 (sin solapamiento).",
                "INSERT INTO vacacion VALUES (1003, 2028-03-01, 2028-03-15);",
                self._c6a_vacacion_ok,
            ),
            CasoPrueba(
                "6B", "6. Trg vacaciones", "FALLA",
                "Período de vacaciones superpuesto del mismo médico",
                "ORA-20006",
                "La Dra. 1001 ya tiene vacaciones 2026-11-20..2026-12-04. Insertar 2026-11-25..2026-12-10 dispara ORA-20006.",
                "INSERT INTO vacacion VALUES (1001, 2026-11-25, 2026-12-10);",
                self._c6b_vacacion_solapa,
            ),
            CasoPrueba(
                "7A", "7. Trg comentario", "OK",
                "Comentario válido (paciente en habitación de la ronda)",
                "OK",
                "Registra comentario sobre I1 en recorrido 2 (ronda 1 visita hab 101, donde Ana estaba el 2026-10-20 16:00).",
                "INSERT INTO comentario (id_internacion=1, id_recorrido=2, texto='...');",
                self._c7a_comentario_ok,
            ),
            CasoPrueba(
                "7B", "7. Trg comentario", "FALLA",
                "Médico comenta su propia internación",
                "ORA-20007",
                "Crea recorrido del Dr. 1004 el 2026-10-15 y trata de comentar sobre I5 (propia internación del Dr. 1004).",
                "INSERT recorrido (ronda=2, med=1004, 2026-10-15); INSERT comentario (I5, :rec, '...');",
                self._c7b_comentario_propio,
            ),
            CasoPrueba(
                "7C", "7. Trg comentario", "FALLA",
                "Recorrido fuera del período de la internación",
                "ORA-20008",
                "I3 terminó el 2026-10-08; el recorrido 2 es del 2026-10-20. Debe disparar ORA-20008.",
                "INSERT INTO comentario (id_internacion=3, id_recorrido=2, texto='...');",
                self._c7c_comentario_fecha,
            ),
            CasoPrueba(
                "7D", "7. Trg comentario", "FALLA",
                "Paciente en habitación que no pertenece a la ronda",
                "ORA-20009",
                "El 2026-10-21 I1 ocupaba hab 101, pero el recorrido 3 (ronda 2) solo visita 301 y 302. Dispara ORA-20009.",
                "INSERT INTO comentario (id_internacion=1, id_recorrido=3, texto='...');",
                self._c7d_comentario_ronda,
            ),
            CasoPrueba(
                "8A", "8. Trg ocupa camas", "OK",
                "Cambio y repetición de cama dentro de la internación",
                "OK",
                "Paciente pasa 101-1 -> 101-2 -> 101-1 sin solapar intervalos y dentro de las fechas de su internación.",
                "INSERT internacion (2028-02-01..10); INSERT ocupa 101-1 -> 101-2 -> 101-1;",
                self._c8a_ocupa_ok,
            ),
            CasoPrueba(
                "8B", "8. Trg ocupa camas", "FALLA",
                "Ocupación fuera del rango de fechas de la internación",
                "ORA-20010",
                "I4 comienza el 2026-09-10 09:00; intentar ocupar una cama el 2026-09-09 dispara ORA-20010.",
                "INSERT INTO ocupa VALUES (4, 2026-09-09 08:00, 201, 2, 2026-09-10 08:00);",
                self._c8b_ocupa_rango,
            ),
            CasoPrueba(
                "8C", "8. Trg ocupa camas", "FALLA",
                "Cama ya ocupada por otro paciente en ese intervalo",
                "ORA-20011",
                "La cama 302-1 fue ocupada por I5 del 2026-10-10 al 2026-10-20. Asignarla a otra internación el 10-12 dispara ORA-20011.",
                "INSERT internacion (10-12..10-15); INSERT ocupa (..., 302, 1, 10-12..10-15);",
                self._c8c_ocupa_cama_ocupada,
            ),
            CasoPrueba(
                "8D", "8. Trg ocupa camas", "FALLA",
                "Un mismo internado ocupando dos camas simultáneamente",
                "ORA-20012",
                "I4 ya ocupa 201-1 del 2026-09-10 al 2026-09-15; asignarle además 201-2 el 09-11 dispara ORA-20012.",
                "INSERT INTO ocupa VALUES (4, 2026-09-11 09:00, 201, 2, 2026-09-12 09:00);",
                self._c8d_ocupa_dos_camas,
            ),
            CasoPrueba(
                "9A", "9. Trg recorrido", "OK",
                "Recorrido fuera de vacaciones del médico",
                "OK",
                "La Dra. 1001 realiza un recorrido el 2026-11-10 (fuera de su período de vacaciones).",
                "INSERT INTO recorrido (id_ronda=1, matricula=1001, fecha=2026-11-10);",
                self._c9a_recorrido_ok,
            ),
            CasoPrueba(
                "9B", "9. Trg recorrido", "FALLA",
                "Recorrido durante vacaciones del médico",
                "ORA-20013",
                "La Dra. 1001 está de vacaciones el 2026-11-25. Insertar un recorrido en esa fecha dispara ORA-20013.",
                "INSERT INTO recorrido (id_ronda=1, matricula=1001, fecha=2026-11-25);",
                self._c9b_recorrido_vacaciones,
            ),
            CasoPrueba(
                "10A", "10. Trg cambio guardia", "OK",
                "Reprogramar guardia a otra fecha válida del mismo mes",
                "OK",
                "Mueve la guardia 1 (asignada a 1001) del 2026-11-02 al 2026-11-12 sin conflictos.",
                "UPDATE guardia SET inicio=2026-11-12 06:00, fin=14:00 WHERE id_guardia=1;",
                self._c10a_cambio_guardia_ok,
            ),
            CasoPrueba(
                "10B", "10. Trg cambio guardia", "FALLA",
                "Reprogramar guardia a vacaciones del médico asignado",
                "ORA-20003",
                "Mueve la guardia 1 (médico 1001) al 2026-11-25 (en sus vacaciones). Dispara ORA-20003.",
                "UPDATE guardia SET inicio=2026-11-25 06:00, fin=14:00 WHERE id_guardia=1;",
                self._c10b_cambio_guardia_vac,
            ),
            CasoPrueba(
                "10C", "10. Trg cambio guardia", "FALLA",
                "Reprogramar guardia a internación del médico asignado",
                "ORA-20004",
                "Mueve la guardia 2 (asignada a 1004) al 2026-10-15 (durante su internación I5). Dispara ORA-20004.",
                "UPDATE guardia SET inicio=2026-10-15 14:00, fin=22:00 WHERE id_guardia=2;",
                self._c10c_cambio_guardia_int,
            ),
            CasoPrueba(
                "10D", "10. Trg cambio guardia", "FALLA",
                "Reprogramar guardia a otro mes superando tope mensual",
                "ORA-20005",
                "Crea una guardia en junio 2028 para el Dr. 1004 y la mueve a nov-2026 donde ya tiene 2/2. Dispara ORA-20005.",
                "INSERT guardia+desempena (2028-06, 1004); UPDATE guardia SET inicio=2026-11-15;",
                self._c10d_cambio_guardia_tope,
            ),
            CasoPrueba(
                "11A", "11. Tx Internaciones", "OK",
                "Ciclo completo: internar -> cambiar cama -> repetir -> alta",
                "OK (3 filas OCUPA)",
                "Ejecuta vía InternacionController el ciclo completo repitiendo la cama inicial y verifica 3 filas cerradas en OCUPA y cama liberada.",
                "internar(c1) -> cambiar_cama(c2) -> cambiar_cama(c1) -> dar_alta() [ROLLBACK]",
                self._c11a_ciclo_internacion_completo,
            ),
            CasoPrueba(
                "11B", "11. Tx Internaciones", "FALLA",
                "Internar paciente que ya tiene internación activa",
                "ReglaError",
                "Llama a InternacionController.internar() para Ana López (30111111, con I1 activa). Debe rechazarse sin insertar filas.",
                "internacion_ctrl.internar(dni='30111111', matricula=1001, cama_libre)",
                self._c11b_internar_doble_activa,
            ),
            CasoPrueba(
                "11C", "11. Tx Internaciones", "FALLA",
                "Atomicidad: internar() en cama ocupada revierte INTERNACION",
                "ORA-20011 + 0 huérf.",
                "Llama a InternacionController.internar() sobre una cama ocupada. Falla en OCUPA (ORA-20011) y el ROLLBACK borra la INTERNACION.",
                "internacion_ctrl.internar('30333333', 1001, cama_ocupada) -> ROLLBACK",
                self._c11c_internar_cama_ocupada_rollback,
            ),
            CasoPrueba(
                "12A", "12. Tx Guardias", "FALLA",
                "Guardia con turnos no contiguos (Mañana + Noche)",
                "ReglaError",
                "Llama a GuardiaController.alta_guardia() con turnos [1, 3]. Debe rechazarse antes de tocar la base.",
                "guardia_ctrl.alta_guardia(1002, 'Cardiologia', 2028-07-10, [1, 3])",
                self._c12a_guardia_turnos_no_contiguos,
            ),
            CasoPrueba(
                "12B", "12. Tx Guardias", "FALLA",
                "Mismo médico en dos especialidades en el mismo horario",
                "ReglaError",
                "Asigna al Dr. 1002 en Cardiología y luego intenta Terapia Intensiva el mismo día y turno. Debe rechazarse sin huérfanas.",
                "alta_guardia(1002, 'Cardiologia') + alta_guardia(1002, 'Terapia Intensiva') [ROLLBACK]",
                self._c12b_guardia_solapa_mismo_medico,
            ),
            CasoPrueba(
                "12C", "12. Tx Guardias", "FALLA",
                "Dos médicos distintos en la misma especialidad y horario",
                "ReglaError",
                "Asigna a la Dra. 1001 en Clínica Médica y luego intenta asignar al Dr. 1004 en la misma especialidad y turno.",
                "alta_guardia(1001, 'Clinica Medica') + alta_guardia(1004, 'Clinica Medica') [ROLLBACK]",
                self._c12c_guardia_solapa_especialidad,
            ),
            CasoPrueba(
                "13A", "13. Tx Rondas", "FALLA",
                "Registrar recorrido en día distinto al de la ronda",
                "ReglaError",
                "Ronda 1 corresponde a MARTES; llamar a RondaController.registrar_recorrido() en miércoles debe ser rechazado.",
                "ronda_ctrl.registrar_recorrido(ronda=1, med=1001, 2028-07-12 miércoles)",
                self._c13a_recorrido_dia_incorrecto,
            ),
            CasoPrueba(
                "13B", "13. Tx Rondas", "FALLA",
                "Registrar recorrido en vacaciones vía RondaController",
                "ORA-20013",
                "Envía un martes válido (2026-11-24) dentro de vacaciones de 1001; verifica que llega sin interferencia al trigger ORA-20013.",
                "ronda_ctrl.registrar_recorrido(ronda=1, med=1001, 2026-11-24 martes)",
                self._c13b_recorrido_vacaciones_via_ctrl,
            ),
            CasoPrueba(
                "13C", "13. Tx Rondas", "FALLA",
                "Superar tope máximo de comentarios por recorrido (= camas)",
                "ReglaError",
                "Completa comentarios en Recorrido 3 (Ronda 2, 3 camas) hasta el tope y verifica que el siguiente comentario es rechazado.",
                "ronda_ctrl.registrar_comentario(rec=3, int=2) hasta max_camas + 1 [ROLLBACK]",
                self._c13c_comentarios_tope_ronda,
            ),
            CasoPrueba(
                "14A", "14. Tx Pacientes/Méd.", "OK",
                "Baja de médico-paciente conserva PERSONA y MEDICO",
                "OK",
                "Da de alta a la Dra. 1001 (DNI 20111111) como paciente y luego la elimina; verifica que PACIENTE se borra pero PERSONA y MEDICO siguen.",
                "paciente_ctrl.alta('20111111') -> paciente_ctrl.eliminar('20111111') [ROLLBACK]",
                self._c14a_baja_medico_paciente_conserva_persona,
            ),
            CasoPrueba(
                "14B", "14. Tx Pacientes/Méd.", "FALLA",
                "Eliminar paciente que posee internaciones registradas",
                "ReglaError",
                "Llama a PacienteController.eliminar('30111111'). Como Ana López tiene internaciones, debe ser rechazado.",
                "paciente_ctrl.eliminar('30111111')",
                self._c14b_baja_paciente_con_internaciones,
            ),
            CasoPrueba(
                "14C", "14. Tx Pacientes/Méd.", "FALLA",
                "Atomicidad: quitar especialidad con guardias revierte todo",
                "ORA-02292 + ROLLBACK",
                "Edita nombre, tope y quita 'Clinica Medica' a la Dra. 1001. Falla FK_DESEMPENA_POSEE (ORA-02292) y revierte PERSONA, MEDICO y AUDITORIA.",
                "medico_ctrl.editar(1001, sin 'Clinica Medica') -> ORA-02292 + ROLLBACK",
                self._c14c_editar_medico_rollback_fk,
            ),
            CasoPrueba(
                "15A", "15. Concurrencia", "FALLA",
                "Bloqueo concurrente de cama con 2 conexiones (~5s WAIT 5)",
                "ORA-00054 / 30006",
                "Cnx1 bloquea una cama libre con FOR UPDATE WAIT 5 sin commit y Cnx2 intenta internar() en esa cama. Debe fallar con ErrorConcurrencia.",
                "Cnx1: SELECT cama FOR UPDATE WAIT 5 | Cnx2: internar() -> ErrorConcurrencia [ROLLBACK]",
                self._c15a_concurrencia_cama_wait5,
            ),
        ]
