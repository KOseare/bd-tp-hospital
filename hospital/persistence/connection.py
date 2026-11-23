"""Gestión del pool de conexiones Oracle, demarcación transaccional y traducción de errores."""

from __future__ import annotations

import atexit
import re
from contextlib import contextmanager
from typing import Any, Callable, Iterator

import oracledb

from hospital.config import OracleConfig
from hospital.models.exceptions import (
    AppError,
    ErrorBaseDatos,
    ErrorConcurrencia,
    ErrorConexion,
    ErrorTrigger,
    ReglaError,
)

# Devuelve BLOBs directamente como bytes sin depender del cursor abierto
oracledb.defaults.fetch_lobs = False

_UNIQUE_MESSAGES: dict[str, str] = {
    "PK_PERSONA": "Ya existe una persona registrada con ese DNI.",
    "PK_PACIENTE": "Ya existe un paciente registrado con ese DNI.",
    "PK_MEDICO": "Ya existe un médico registrado con esa matrícula.",
    "UQ_MEDICO_DNI": "Ya existe un médico registrado con ese DNI.",
    "UQ_MEDICO_CUIL": "Ya existe un médico registrado con ese CUIL/CUIT.",
    "PK_CAMA": "Ya existe esa cama registrada en la habitación.",
    "PK_INTERNACION": "Ya existe una internación con ese identificador.",
    "PK_OCUPA": "Ya existe una asignación de cama para esa internación en esa misma fecha y hora.",
    "PK_ESPECIALIDAD": "Ya existe esa especialidad.",
    "PK_POSEE": "El médico ya tiene registrada esa especialidad.",
    "PK_GUARDIA": "Ya existe una guardia con ese identificador.",
    "PK_GUARDIA_MANANA": "La guardia ya tiene asignado el turno mañana.",
    "PK_GUARDIA_TARDE": "La guardia ya tiene asignado el turno tarde.",
    "PK_GUARDIA_NOCHE": "La guardia ya tiene asignado el turno noche.",
    "PK_DESEMPENA": "El médico ya tiene asignada esa guardia en esa especialidad.",
    "PK_VACACION": "El médico ya registra vacaciones con esa fecha de inicio.",
    "UQ_VACACION_FIN": "El médico ya registra vacaciones con esa fecha de fin.",
    "PK_ES_VISITADA": "La habitación ya pertenece a esa ronda.",
}

_CHECK_MESSAGES: dict[str, str] = {
    "CK_CAMA_NRO": "El número de cama debe ser mayor o igual a 1.",
    "CK_PERSONA_DNI": "El DNI debe tener entre 6 y 9 dígitos numéricos.",
    "CK_PACIENTE_SEXO": "El sexo del paciente debe ser 'F', 'M' o 'X'.",
    "CK_MEDICO_CUIL": "El CUIL/CUIT debe tener exactamente 11 dígitos numéricos.",
    "CK_MEDICO_CANT_GUARDIAS": "El máximo de guardias por mes debe ser mayor o igual a 0.",
    "CK_INTERNACION_FECHAS": "La fecha de alta debe ser estrictamente posterior a la fecha de inicio de la internación.",
    "CK_OCUPA_FECHAS": "La fecha de liberación de cama debe ser estrictamente posterior a la fecha de asignación.",
    "CK_POSEE_HACE_GUARDIA": "El indicador de guardia debe ser 'S' o 'N'.",
    "CK_GUARDIA_FECHAS": "La fecha de fin de la guardia debe ser posterior a la fecha de inicio.",
    "CK_VACACION_FECHAS": "La fecha de fin de vacaciones debe ser posterior a la fecha de inicio.",
    "CK_RONDA_DIA": "El día de la ronda debe ser un día válido de la semana (LUNES..DOMINGO).",
    "CK_RONDA_TURNO": "El turno de la ronda debe ser mayor o igual a 1.",
}

_FK_PARENT_MESSAGES: dict[str, str] = {
    "FK_PACIENTE_PERSONA": "El DNI indicado no existe en PERSONA.",
    "FK_MEDICO_PERSONA": "El DNI indicado no existe en PERSONA.",
    "FK_INTERNACION_MEDICO": "La matrícula no corresponde a un médico registrado.",
    "FK_INTERNACION_PACIENTE": "El DNI no corresponde a un paciente registrado.",
    "FK_OCUPA_INTERNACION": "La internación indicada no existe.",
    "FK_OCUPA_CAMA": "La cama indicada no existe en esa habitación.",
    "FK_POSEE_MEDICO": "El médico indicado no existe.",
    "FK_POSEE_ESPECIALIDAD": "La especialidad indicada no existe.",
    "FK_DESEMPENA_POSEE": "El médico no posee la especialidad seleccionada.",
    "FK_DESEMPENA_GUARDIA": "La guardia indicada no existe.",
    "FK_RECORRIDO_RONDA": "La ronda indicada no existe.",
    "FK_RECORRIDO_MEDICO": "El médico indicado no existe.",
    "FK_COMENTARIO_INTERNACION": "La internación indicada no existe.",
    "FK_COMENTARIO_RECORRIDO": "El recorrido indicado no existe.",
}

