"""Controlador transaccional de Médicos (`PERSONA` + `MEDICO` + `POSEE` + `VACACION`)."""

from __future__ import annotations

from datetime import datetime

from hospital.controllers._validadores import (
    validar_cuil,
    validar_dni,
    validar_matricula,
    validar_max_guardias,
    validar_texto,
)
from hospital.models.entities import Medico, Vacacion
from hospital.models.exceptions import ReglaError
from hospital.persistence import medico_dao, persona_dao
from hospital.persistence.connection import ConnectionManager


class MedicoController:
    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def listar(self, filtro: str | None = None) -> list[Medico]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                medicos = medico_dao.listar(cur, filtro=(filtro or "").strip() or None)
                for med in medicos:
                    med.especialidades = medico_dao.listar_especialidades_medico(cur, med.matricula)
                return medicos

    def obtener(self, matricula: int) -> Medico:
        mat_ok = validar_matricula(matricula)
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                med = medico_dao.obtener_por_matricula(cur, mat_ok)
                if med is None:
                    raise ReglaError(f"No existe un médico con matrícula {mat_ok}.")
                med.especialidades = medico_dao.listar_especialidades_medico(cur, mat_ok)
                return med

    def listar_especialidades(self) -> list[str]:
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return medico_dao.listar_especialidades(cur)

    def especialidades_de_guardia(self, matricula: int) -> list[str]:
        mat_ok = validar_matricula(matricula)
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return medico_dao.especialidades_de_guardia(cur, mat_ok)

    def listar_vacaciones(self, matricula: int | None = None) -> list[Vacacion]:
        if matricula is not None:
            matricula = validar_matricula(matricula)
        with self._db.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                return medico_dao.listar_vacaciones(cur, matricula=matricula)

    def detectar_especialidades_nuevas(self, especialidades: list[tuple[str, bool]]) -> list[str]:
        """Devuelve los nombres de especialidades que aún no existen en el catálogo."""
        existentes = set(self.listar_especialidades())
        nuevas: list[str] = []
        for nombre, _ in especialidades:
            limpio = (nombre or "").strip()
            if limpio and limpio not in existentes and limpio not in nuevas:
                nuevas.append(limpio)
        return nuevas

    def alta(
        self,
        matricula: int,
        dni: str,
        nombre: str,
        apellido: str,
        cuil: str,
        fecha_ingreso: datetime,
        max_guardias: int,
        foto: bytes | None,
        especialidades: list[tuple[str, bool]],
        permitir_nuevas_especialidades: bool = False,
    ) -> Medico:
        """Alta atómica en PERSONA + MEDICO (BLOB) + POSEE (auditada por triggers)."""
        mat_ok = validar_matricula(matricula)
        dni_ok = validar_dni(dni)
        nom_ok = validar_texto(nombre, "nombre")
        ape_ok = validar_texto(apellido, "apellido")
        cuil_ok = validar_cuil(cuil)
        max_ok = validar_max_guardias(max_guardias)

        esp_limpias: list[tuple[str, bool]] = []
        vistas: set[str] = set()
        for nombre_esp, hace_guardia in especialidades:
            esp_ok = validar_texto(nombre_esp, "especialidad")
            if esp_ok not in vistas:
                vistas.add(esp_ok)
                esp_limpias.append((esp_ok, bool(hace_guardia)))

        with self._db.transaccion() as cur:
            if medico_dao.existe_matricula(cur, mat_ok):
                raise ReglaError("Ya existe un médico con esa matrícula.")
            if medico_dao.existe_dni(cur, dni_ok):
                raise ReglaError("Ya existe un médico con ese DNI.")
            if medico_dao.existe_cuil(cur, cuil_ok):
                raise ReglaError("Ya existe un médico con ese CUIL/CUIT.")

            if not persona_dao.existe(cur, dni_ok):
                persona_dao.insertar(cur, dni_ok, nom_ok, ape_ok)
            else:
                persona_dao.actualizar(cur, dni_ok, nom_ok, ape_ok)

            medico_dao.insertar(cur, mat_ok, dni_ok, cuil_ok, fecha_ingreso, max_ok, foto)

            for esp_ok, hace_guardia in esp_limpias:
                if not medico_dao.existe_especialidad(cur, esp_ok):
                    if not permitir_nuevas_especialidades:
                        raise ReglaError(
                            f"La especialidad '{esp_ok}' no existe en el catálogo. "
                            "Confirmá su creación o elegí una especialidad existente."
                        )
                    medico_dao.insertar_especialidad(cur, esp_ok)
                medico_dao.upsert_posee(cur, mat_ok, esp_ok, hace_guardia)

            creado = medico_dao.obtener_por_matricula(cur, mat_ok)
            assert creado is not None
            creado.especialidades = medico_dao.listar_especialidades_medico(cur, mat_ok)
            return creado

    def editar(
        self,
        matricula: int,
        nombre: str,
        apellido: str,
        cuil: str,
        fecha_ingreso: datetime,
        max_guardias: int,
        especialidades: list[tuple[str, bool]] | None = None,
        foto: bytes | None = None,
        actualizar_foto: bool = False,
        permitir_nuevas_especialidades: bool = False,
    ) -> Medico:
        """Actualización atómica de PERSONA + MEDICO + sincronización de POSEE."""
        mat_ok = validar_matricula(matricula)
        nom_ok = validar_texto(nombre, "nombre")
        ape_ok = validar_texto(apellido, "apellido")
        cuil_ok = validar_cuil(cuil)
        max_ok = validar_max_guardias(max_guardias)

        with self._db.transaccion() as cur:
            if not medico_dao.bloquear(cur, mat_ok):
                raise ReglaError(f"No existe un médico con matrícula {mat_ok}.")
            actual = medico_dao.obtener_por_matricula(cur, mat_ok)
            assert actual is not None

            if medico_dao.existe_cuil(cur, cuil_ok, excluir_matricula=mat_ok):
                raise ReglaError("Ya existe otro médico con ese CUIL/CUIT.")

            persona_dao.actualizar(cur, actual.dni, nom_ok, ape_ok)
            medico_dao.actualizar(
                cur,
                mat_ok,
                cuil_ok,
                fecha_ingreso,
                max_ok,
                foto=foto,
                actualizar_foto=actualizar_foto,
            )

            if especialidades is not None:
                nuevas_map: dict[str, bool] = {}
                for nombre_esp, hace_guardia in especialidades:
                    esp_ok = validar_texto(nombre_esp, "especialidad")
                    nuevas_map[esp_ok] = bool(hace_guardia)

                actuales_esp = {
                    e.nombre_especialidad
                    for e in medico_dao.listar_especialidades_medico(cur, mat_ok)
                }
                for esp_ok, hace_guardia in nuevas_map.items():
                    if not medico_dao.existe_especialidad(cur, esp_ok):
                        if not permitir_nuevas_especialidades:
                            raise ReglaError(
                                f"La especialidad '{esp_ok}' no existe en el catálogo."
                            )
                        medico_dao.insertar_especialidad(cur, esp_ok)
                    medico_dao.upsert_posee(cur, mat_ok, esp_ok, hace_guardia)

                for esp_quitar in sorted(actuales_esp - set(nuevas_map.keys())):
                    medico_dao.eliminar_posee(cur, mat_ok, esp_quitar)

            actualizado = medico_dao.obtener_por_matricula(cur, mat_ok)
            assert actualizado is not None
            actualizado.especialidades = medico_dao.listar_especialidades_medico(cur, mat_ok)
            return actualizado
