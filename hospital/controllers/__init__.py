"""Capa de Controladores: lógica de negocio, validaciones y coordinación transaccional."""

from hospital.controllers.container import AppControllers
from hospital.controllers.guardia_controller import GuardiaController, calcular_intervalo
from hospital.controllers.internacion_controller import InternacionController
from hospital.controllers.medico_controller import MedicoController
from hospital.controllers.paciente_controller import PacienteController
from hospital.controllers.pruebas_controller import PruebasController
from hospital.controllers.reportes_controller import ReportesController
from hospital.controllers.ronda_controller import RondaController

__all__ = [
    "AppControllers",
    "GuardiaController",
    "InternacionController",
    "MedicoController",
    "PacienteController",
    "PruebasController",
    "ReportesController",
    "RondaController",
    "calcular_intervalo",
]