_FK_CHILD_MESSAGES: dict[str, str] = {
    "FK_INTERNACION_PACIENTE": "No se puede eliminar el paciente porque tiene internaciones registradas.",
    "FK_DESEMPENA_POSEE": "No se puede quitar la especialidad porque el médico ya tiene guardias asignadas en ella.",
    "FK_INTERNACION_MEDICO": "No se puede eliminar el médico porque figura como médico principal en internaciones.",
}

_CONNECTION_CODES = {1017, 1033, 1034, 1089, 12154, 12514, 12541, 12545, 28000}


def _extraer_constraint(mensaje: str, catalogo: dict[str, str]) -> str | None:
    """Extrae el nombre exacto de una constraint Oracle evitando colisiones por prefijo."""
    upper = mensaje.upper()
    m = re.search(r"\((?:[A-Z0-9_$#]+\.)?([A-Z0-9_$#]+)\)", upper)
    if m and m.group(1) in catalogo:
        return m.group(1)
    for nombre in sorted(catalogo.keys(), key=len, reverse=True):
        if re.search(rf"(?<![A-Z0-9_$#]){re.escape(nombre)}(?![A-Z0-9_$#])", upper):
            return nombre
    return None


def traducir_error_oracle(exc: Exception) -> AppError:
    """Convierte una excepción `oracledb.Error` en una excepción clara de dominio."""
    if isinstance(exc, AppError):
        return exc

    err = exc.args[0] if getattr(exc, "args", None) else None
    codigo = getattr(err, "code", None)
    mensaje_raw = getattr(err, "message", None) or str(exc)
    primera = mensaje_raw.strip().splitlines()[0] if mensaje_raw.strip() else str(exc)

    if codigo is None:
        m_ora = re.search(r"ORA-(\d+)", primera)
        if m_ora:
            codigo = int(m_ora.group(1))

    # Errores de triggers personalizados (06_triggers.sql: ORA-20001..20013)
    if codigo is not None and 20000 <= codigo <= 20999:
        texto = re.sub(r"^ORA-\d+:\s*", "", primera).strip()
        return ErrorTrigger(codigo, texto)

    # Bloqueo concurrente (FOR UPDATE WAIT / NOWAIT)
    if codigo in (54, 30006):
        return ErrorConcurrencia(
            "El registro está siendo utilizado por otra operación en este momento. "
            "Esperá unos segundos e intentá nuevamente.",
            codigo_ora=codigo,
            detalle=mensaje_raw,
        )

    # Clave duplicada / UNIQUE
    if codigo == 1:
        constraint = _extraer_constraint(mensaje_raw, _UNIQUE_MESSAGES)
        msg = (
            _UNIQUE_MESSAGES[constraint]
            if constraint
            else "Ya existe un registro con esos datos únicos."
        )
        return ReglaError(msg, codigo_ora=1, detalle=mensaje_raw)

    # Violación de CHECK
    if codigo == 2290:
        constraint = _extraer_constraint(mensaje_raw, _CHECK_MESSAGES)
        msg = (
            _CHECK_MESSAGES[constraint]
            if constraint
            else "Alguno de los valores ingresados incumple una restricción de la base de datos."
        )
        return ReglaError(msg, codigo_ora=2290, detalle=mensaje_raw)

    # FK padre inexistente
    if codigo == 2291:
        constraint = _extraer_constraint(mensaje_raw, _FK_PARENT_MESSAGES)
        msg = (
            _FK_PARENT_MESSAGES[constraint]
            if constraint
            else "El registro referenciado no existe en la base de datos."
        )
        return ReglaError(msg, codigo_ora=2291, detalle=mensaje_raw)

    # FK registros hijos dependientes
    if codigo == 2292:
        constraint = _extraer_constraint(mensaje_raw, _FK_CHILD_MESSAGES)
        msg = (
            _FK_CHILD_MESSAGES[constraint]
            if constraint
            else "No se puede eliminar o modificar el registro porque tiene datos asociados."
        )
        return ReglaError(msg, codigo_ora=2292, detalle=mensaje_raw)

    # NOT NULL / valor demasiado largo
    if codigo in (1400, 1407):
        return ReglaError(
            "Falta completar un campo obligatorio.",
            codigo_ora=codigo,
            detalle=mensaje_raw,
        )
    if codigo == 12899:
        return ReglaError(
            "Uno de los textos supera la longitud máxima permitida.",
            codigo_ora=codigo,
            detalle=mensaje_raw,
        )

    # Errores de conexión / autenticación (ORA-* o DPY-*)
    if (
        codigo in _CONNECTION_CODES
        or "DPY-4001" in mensaje_raw
        or "DPY-6005" in mensaje_raw
        or "DPY-6000" in mensaje_raw
    ):
        if codigo == 1017:
            msg = "Usuario o contraseña incorrectos."
        elif codigo in (12514, 12541) or "DPY-6005" in mensaje_raw:
            msg = "No se pudo conectar al servidor Oracle. Verificá que el servicio esté iniciado y el DSN sea correcto."
        else:
            msg = re.sub(r"^(?:ORA|DPY)-\d+:\s*", "", primera).strip()
        return ErrorConexion(msg, codigo_ora=codigo, detalle=mensaje_raw)

    return ErrorBaseDatos(
        re.sub(r"^ORA-\d+:\s*", "", primera).strip(),
        codigo_ora=codigo,
        detalle=mensaje_raw,
    )


