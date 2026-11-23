"""Capa de Vistas Tkinter (modularizada por pestaña, sin SQL directo)."""

from hospital.views.auditoria_view import AuditoriaView
from hospital.views.camas_view import CamasView
from hospital.views.comentarios_view import ComentariosView
from hospital.views.guardias_view import GuardiasView
from hospital.views.internaciones_view import InternacionesView
from hospital.views.main_window import MainWindow
from hospital.views.medicos_view import MedicosView
from hospital.views.pacientes_view import PacientesView
from hospital.views.pruebas_view import PruebasView
from hospital.views.rondas_view import RondasView
from hospital.views.widgets import TablaPaginada, pedir_credenciales

__all__ = [
    "AuditoriaView",
    "CamasView",
    "ComentariosView",
    "GuardiasView",
    "InternacionesView",
    "MainWindow",
    "MedicosView",
    "PacientesView",
    "PruebasView",
    "RondasView",
    "TablaPaginada",
    "pedir_credenciales",
]
