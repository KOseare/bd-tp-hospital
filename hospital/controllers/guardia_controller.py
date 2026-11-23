"""Controlador transaccional de Guardias y consulta de Auditoría."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from hospital.config import TURNOS_GUARDIA
from hospital.controllers._validadores import validar_matricula, validar_texto
from hospital.models.entities import AuditoriaGuardia, Guardia
from hospital.models.exceptions import ReglaError
from hospital.persistence import auditoria_dao, guardia_dao, medico_dao
from hospital.persistence.connection import ConnectionManager


def calcular_intervalo(dia: date, turnos: list[int]) -> tuple[list[int], datetime, datetime]:
    """Devuelve `(turnos ordenados, inicio, fin)`. Los turnos de una guardia deben ser contiguos."""
    turnos_ord = sorted(set(int(t) for t in turnos))
    if not turnos_ord:
        raise ReglaError("Elegí al menos un turno.")
    for t in turnos_ord:
        if t not in TURNOS_GUARDIA:
            raise ReglaError(f"Turno inválido: {t}.")
    if turnos_ord != list(range(turnos_ord[0], turnos_ord[-1] + 1)):
        raise ReglaError("Los turnos de una misma guardia tienen que ser contiguos.")

    inicio = datetime.combine(dia, time(TURNOS_GUARDIA[turnos_ord[0]][1]))
    fin = datetime.combine(dia, time(TURNOS_GUARDIA[turnos_ord[-1]][1])) + timedelta(hours=8)
    return turnos_ord, inicio, fin


class GuardiaController:
    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def listar(
        self,
        matricula_medico: int | None = None,
        nombre_especialidad: str | None = None,
    ) -> list[Guardia]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return guardia_dao.listar(
                    cur,
                    matricula_medico=matricula_medico,
                    nombre_especialidad=(nombre_especialidad or "").strip() or None,
                )

    def listar_auditoria(
        self,
        tabla_afectada: str | None = None,
        limite: int = 300,
    ) -> list[AuditoriaGuardia]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return auditoria_dao.listar(
                    cur,
                    tabla_afectada=tabla_afectada,
                    limite=limite,
                )

    def alta_guardia(
        self,
        matricula: int,
        especialidad: str,
        dia: date,
        turnos: list[int],
    ) -> int:
        """Transacción: crea GUARDIA, sus turnos y DESEMPENA.

        Bloquea MEDICO (`FOR UPDATE WAIT 5`), valida que no se superponga con otra
        guardia de la especialidad ni del mismo médico en otra especialidad, y delega
        en `trg_validar_asignacion_guardia` (ORA-20002..20005). Ante error hace ROLLBACK
        total (incluyendo los registros generados en AUDITORIA_GUARDIAS).
        """
        mat_ok = validar_matricula(int(matricula))
        esp_ok = validar_texto(especialidad, "especialidad")
        turnos_ord, inicio, fin = calcular_intervalo(dia, turnos)

        with self._db.transaccion() as cur:
            # Orden fijo de bloqueos (ESPECIALIDAD -> MEDICO) para evitar deadlocks y
            # serializar asignaciones concurrentes de dos médicos distintos a la misma especialidad.
            if not medico_dao.bloquear_especialidad(cur, esp_ok):
                raise ReglaError("La especialidad indicada no existe.")

            if not medico_dao.bloquear(cur, mat_ok):
                raise ReglaError("El médico no existe.")

            if not medico_dao.posee_especialidad(cur, mat_ok, esp_ok):
                raise ReglaError("El médico no posee esa especialidad.")

            if guardia_dao.existe_solapamiento_medico(cur, mat_ok, inicio, fin):
                raise ReglaError(
                    "El médico ya tiene otra guardia asignada en ese horario."
                )

            if guardia_dao.existe_solapamiento_especialidad(cur, esp_ok, inicio, fin):
                raise ReglaError(
                    "Ya hay un médico asignado a esa especialidad en ese horario."
                )

            id_guardia = guardia_dao.insertar_guardia(cur, inicio, fin)
            for t in turnos_ord:
                guardia_dao.insertar_turno(cur, id_guardia, t)
            guardia_dao.insertar_desempena(cur, mat_ok, esp_ok, id_guardia)
            return id_guardia
