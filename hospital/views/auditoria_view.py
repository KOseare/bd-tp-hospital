"""Vista de consulta de Auditoría de guardias (`AUDITORIA_GUARDIAS`)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hospital.controllers.container import AppControllers
from hospital.views.widgets import TablaPaginada, ejecutar

_TABLAS_AUD = ["Todas", "DESEMPENA", "GUARDIA", "MEDICO", "POSEE", "VACACION"]


class AuditoriaView(ttk.Frame):
    def __init__(self, parent: tk.Widget, controllers: AppControllers) -> None:
        super().__init__(parent)
        self._ctrl = controllers
        self._construir_ui()

    def _construir_ui(self) -> None:
        filtros = ttk.Frame(self)
        filtros.pack(fill="x", padx=10, pady=8)

        ttk.Label(filtros, text="Tabla:").pack(side="left", padx=(0, 4))
        self.cb_tabla = ttk.Combobox(
            filtros,
            values=_TABLAS_AUD,
            width=16,
            state="readonly",
        )
        self.cb_tabla.set("Todas")
        self.cb_tabla.pack(side="left")
        self.cb_tabla.bind("<<ComboboxSelected>>", lambda _e: ejecutar(self.refrescar))

        self.t_audit = TablaPaginada(
            self,
            ("id", "fecha_hora", "usuario_bd", "usuario_so", "tabla", "operacion", "clave", "detalle"),
            anchos_columna={
                "id": 55,
                "fecha_hora": 140,
                "usuario_bd": 100,
                "usuario_so": 105,
                "tabla": 95,
                "operacion": 80,
                "clave": 210,
                "detalle": 310,
            },
            titulos={
                "id": "ID",
                "fecha_hora": "Fecha y hora",
                "usuario_bd": "Usuario BD",
                "usuario_so": "Usuario SO",
                "tabla": "Tabla",
                "operacion": "Operación",
                "clave": "Clave",
                "detalle": "Detalle",
            },
            altura=15,
            page_size=25,
        )
        self.t_audit.pack(expand=True, fill="both", padx=10, pady=(0, 8))

    def refrescar(self) -> None:
        sel = self.cb_tabla.get()
        tabla = None if not sel or sel == "Todas" else sel
        eventos = self._ctrl.guardias.listar_auditoria(tabla_afectada=tabla)
        self.t_audit.cargar(
            [
                (
                    e.id_auditoria,
                    e.fecha_hora.strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(e.fecha_hora, "strftime")
                    else e.fecha_hora,
                    e.usuario_bd,
                    e.usuario_so or "-",
                    e.tabla_afectada,
                    e.operacion,
                    e.clave_registro,
                    e.detalle_cambio or "-",
                )
                for e in eventos
            ]
        )
