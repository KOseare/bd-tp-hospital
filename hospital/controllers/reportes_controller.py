"""Controlador de reportes obligatorios (`05_procedures.sql`) y consulta de camas."""

from __future__ import annotations

from hospital.controllers._validadores import validar_dni
from hospital.models.entities import CamaDisponible, CamaEstado, ComentarioVisita, ResumenSector
from hospital.models.exceptions import ReglaError
from hospital.persistence import cama_dao, reportes_dao
from hospital.persistence.connection import ConnectionManager


class ReportesController:
    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def camas_disponibles(self) -> tuple[list[ResumenSector], list[CamaDisponible]]:
        """Ejecuta `pr_camas_disponibles` y devuelve (resumen_por_sector, detalle)."""
        with self._db.conexion_lectura() as cnx:
            return reportes_dao.ejecutar_pr_camas_disponibles(cnx)

    def comentarios_internacion(
        self,
        id_internacion: int,
        dni: str,
    ) -> list[ComentarioVisita]:
        """Ejecuta `pr_comentarios_internacion` para una internación y DNI dados."""
        if not isinstance(id_internacion, int) or isinstance(id_internacion, bool) or id_internacion <= 0:
            raise ReglaError("El ID de internación debe ser un número entero positivo.")
        dni_ok = validar_dni(dni)
        with self._db.conexion_lectura() as cnx:
            return reportes_dao.ejecutar_pr_comentarios_internacion(cnx, id_internacion, dni_ok)

    def listar_sectores(self) -> list[str]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return cama_dao.listar_sectores(cur)

    def listar_camas_libres(self) -> list[tuple[int, int, str]]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return cama_dao.listar_camas_libres(cur)

    def listar_todas_las_camas(
        self,
        nombre_sector: str | None = None,
        solo_disponibles: bool | None = None,
    ) -> list[CamaEstado]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return cama_dao.listar_todas_con_estado(
                    cur,
                    nombre_sector=nombre_sector,
                    solo_disponibles=solo_disponibles,
                )
