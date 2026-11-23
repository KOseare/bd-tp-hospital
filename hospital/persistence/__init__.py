"""Capa de Persistencia: gestión de conexiones Oracle y DAOs por entidad."""

from hospital.persistence import (
    auditoria_dao,
    cama_dao,
    guardia_dao,
    internacion_dao,
    medico_dao,
    paciente_dao,
    persona_dao,
    pruebas_dao,
    reportes_dao,
    ronda_dao,
)
from hospital.persistence.connection import ConnectionManager, traducir_error_oracle

__all__ = [
    "ConnectionManager",
    "auditoria_dao",
    "cama_dao",
    "guardia_dao",
    "internacion_dao",
    "medico_dao",
    "paciente_dao",
    "persona_dao",
    "pruebas_dao",
    "reportes_dao",
    "ronda_dao",
    "traducir_error_oracle",
]
