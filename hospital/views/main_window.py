"""Ventana principal Tkinter que coordina las 9 vistas del sistema hospitalario."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from hospital.controllers.container import AppControllers
from hospital.models.exceptions import AppError
from hospital.views.auditoria_view import AuditoriaView
from hospital.views.camas_view import CamasView
from hospital.views.comentarios_view import ComentariosView
from hospital.views.guardias_view import GuardiasView
from hospital.views.internaciones_view import InternacionesView
from hospital.views.medicos_view import MedicosView
from hospital.views.pacientes_view import PacientesView
from hospital.views.pruebas_view import PruebasView
from hospital.views.rondas_view import RondasView


class MainWindow:
    def __init__(self, root: tk.Tk, controllers: AppControllers) -> None:
        self.root = root
        self.controllers = controllers
        root.title("Hospital - Gestión")
        w, h = 1180, 740
        x = max(0, (root.winfo_screenwidth() - w) // 2)
        y = max(0, (root.winfo_screenheight() - h) // 2 - 20)
        root.geometry(f"{w}x{h}+{x}+{y}")

        self.nb = ttk.Notebook(root)
        self.nb.pack(expand=True, fill="both")

        self.v_camas = CamasView(self.nb, controllers)
        self.v_comentarios = ComentariosView(self.nb, controllers)
        self.v_pacientes = PacientesView(self.nb, controllers, on_change=self.refrescar_todo)
        self.v_medicos = MedicosView(self.nb, controllers, on_change=self.refrescar_todo)
        self.v_internaciones = InternacionesView(
            self.nb, controllers, on_change=self.refrescar_todo
        )
        self.v_rondas = RondasView(self.nb, controllers, on_change=self.refrescar_todo)
        self.v_guardias = GuardiasView(self.nb, controllers, on_change=self.refrescar_todo)
        self.v_auditoria = AuditoriaView(self.nb, controllers)
        self.v_pruebas = PruebasView(self.nb, controllers.pruebas)

        self._vistas_refrescables = [
            (self.v_camas, "Camas"),
            (self.v_comentarios, "Comentarios"),
            (self.v_pacientes, "Pacientes"),
            (self.v_medicos, "Médicos"),
            (self.v_internaciones, "Internaciones"),
            (self.v_rondas, "Rondas"),
            (self.v_guardias, "Guardias"),
            (self.v_auditoria, "Auditoría de guardias"),
        ]

        for vista, titulo in self._vistas_refrescables:
            self.nb.add(vista, text=titulo)
        self.nb.add(self.v_pruebas, text="Batería de pruebas")

        self.nb.bind("<<NotebookTabChanged>>", self._al_cambiar_tab)
        self.refrescar_todo()

    def _al_cambiar_tab(self, _event: object = None) -> None:
        try:
            idx = self.nb.index(self.nb.select())
        except tk.TclError:
            return
        if 0 <= idx < len(self._vistas_refrescables):
            vista = self._vistas_refrescables[idx][0]
            try:
                vista.refrescar()
            except AppError as e:
                messagebox.showerror("Error de conexión", str(e))

    def refrescar_todo(self) -> None:
        try:
            for vista, _ in self._vistas_refrescables:
                vista.refrescar()
        except AppError as e:
            messagebox.showerror("Error de conexión", f"No se pudo leer la base:\n{e}")
