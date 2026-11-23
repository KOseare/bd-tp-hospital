"""Vista de Internaciones: alta, cambio de cama, alta médica e historial de camas (OCUPA)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from hospital.controllers.container import AppControllers
from hospital.views.widgets import (
    TablaPaginada,
    cargar_combo,
    combo,
    ejecutar,
    valor_combo,
)


class InternacionesView(ttk.Frame):
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
        form = ttk.LabelFrame(self, text="Nueva internación / cambio de cama")
        form.pack(fill="x", padx=10, pady=8)

        self.cb_paciente = combo(form, 0, "Paciente:", ancho=46)
        self.cb_medico_ppal = combo(form, 1, "Médico principal:", ancho=46)
        self.cb_cama = combo(form, 2, "Cama libre:", ancho=46)

        botones = ttk.Frame(form)
        botones.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(botones, text="Internar paciente", command=self.internar).pack(
            side="left", padx=6
        )
        ttk.Button(
            botones,
            text="Cambiar cama de la internación seleccionada",
            command=self.cambiar_cama,
        ).pack(side="left", padx=6)
        ttk.Button(
            botones,
            text="Dar de alta la seleccionada",
            command=self.dar_alta,
        ).pack(side="left", padx=6)

        # Filtros
        filtros = ttk.Frame(self)
        filtros.pack(fill="x", padx=10, pady=(2, 4))
        self.var_ver_todas = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filtros,
            text="Incluir finalizadas",
            variable=self.var_ver_todas,
            command=lambda: ejecutar(self.refrescar_listado),
        ).pack(side="left", padx=(0, 12))

        ttk.Label(filtros, text="Filtrar por DNI:").pack(side="left", padx=(0, 4))
        self.e_dni_filtro = ttk.Entry(filtros, width=16)
        self.e_dni_filtro.pack(side="left")
        self.e_dni_filtro.bind("<KeyRelease>", lambda _e: ejecutar(self.refrescar_listado))

        # Tabla principal de internaciones
        self.t_int = TablaPaginada(
            self,
            ("id_internacion", "estado", "dni", "paciente", "medico", "habitacion", "cama", "desde", "hasta"),
            anchos_columna={
                "id_internacion": 60,
                "estado": 80,
                "dni": 90,
                "paciente": 160,
                "medico": 160,
                "habitacion": 80,
                "cama": 55,
                "desde": 125,
                "hasta": 125,
            },
            titulos={
                "id_internacion": "ID",
                "estado": "Estado",
                "dni": "DNI",
                "paciente": "Paciente",
                "medico": "Médico principal",
                "habitacion": "Habitación",
                "cama": "Cama",
                "desde": "Inicio",
                "hasta": "Alta",
            },
            altura=7,
            page_size=10,
        )
        self.t_int.pack(expand=True, fill="both", padx=10, pady=(0, 6))
        self.t_int.tree.bind("<<TreeviewSelect>>", self._al_seleccionar_internacion)

        # Historial de camas (OCUPA) de la internación seleccionada
        marco_hist = ttk.LabelFrame(self, text="Historial de camas de la internación seleccionada")
        marco_hist.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.t_ocupa = TablaPaginada(
            marco_hist,
            ("estado", "sector", "habitacion", "piso", "orientacion", "cama", "desde", "hasta"),
            anchos_columna={
                "estado": 75,
                "sector": 140,
                "habitacion": 85,
                "piso": 50,
                "orientacion": 90,
                "cama": 55,
                "desde": 135,
                "hasta": 135,
            },
            titulos={
                "estado": "Estado",
                "sector": "Sector",
                "habitacion": "Habitación",
                "piso": "Piso",
                "orientacion": "Orientación",
                "cama": "Cama",
                "desde": "Desde",
                "hasta": "Hasta",
            },
            altura=4,
            page_size=10,
        )
        self.t_ocupa.pack(expand=True, fill="both", padx=6, pady=4)

    def refrescar(self) -> None:
        pacientes = self._ctrl.pacientes.listar()
        medicos = self._ctrl.medicos.listar()
        camas = self._ctrl.reportes.listar_camas_libres()

        cargar_combo(
            self.cb_paciente,
            [(f"{p.dni} - {p.nombre_completo}", p.dni) for p in pacientes],
        )
        cargar_combo(
            self.cb_medico_ppal,
            [(f"{m.matricula} - {m.nombre_completo}", m.matricula) for m in medicos],
        )
        cargar_combo(
            self.cb_cama,
            [(f"Hab {h} / Cama {c} - {s}", (h, c)) for h, c, s in camas],
        )
        self.refrescar_listado()

    def refrescar_listado(self) -> None:
        solo_activas = not self.var_ver_todas.get()
        dni = self.e_dni_filtro.get().strip() or None
        internaciones = self._ctrl.internaciones.listar(
            solo_activas=solo_activas,
            dni_paciente=dni,
        )
        self.t_int.cargar(
            [
                (
                    it.id_internacion,
                    "Activa" if it.esta_activa else "Finalizada",
                    it.dni,
                    it.paciente,
                    f"{it.medico} ({it.matricula_medico})",
                    it.nro_habitacion if it.nro_habitacion is not None else "-",
                    it.nro_cama if it.nro_cama is not None else "-",
                    it.fecha_inicio,
                    it.fecha_terminacion or "-",
                )
                for it in internaciones
            ]
        )
        self.t_ocupa.cargar([])

    def _al_seleccionar_internacion(self, _event: object = None) -> None:
        sel = self.t_int.tree.selection()
        if not sel:
            self.t_ocupa.cargar([])
            return
        valores = self.t_int.tree.item(sel[0])["values"]
        if not valores:
            return
        id_int = int(valores[0])

        def accion() -> None:
            ocups = self._ctrl.internaciones.listar_ocupaciones(id_int)
            self.t_ocupa.cargar(
                [
                    (
                        "Actual" if o.fecha_terminacion is None else "Liberada",
                        o.nombre_sector,
                        o.nro_habitacion,
                        o.piso,
                        o.orientacion,
                        o.nro_cama,
                        o.fecha_asignacion,
                        o.fecha_terminacion or "-",
                    )
                    for o in ocups
                ],
                reset_pagina=True,
            )

        ejecutar(accion)

    def internar(self) -> None:
        def accion() -> None:
            hab, cama = valor_combo(self.cb_cama, "Cama libre")
            id_int = self._ctrl.internaciones.internar(
                valor_combo(self.cb_paciente, "Paciente"),
                valor_combo(self.cb_medico_ppal, "Médico principal"),
                hab,
                cama,
            )
            messagebox.showinfo("Listo", f"Internación #{id_int} creada.")

        ejecutar(accion, despues=self._on_change)

    def cambiar_cama(self) -> None:
        def accion() -> None:
            fila = self.t_int.fila_seleccionada("Seleccioná una internación de la lista.")
            hab, cama = valor_combo(self.cb_cama, "Cama libre")
            self._ctrl.internaciones.cambiar_cama(int(fila[0]), hab, cama)

        ejecutar(accion, "Cama cambiada.", self._on_change)

    def dar_alta(self) -> None:
        def accion() -> bool:
            fila = self.t_int.fila_seleccionada("Seleccioná una internación de la lista.")
            if not messagebox.askyesno("Confirmar", f"¿Dar de alta la internación #{fila[0]}?"):
                return False
            self._ctrl.internaciones.dar_alta(int(fila[0]))
            return True

        if ejecutar(accion):
            messagebox.showinfo("Listo", "Alta registrada.")
            self._on_change()
