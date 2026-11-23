"""Contenedor que instancia y agrupa todos los controladores sobre un ConnectionManager."""

from __future__ import annotations

from dataclasses import dataclass

from hospital.config import OracleConfig
from hospital.controllers.guardia_controller import GuardiaController
from hospital.controllers.internacion_controller import InternacionController
from hospital.controllers.medico_controller import MedicoController
from hospital.controllers.paciente_controller import PacienteController
from hospital.controllers.pruebas_controller import PruebasController
from hospital.controllers.reportes_controller import ReportesController
from hospital.controllers.ronda_controller import RondaController
from hospital.persistence.connection import ConnectionManager


@dataclass
class AppControllers:
    db: ConnectionManager
    pacientes: PacienteController
    medicos: MedicoController
    internaciones: InternacionController
    rondas: RondaController
    guardias: GuardiaController
    reportes: ReportesController
    pruebas: PruebasController

    @classmethod
    def desde_connection_manager(cls, db: ConnectionManager) -> AppControllers:
        pacientes = PacienteController(db)
        medicos = MedicoController(db)
        internaciones = InternacionController(db)
        rondas = RondaController(db)
        guardias = GuardiaController(db)
        reportes = ReportesController(db)
        pruebas = PruebasController(
            db,
            internaciones,
            guardias,
            reportes,
            rondas,
            pacientes,
            medicos,
        )
        return cls(
            db=db,
            pacientes=pacientes,
            medicos=medicos,
            internaciones=internaciones,
            rondas=rondas,
            guardias=guardias,
            reportes=reportes,
            pruebas=pruebas,
        )

    @classmethod
    def desde_config(cls, config: OracleConfig) -> AppControllers:
        return cls.desde_connection_manager(ConnectionManager(config))
