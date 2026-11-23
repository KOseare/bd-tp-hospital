"""Controlador de Rondas, Recorridos y Comentarios de visitas médicas."""

from __future__ import annotations

from datetime import datetime

from hospital.controllers._validadores import dia_semana_es, validar_matricula, validar_texto
from hospital.models.entities import Recorrido, Ronda
from hospital.models.exceptions import ReglaError
from hospital.persistence import internacion_dao, medico_dao, ronda_dao
from hospital.persistence.connection import ConnectionManager


class RondaController:
    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def listar_rondas(self) -> list[Ronda]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return ronda_dao.listar_rondas(cur)

    def listar_recorridos(
        self,
        id_ronda: int | None = None,
        matricula_medico: int | None = None,
    ) -> list[Recorrido]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return ronda_dao.listar_recorridos(
                    cur,
                    id_ronda=id_ronda,
                    matricula_medico=matricula_medico,
                )

    def listar_comentarios_de_recorrido(
        self,
        id_recorrido: int,
    ) -> list[tuple[int, int, str, str, str]]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return ronda_dao.listar_comentarios_de_recorrido(cur, int(id_recorrido))

    def registrar_recorrido(
        self,
        id_ronda: int,
        matricula_medico: int,
        fecha_recorrido: datetime,
    ) -> int:
        """Registra un recorrido médico para una ronda (trigger ORA-20013 valida vacaciones)."""
        mat_ok = validar_matricula(int(matricula_medico))
        if not isinstance(fecha_recorrido, datetime):
            raise ReglaError("Fecha y hora de recorrido inválidas.")

        with self._db.transaccion() as cur:
            ronda = ronda_dao.obtener_ronda(cur, int(id_ronda))
            if ronda is None:
                raise ReglaError("La ronda indicada no existe.")
            if not medico_dao.existe_matricula(cur, mat_ok):
                raise ReglaError("La matrícula no corresponde a un médico registrado.")

            dia_real = dia_semana_es(fecha_recorrido)
            if dia_real != ronda.dia_ronda.upper():
                raise ReglaError(
                    f"La ronda #{ronda.id_ronda} corresponde al día {ronda.dia_ronda}, "
                    f"pero la fecha elegida cae {dia_real}."
                )

            return ronda_dao.insertar_recorrido(cur, ronda.id_ronda, mat_ok, fecha_recorrido)

    def registrar_comentario(
        self,
        id_recorrido: int,
        id_internacion: int,
        texto_comentario: str,
    ) -> int:
        """Registra un comentario clínico de recorrido sobre una internación.

        Valida tope de comentarios por recorrido (suma de camas de la ronda) y delega
        en `trg_validar_comentario` (ORA-20007 médico=paciente, ORA-20008 fecha fuera
        de internación, ORA-20009 habitación fuera de la ronda).
        """
        texto_ok = validar_texto(texto_comentario, "comentario", max_len=2000)

        with self._db.transaccion() as cur:
            # Bloqueo en orden fijo (RECORRIDO -> INTERNACION) para serializar el tope de comentarios
            if not ronda_dao.bloquear_recorrido(cur, int(id_recorrido)):
                raise ReglaError("El recorrido seleccionado no existe.")
            recorrido = ronda_dao.obtener_recorrido(cur, int(id_recorrido))
            assert recorrido is not None
            if internacion_dao.bloquear_internacion(cur, int(id_internacion)) is None:
                raise ReglaError("La internación seleccionada no existe.")

            max_comentarios = ronda_dao.contar_camas_en_ronda(cur, recorrido.id_ronda)
            actuales = ronda_dao.contar_comentarios_recorrido(cur, recorrido.id_recorrido)
            if max_comentarios > 0 and actuales >= max_comentarios:
                raise ReglaError(
                    f"El recorrido #{recorrido.id_recorrido} ya alcanzó el máximo de "
                    f"{max_comentarios} comentario(s) permitido(s) para las camas de su ronda."
                )

            return ronda_dao.insertar_comentario(
                cur,
                int(id_internacion),
                recorrido.id_recorrido,
                texto_ok,
            )
