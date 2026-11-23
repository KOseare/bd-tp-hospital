"""Vista de Guardias médicas y consulta de vacaciones."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from hospital.config import TURNOS_GUARDIA
from hospital.controllers.container import AppControllers
from hospital.views.widgets import (
    TablaPaginada,
    campo,
    cargar_combo,
    combo,
    ejecutar,
    parsear_fecha,
    valor_combo,
)


class GuardiasView(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        controllers: AppControllers,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._ctrl = controllers
        self._on_change = on_change
        self._construir_ui()

    def _construir_ui(self) -> None:
        form = ttk.LabelFrame(self, text="Asignar guardia")
        form.pack(fill="x", padx=10, pady=8)

        self.cb_medico_g = combo(form, 0, "Médico:", ancho=45)
        self.cb_medico_g.bind("<<ComboboxSelected>>", lambda _e: self.cargar_esp_guardia())
        self.cb_esp_g = combo(form, 1, "Especialidad (hace guardia):", ancho=45)
        self.g_fecha = campo(form, 2, "Día (AAAA-MM-DD):", 15)

        ttk.Label(form, text="Turnos:").grid(row=3, column=0, sticky="e", padx=6)
        marcos = ttk.Frame(form)
        marcos.grid(row=3, column=1, sticky="w")
        self.var_turnos: dict[int, tk.BooleanVar] = {}
        for t, (nombre, hora) in TURNOS_GUARDIA.items():
            self.var_turnos[t] = tk.BooleanVar()
            ttk.Checkbutton(
                marcos,
                text=f"{nombre} ({hora:02d}:00)",
                variable=self.var_turnos[t],
            ).pack(side="left", padx=6)

        ttk.Button(form, text="Asignar guardia", command=self.asignar_guardia).grid(
            row=4, column=0, columnspan=2, pady=8
        )

        self.t_guardias = TablaPaginada(
            self,
            ("id_guardia", "matricula", "medico", "especialidad", "turnos", "inicio", "fin"),
            anchos_columna={
                "id_guardia": 75,
                "matricula": 80,
                "medico": 170,
                "especialidad": 160,
                "turnos": 140,
                "inicio": 135,
                "fin": 135,
            },
            titulos={
                "id_guardia": "ID Guardia",
                "matricula": "Matrícula",
                "medico": "Médico",
                "especialidad": "Especialidad",
                "turnos": "Turnos",
                "inicio": "Inicio",
                "fin": "Fin",
            },
            altura=11,
        )
        self.t_guardias.pack(expand=True, fill="both", padx=10, pady=(0, 8))

    def refrescar(self) -> None:
        medicos = self._ctrl.medicos.listar()
        cargar_combo(
            self.cb_medico_g,
            [(f"{m.matricula} - {m.nombre_completo}", m.matricula) for m in medicos],
        )

        # Bug fix: sincronizar cb_esp_g según el médico actualmente seleccionado
        mapa = getattr(self.cb_medico_g, "mapa", {})
        mat_sel = mapa.get(self.cb_medico_g.get())
        if mat_sel is not None:
            esps = self._ctrl.medicos.especialidades_de_guardia(mat_sel)
            cargar_combo(self.cb_esp_g, [(e, e) for e in esps])
        else:
            cargar_combo(self.cb_esp_g, [])

        guardias = self._ctrl.guardias.listar()
        self.t_guardias.cargar(
            [
                (
                    g.id_guardia,
                    g.matricula_medico,
                    g.medico,
                    g.nombre_especialidad,
                    ", ".join(g.turnos) if g.turnos else "-",
                    g.fecha_inicio,
                    g.fecha_fin,
                )
                for g in guardias
            ]
        )

    def cargar_esp_guardia(self) -> None:
        def accion() -> None:
            mat = valor_combo(self.cb_medico_g, "Médico")
            esps = self._ctrl.medicos.especialidades_de_guardia(mat)
            cargar_combo(self.cb_esp_g, [(e, e) for e in esps])

        ejecutar(accion)

    def asignar_guardia(self) -> None:
        def accion() -> None:
            self._ctrl.guardias.alta_guardia(
                valor_combo(self.cb_medico_g, "Médico"),
                valor_combo(self.cb_esp_g, "Especialidad"),
                parsear_fecha(self.g_fecha.get(), "Día"),
                [t for t, v in self.var_turnos.items() if v.get()],
            )

        ejecutar(accion, "Guardia asignada.", self._on_change)
