"""Vista de Camas: resumen/detalle desde PR_CAMAS_DISPONIBLES y consulta de todas las camas."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hospital.controllers.container import AppControllers
from hospital.views.widgets import TablaPaginada, ejecutar


class CamasView(ttk.Frame):
    def __init__(self, parent: tk.Widget, controllers: AppControllers) -> None:
        super().__init__(parent)
        self._ctrl = controllers
        self._construir_ui()

    def _construir_ui(self) -> None:
        sub = ttk.Notebook(self)
        sub.pack(expand=True, fill="both", padx=6, pady=6)

        # Sub-tab 1: Resumen por sector (PR_CAMAS_DISPONIBLES)
        f1 = ttk.Frame(sub)
        sub.add(f1, text="Resumen por sector")
        self.t_resumen = TablaPaginada(
            f1,
            ("sector", "camas_disponibles"),
            ancho=260,
            titulos={"sector": "Sector", "camas_disponibles": "Camas disponibles"},
            altura=12,
        )
        self.t_resumen.pack(expand=True, fill="both", padx=6, pady=6)

        # Sub-tab 2: Detalle de disponibles (PR_CAMAS_DISPONIBLES)
        f2 = ttk.Frame(sub)
        sub.add(f2, text="Detalle disponibles")
        self.t_detalle = TablaPaginada(
            f2,
            ("sector", "habitacion", "piso", "orientacion", "cama"),
            ancho=150,
            titulos={
                "sector": "Sector",
                "habitacion": "Habitación",
                "piso": "Piso",
                "orientacion": "Orientación",
                "cama": "Cama",
            },
            altura=12,
        )
        self.t_detalle.pack(expand=True, fill="both", padx=6, pady=6)

        # Sub-tab 3: Todas las camas (estado Libre / Ocupada derivado de OCUPA)
        f3 = ttk.Frame(sub)
        sub.add(f3, text="Todas las camas")

        filtros = ttk.Frame(f3)
        filtros.pack(fill="x", padx=6, pady=6)

        ttk.Label(filtros, text="Sector:").pack(side="left", padx=(0, 4))
        self.cb_sector = ttk.Combobox(filtros, width=22, state="readonly")
        self.cb_sector.pack(side="left", padx=(0, 12))
        self.cb_sector.bind("<<ComboboxSelected>>", lambda _e: ejecutar(self.refrescar_todas))

        ttk.Label(filtros, text="Estado:").pack(side="left", padx=(0, 4))
        self.cb_estado = ttk.Combobox(
            filtros,
            values=["Todas", "Libres", "Ocupadas"],
            width=12,
            state="readonly",
        )
        self.cb_estado.set("Todas")
        self.cb_estado.pack(side="left")
        self.cb_estado.bind("<<ComboboxSelected>>", lambda _e: ejecutar(self.refrescar_todas))

        self.t_todas = TablaPaginada(
            f3,
            ("estado", "sector", "habitacion", "piso", "orientacion", "cama", "internacion", "paciente", "desde"),
            anchos_columna={
                "estado": 80,
                "sector": 140,
                "habitacion": 85,
                "piso": 55,
                "orientacion": 90,
                "cama": 60,
                "internacion": 85,
                "paciente": 180,
                "desde": 130,
            },
            titulos={
                "estado": "Estado",
                "sector": "Sector",
                "habitacion": "Habitación",
                "piso": "Piso",
                "orientacion": "Orientación",
                "cama": "Cama",
                "internacion": "Int. ID",
                "paciente": "Paciente actual",
                "desde": "Desde",
            },
            altura=12,
        )
        self.t_todas.pack(expand=True, fill="both", padx=6, pady=(0, 6))

    def refrescar(self) -> None:
        resumen, detalle = self._ctrl.reportes.camas_disponibles()
        self.t_resumen.cargar([(r.nombre_sector, r.camas_disponibles) for r in resumen])
        self.t_detalle.cargar(
            [
                (d.nombre_sector, d.nro_habitacion, d.piso, d.orientacion, d.nro_cama)
                for d in detalle
            ]
        )

        sectores = ["Todos"] + self._ctrl.reportes.listar_sectores()
        sel_actual = self.cb_sector.get()
        self.cb_sector["values"] = sectores
        if sel_actual not in sectores:
            self.cb_sector.set("Todos")

        self.refrescar_todas()

    def refrescar_todas(self) -> None:
        sector_val = self.cb_sector.get()
        sector = None if not sector_val or sector_val == "Todos" else sector_val
        estado_val = self.cb_estado.get()
        solo_disp = {"Todas": None, "Libres": True, "Ocupadas": False}.get(estado_val, None)

        camas = self._ctrl.reportes.listar_todas_las_camas(
            nombre_sector=sector,
            solo_disponibles=solo_disp,
        )
        self.t_todas.cargar(
            [
                (
                    "Ocupada" if c.ocupada else "Libre",
                    c.nombre_sector,
                    c.nro_habitacion,
                    c.piso,
                    c.orientacion,
                    c.nro_cama,
                    c.id_internacion_activa or "-",
                    c.nombre_paciente or "-",
                    c.fecha_asignacion or "-",
                )
                for c in camas
            ]
        )