class ConnectionManager:
    """Administra el pool de conexiones Oracle y los límites de transacción."""

    def __init__(
        self,
        config: OracleConfig,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._config = config
        self._connection_factory = connection_factory
        self._pool: Any = None
        atexit.register(self.cerrar)

    @property
    def config(self) -> OracleConfig:
        return self._config

    def _obtener_pool(self) -> Any:
        if self._pool is None:
            if not self._config.esta_configurado:
                raise ErrorConexion("Faltan usuario, contraseña o DSN para conectar a Oracle.")
            try:
                self._pool = oracledb.create_pool(
                    user=self._config.usuario,
                    password=self._config.clave,
                    dsn=self._config.dsn,
                    min=self._config.pool_min,
                    max=self._config.pool_max,
                    increment=self._config.pool_increment,
                )
            except oracledb.Error as exc:
                raise traducir_error_oracle(exc) from exc
        return self._pool

    def adquirir_conexion(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        try:
            return self._obtener_pool().acquire()
        except oracledb.Error as exc:
            raise traducir_error_oracle(exc) from exc

    def cerrar(self) -> None:
        if self._pool is not None:
            try:
                self._pool.close(force=True)
            except Exception:
                pass
            self._pool = None

    def probar_conexion(self) -> dict[str, Any]:
        """Verifica conectividad ejecutando una consulta mínima sobre DUAL."""
        with self.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                cur.execute(
                    "SELECT USER, SYS_CONTEXT('USERENV', 'CON_NAME'), SYSTIMESTAMP FROM DUAL"
                )
                fila = cur.fetchone()
                return {
                    "usuario": fila[0] if fila else self._config.usuario,
                    "contenedor": fila[1] if fila else "",
                    "fecha_servidor": fila[2] if fila else None,
                    "dsn": self._config.dsn,
                }

    @contextmanager
    def conexion_lectura(self) -> Iterator[Any]:
        """Entrega una conexión para operaciones de solo lectura (sin COMMIT)."""
        cnx = self.adquirir_conexion()
        try:
            cnx.autocommit = False
            yield cnx
        except AppError:
            raise
        except oracledb.Error as exc:
            raise traducir_error_oracle(exc) from exc
        finally:
            try:
                cnx.close()
            except Exception:
                pass

    @contextmanager
    def transaccion(self) -> Iterator[Any]:
        """Demarca una transacción ACID: entrega cursor; COMMIT al éxito, ROLLBACK ante error."""
        cnx = self.adquirir_conexion()
        cnx.autocommit = False
        cur = cnx.cursor()
        try:
            yield cur
            cnx.commit()
        except AppError:
            try:
                cnx.rollback()
            except Exception:
                pass
            raise
        except oracledb.Error as exc:
            try:
                cnx.rollback()
            except Exception:
                pass
            raise traducir_error_oracle(exc) from exc
        except Exception:
            try:
                cnx.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                cnx.close()
            except Exception:
                pass

    def consultar(self, sql: str, **params: Any) -> list[tuple[Any, ...]]:
        """Ejecuta una consulta SELECT parametrizada y retorna todas las filas."""
        with self.conexion_lectura() as cnx:
            with cnx.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
