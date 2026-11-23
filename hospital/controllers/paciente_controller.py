"""Controlador CRUD transaccional de Pacientes (`PERSONA` + `PACIENTE`)."""

from __future__ import annotations

from datetime import date

from hospital.controllers._validadores import (
    validar_dni,
    validar_fecha_nacimiento,
    validar_sexo,
    validar_texto,
)
from hospital.models.entities import Paciente
from hospital.models.exceptions import ReglaError
from hospital.persistence import medico_dao, paciente_dao, persona_dao
from hospital.persistence.connection import ConnectionManager


class PacienteController:
    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def listar(self, filtro: str | None = None) -> list[Paciente]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return paciente_dao.listar(cur, filtro=(filtro or "").strip() or None)

    def obtener(self, dni: str) -> Paciente:
        dni_ok = validar_dni(dni)
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                pac = paciente_dao.obtener_por_dni(cur, dni_ok)
                if pac is None:
                    raise ReglaError(f"No existe un paciente con DNI {dni_ok}.")
                return pac

    def alta(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        fecha_nacimiento: date,
        sexo: str,
    ) -> Paciente:
        """Alta atómica en PERSONA + PACIENTE (reutiliza PERSONA si ya es médico)."""
        dni_ok = validar_dni(dni)
        nom_ok = validar_texto(nombre, "nombre")
        ape_ok = validar_texto(apellido, "apellido")
        nac_ok = validar_fecha_nacimiento(fecha_nacimiento)
        sexo_ok = validar_sexo(sexo)

        with self._db.transaccion() as cur:
            if paciente_dao.existe(cur, dni_ok):
                raise ReglaError("Ya existe un paciente con ese DNI.")
            if not persona_dao.existe(cur, dni_ok):
                persona_dao.insertar(cur, dni_ok, nom_ok, ape_ok)
            else:
                persona_dao.actualizar(cur, dni_ok, nom_ok, ape_ok)
            paciente_dao.insertar(cur, dni_ok, nac_ok, sexo_ok)
            creado = paciente_dao.obtener_por_dni(cur, dni_ok)
            assert creado is not None
            return creado

    def editar(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        fecha_nacimiento: date,
        sexo: str,
    ) -> Paciente:
        """Modificación atómica en PERSONA + PACIENTE."""
        dni_ok = validar_dni(dni)
        nom_ok = validar_texto(nombre, "nombre")
        ape_ok = validar_texto(apellido, "apellido")
        nac_ok = validar_fecha_nacimiento(fecha_nacimiento)
        sexo_ok = validar_sexo(sexo)

        with self._db.transaccion() as cur:
            if not paciente_dao.bloquear(cur, dni_ok):
                raise ReglaError(f"No existe un paciente con DNI {dni_ok}.")
            persona_dao.actualizar(cur, dni_ok, nom_ok, ape_ok)
            paciente_dao.actualizar(cur, dni_ok, nac_ok, sexo_ok)
            actualizado = paciente_dao.obtener_por_dni(cur, dni_ok)
            assert actualizado is not None
            return actualizado

    def eliminar(self, dni: str) -> None:
        """Baja atómica: rechaza si tiene internaciones; conserva PERSONA si también es médico."""
        dni_ok = validar_dni(dni)
        with self._db.transaccion() as cur:
            if not paciente_dao.bloquear(cur, dni_ok):
                raise ReglaError(f"No existe un paciente con DNI {dni_ok}.")
            if paciente_dao.tiene_internaciones(cur, dni_ok):
                raise ReglaError(
                    "No se puede eliminar el paciente porque tiene internaciones registradas."
                )
            paciente_dao.eliminar(cur, dni_ok)
            if not medico_dao.existe_dni(cur, dni_ok):
                persona_dao.eliminar(cur, dni_ok)
