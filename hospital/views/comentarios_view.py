"""Vista de consulta de Comentarios de visitas médicas (`pr_comentarios_internacion`)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from hospital.controllers.container import AppControllers
from hospital.views.widgets import (
    TablaPaginada,
    campo,
    cargar_combo,
    combo,
    ejecutar,
    parsear_entero,
)


class ComentariosView(ttk.Frame):
    def __init__(self, parent: tk.Widget, controllers: AppControllers) -> None:
        super().__init__(parent)
        self._ctrl = controllers
        self._construir_ui()

    def _construir_ui(self) -> None:
        form = ttk.LabelFrame(self, text="Buscar comentarios por internación")
        form.pack(fill="x", padx=10, pady=8)

        self.cb_int = combo(form, 0, "Internación (opcional):", ancho=52)
        self.cb_int.bind("<<ComboboxSelected>>", self._al_elegir_internacion)

        self.e_com_int = campo(form, 1, "ID de internación:", 15)
        self.e_com_dni = campo(form, 2, "DNI del paciente:", 15)
        ttk.Button(form, text="Buscar comentarios", command=self.buscar).grid(
            row=3, column=0, columnspan=2, pady=8
        )

        self.t_coment = TablaPaginada(
            self,
            ("fecha_recorrido", "turno", "apellido", "nombre", "comentario"),
            anchos_columna={
                "fecha_recorrido": 140,
                "turno": 70,
                "apellido": 130,
                "nombre": 130,
                "comentario": 480,
            },
            titulos={
                "fecha_recorrido": "Fecha recorrido",
                "turno": "Turno",
                "apellido": "Apellido médico",
                "nombre": "Nombre médico",
                "comentario": "Comentario",
            },
            altura=13,
        )
        self.t_coment.pack(expand=True, fill="both", padx=10, pady=(0, 8))

    def refrescar(self) -> None:
        internaciones = self._ctrl.internaciones.listar(solo_activas=False)
        items = [
            (
                f"#{it.id_internacion} - {it.paciente} (DNI {it.dni}) - "
                f"{'Activa' if it.esta_activa else 'Finalizada'}",
                (it.id_internacion, it.dni),
            )
            for it in internaciones
        ]
        cargar_combo(self.cb_int, items)

    def _al_elegir_internacion(self, _event: object = None) -> None:
        mapa = getattr(self.cb_int, "mapa", {})
        sel = mapa.get(self.cb_int.get())
        if sel:
            id_int, dni = sel
            self.e_com_int.delete(0, "end")
            self.e_com_int.insert(0, str(id_int))
            self.e_com_dni.delete(0, "end")
            self.e_com_dni.insert(0, str(dni))

    def buscar(self) -> None:
        def accion() -> None:
            id_int = parsear_entero(self.e_com_int.get(), "ID de internación")
            dni = self.e_com_dni.get().strip()
            filas = self._ctrl.reportes.comentarios_internacion(id_int, dni)
            self.t_coment.cargar(
                [
                    (c.fecha_recorrido, c.turno_ronda, c.apellido_medico, c.nombre_medico, c.texto_comentario)
                    for c in filas
                ],
                reset_pagina=True,
            )
            if not filas:
                messagebox.showinfo(
                    "Sin resultados",
                    "No hay comentarios (o la internación no corresponde a ese paciente).",
                )

        ejecutar(accion)
