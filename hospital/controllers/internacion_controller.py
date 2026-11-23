"""Controlador transaccional de Internaciones y Gestión de Camas (`INTERNACION` + `OCUPA`)."""

from __future__ import annotations

from datetime import datetime

from hospital.controllers._validadores import comparar_datetimes, validar_dni, validar_matricula
from hospital.models.entities import Internacion, OcupacionCama
from hospital.models.exceptions import ReglaError
from hospital.persistence import cama_dao, internacion_dao, medico_dao, paciente_dao
from hospital.persistence.connection import ConnectionManager


class InternacionController:
    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def listar(
        self,
        solo_activas: bool = True,
        dni_paciente: str | None = None,
    ) -> list[Internacion]:
        dni_filtro = (dni_paciente or "").strip() or None
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return internacion_dao.listar(
                    cur,
                    solo_activas=solo_activas,
                    dni_paciente=dni_filtro,
                )

    def listar_ocupaciones(self, id_internacion: int) -> list[OcupacionCama]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return internacion_dao.listar_ocupaciones(cur, int(id_internacion))

    def internar(
        self,
        dni: str,
        matricula: int,
        nro_hab: int,
        nro_cama: int,
        fecha_inicio: datetime | None = None,
    ) -> int:
        """Transacción: crea INTERNACION y asigna la primera cama en OCUPA.

        Usa bloqueos `FOR UPDATE WAIT 5` sobre PACIENTE y CAMA para serializar
        operaciones concurrentes sin colgar la interfaz Tkinter.
        Delega en triggers de Oracle (`06_triggers.sql`):
          - trg_internacion_medico_paciente (ORA-20001)
          - trg_validar_ocupa (ORA-20010..20012)
        """
        dni_ok = validar_dni(dni)
        mat_ok = validar_matricula(int(matricula))
        ahora = fecha_inicio or datetime.now()

        with self._db.transaccion() as cur:
            if not paciente_dao.bloquear(cur, dni_ok):
                raise ReglaError("El DNI no corresponde a un paciente registrado.")
            if not medico_dao.existe_matricula(cur, mat_ok):
                raise ReglaError("La matrícula no corresponde a un médico registrado.")
            if internacion_dao.tiene_internacion_abierta(cur, dni_ok):
                raise ReglaError("El paciente ya tiene una internación en curso.")
            if not cama_dao.bloquear_cama(cur, int(nro_hab), int(nro_cama)):
                raise ReglaError("La cama indicada no existe.")

            id_internacion = internacion_dao.insertar_internacion(cur, ahora, mat_ok, dni_ok)
            internacion_dao.insertar_ocupa(cur, id_internacion, ahora, int(nro_hab), int(nro_cama))
            return id_internacion

    def cambiar_cama(
        self,
        id_internacion: int,
        nro_hab: int,
        nro_cama: int,
        fecha_cambio: datetime | None = None,
    ) -> None:
        """Transacción: cierra la ocupación actual en OCUPA y abre la nueva cama."""
        ahora = fecha_cambio or datetime.now()

        with self._db.transaccion() as cur:
            fechas_int = internacion_dao.bloquear_internacion(cur, int(id_internacion))
            if fechas_int is None:
                raise ReglaError("La internación no existe.")
            fecha_ini_int, fecha_fin_int = fechas_int
            if fecha_fin_int is not None:
                raise ReglaError("La internación ya tiene el alta.")

            if comparar_datetimes(ahora, fecha_ini_int) < 0:
                raise ReglaError(
                    "La fecha del cambio de cama no puede ser anterior al inicio de la internación."
                )

            actual = internacion_dao.bloquear_ocupacion_activa(cur, int(id_internacion))
            if actual is not None:
                hab_actual, cama_actual, fecha_asig_actual = actual
                if (hab_actual, cama_actual) == (int(nro_hab), int(nro_cama)):
                    raise ReglaError("El paciente ya está en esa cama.")
                if comparar_datetimes(ahora, fecha_asig_actual) <= 0:
                    raise ReglaError(
                        "La fecha del traslado debe ser posterior a la fecha de asignación de la cama actual."
                    )

            if not cama_dao.bloquear_cama(cur, int(nro_hab), int(nro_cama)):
                raise ReglaError("La cama destino no existe.")

            if actual is not None:
                internacion_dao.cerrar_ocupacion_activa(cur, int(id_internacion), ahora)
            internacion_dao.insertar_ocupa(cur, int(id_internacion), ahora, int(nro_hab), int(nro_cama))

    def dar_alta(self, id_internacion: int, fecha_alta: datetime | None = None) -> None:
        """Transacción: libera la cama activa en OCUPA y cierra la INTERNACION."""
        ahora = fecha_alta or datetime.now()

        with self._db.transaccion() as cur:
            fechas_int = internacion_dao.bloquear_internacion(cur, int(id_internacion))
            if fechas_int is None:
                raise ReglaError("La internación no existe.")
            fecha_ini_int, fecha_fin_int = fechas_int
            if fecha_fin_int is not None:
                raise ReglaError("La internación ya tiene el alta.")

            if comparar_datetimes(ahora, fecha_ini_int) <= 0:
                raise ReglaError(
                    "La fecha de alta debe ser posterior a la fecha de inicio de la internación."
                )

            actual = internacion_dao.bloquear_ocupacion_activa(cur, int(id_internacion))
            if actual is not None:
                _, _, fecha_asig_actual = actual
                if comparar_datetimes(ahora, fecha_asig_actual) <= 0:
                    raise ReglaError(
                        "La fecha de alta debe ser posterior a la última asignación de cama."
                    )
                internacion_dao.cerrar_ocupacion_activa(cur, int(id_internacion), ahora)

            internacion_dao.cerrar_internacion(cur, int(id_internacion), ahora)
