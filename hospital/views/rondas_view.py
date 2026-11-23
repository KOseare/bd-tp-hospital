"""Vista de Rondas, Recorridos médicos y registro de Comentarios de visitas."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from hospital.controllers.container import AppControllers
from hospital.views.widgets import (
    TablaPaginada,
    campo,
    cargar_combo,
    combo,
    ejecutar,
    parsear_fecha_hora,
    valor_combo,
)


class RondasView(ttk.Frame):
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
        sub = ttk.Notebook(self)
        sub.pack(expand=True, fill="both", padx=6, pady=6)

        # ---- Sub-tab 1: Rondas y registro de Recorridos ----
        tab_rec = ttk.Frame(sub)
        sub.add(tab_rec, text="Rondas y recorridos")

        marco_rondas = ttk.LabelFrame(tab_rec, text="Rondas configuradas")
        marco_rondas.pack(fill="x", padx=8, pady=(6, 4))
        self.t_rondas = TablaPaginada(
            marco_rondas,
            ("id_ronda", "dia", "turno", "habitaciones"),
            anchos_columna={
                "id_ronda": 70,
                "dia": 120,
                "turno": 70,
                "habitaciones": 520,
            },
            titulos={
                "id_ronda": "ID Ronda",
                "dia": "Día",
                "turno": "Turno",
                "habitaciones": "Habitaciones visitadas",
            },
            altura=4,
            page_size=10,
        )
        self.t_rondas.pack(fill="x", padx=6, pady=4)

        form_rec = ttk.LabelFrame(tab_rec, text="Registrar recorrido médico")
        form_rec.pack(fill="x", padx=8, pady=4)
        self.cb_ronda = combo(form_rec, 0, "Ronda:", ancho=46)
        self.cb_med_rec = combo(form_rec, 1, "Médico:", ancho=46)
        self.e_fecha_rec = campo(form_rec, 2, "Fecha y hora (AAAA-MM-DD HH:MM):", 22)
        self.e_fecha_rec.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))
        ttk.Button(
            form_rec,
            text="Registrar recorrido",
            command=self.registrar_recorrido,
        ).grid(row=3, column=0, columnspan=2, pady=6)

        marco_lista_rec = ttk.LabelFrame(tab_rec, text="Recorridos registrados")
        marco_lista_rec.pack(expand=True, fill="both", padx=8, pady=(4, 6))
        self.t_recorridos = TablaPaginada(
            marco_lista_rec,
            ("id_recorrido", "ronda", "dia", "turno", "medico", "fecha", "comentarios"),
            anchos_columna={
                "id_recorrido": 75,
                "ronda": 65,
                "dia": 100,
                "turno": 60,
                "medico": 200,
                "fecha": 140,
                "comentarios": 95,
            },
            titulos={
                "id_recorrido": "ID Rec.",
                "ronda": "Ronda",
                "dia": "Día",
                "turno": "Turno",
                "medico": "Médico",
                "fecha": "Fecha y hora",
                "comentarios": "Comentarios",
            },
            altura=6,
            page_size=10,
        )
        self.t_recorridos.pack(expand=True, fill="both", padx=6, pady=4)

        # ---- Sub-tab 2: Comentarios de recorrido ----
        tab_com = ttk.Frame(sub)
        sub.add(tab_com, text="Cargar comentario de recorrido")

        form_com = ttk.LabelFrame(tab_com, text="Nuevo comentario clínico")
        form_com.pack(fill="x", padx=8, pady=8)

        self.cb_recorrido = combo(form_com, 0, "Recorrido:", ancho=58)
        self.cb_recorrido.bind("<<ComboboxSelected>>", lambda _e: ejecutar(self.cargar_comentarios_rec))
        self.cb_int_com = combo(form_com, 1, "Internación:", ancho=58)

        ttk.Label(form_com, text="Comentario:").grid(row=2, column=0, sticky="ne", padx=6, pady=4)
        self.txt_comentario = tk.Text(form_com, width=58, height=4, wrap="word")
        self.txt_comentario.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Button(
            form_com,
            text="Guardar comentario",
            command=self.registrar_comentario,
        ).grid(row=3, column=0, columnspan=2, pady=8)

        marco_com = ttk.LabelFrame(tab_com, text="Comentarios del recorrido seleccionado")
        marco_com.pack(expand=True, fill="both", padx=8, pady=(0, 8))
        self.t_com_rec = TablaPaginada(
            marco_com,
            ("id_comentario", "id_internacion", "dni", "paciente", "texto"),
            anchos_columna={
                "id_comentario": 70,
                "id_internacion": 80,
                "dni": 95,
                "paciente": 160,
                "texto": 480,
            },
            titulos={
                "id_comentario": "ID",
                "id_internacion": "Int. ID",
                "dni": "DNI",
                "paciente": "Paciente",
                "texto": "Comentario",
            },
            altura=9,
            page_size=10,
        )
        self.t_com_rec.pack(expand=True, fill="both", padx=6, pady=4)

    def refrescar(self) -> None:
        rondas = self._ctrl.rondas.listar_rondas()
        medicos = self._ctrl.medicos.listar()
        recorridos = self._ctrl.rondas.listar_recorridos()
        internaciones = self._ctrl.internaciones.listar(solo_activas=False)

        self.t_rondas.cargar(
            [
                (
                    r.id_ronda,
                    r.dia_ronda,
                    r.turno_ronda,
                    ", ".join(str(h) for h in r.habitaciones) or "-",
                )
                for r in rondas
            ]
        )

        cargar_combo(
            self.cb_ronda,
            [
                (
                    f"Ronda #{r.id_ronda} - {r.dia_ronda} Turno {r.turno_ronda} "
                    f"(Habs: {', '.join(str(h) for h in r.habitaciones)})",
                    r.id_ronda,
                )
                for r in rondas
            ],
        )
        cargar_combo(
            self.cb_med_rec,
            [(f"{m.matricula} - {m.nombre_completo}", m.matricula) for m in medicos],
        )

        self.t_recorridos.cargar(
            [
                (
                    rec.id_recorrido,
                    rec.id_ronda,
                    rec.dia_ronda,
                    rec.turno_ronda,
                    f"{rec.medico} ({rec.matricula_medico})",
                    rec.fecha_recorrido,
                    rec.cantidad_comentarios,
                )
                for rec in recorridos
            ]
        )

        cargar_combo(
            self.cb_recorrido,
            [
                (
                    f"Rec. #{rec.id_recorrido} | Ronda #{rec.id_ronda} ({rec.dia_ronda} T{rec.turno_ronda}) | "
                    f"{rec.fecha_recorrido.strftime('%Y-%m-%d %H:%M')} | {rec.medico}",
                    rec.id_recorrido,
                )
                for rec in recorridos
            ],
        )
        cargar_combo(
            self.cb_int_com,
            [
                (
                    f"Int. #{it.id_internacion} - {it.paciente} (DNI {it.dni}) - "
                    f"{'Activa' if it.esta_activa else 'Finalizada'}",
                    it.id_internacion,
                )
                for it in internaciones
            ],
        )

        if self.cb_recorrido.get():
            self.cargar_comentarios_rec()
        else:
            self.t_com_rec.cargar([])

    def cargar_comentarios_rec(self) -> None:
        mapa = getattr(self.cb_recorrido, "mapa", {})
        id_rec = mapa.get(self.cb_recorrido.get())
        if id_rec is None:
            self.t_com_rec.cargar([])
            return
        filas = self._ctrl.rondas.listar_comentarios_de_recorrido(id_rec)
        self.t_com_rec.cargar(filas, reset_pagina=True)

    def registrar_recorrido(self) -> None:
        def accion() -> None:
            id_rec = self._ctrl.rondas.registrar_recorrido(
                valor_combo(self.cb_ronda, "Ronda"),
                valor_combo(self.cb_med_rec, "Médico"),
                parsear_fecha_hora(self.e_fecha_rec.get(), "Fecha y hora"),
            )
            messagebox.showinfo("Listo", f"Recorrido #{id_rec} registrado.")

        ejecutar(accion, despues=self._on_change)

    def registrar_comentario(self) -> None:
        def accion() -> None:
            texto = self.txt_comentario.get("1.0", "end").strip()
            id_com = self._ctrl.rondas.registrar_comentario(
                valor_combo(self.cb_recorrido, "Recorrido"),
                valor_combo(self.cb_int_com, "Internación"),
                texto,
            )
            messagebox.showinfo("Listo", f"Comentario #{id_com} guardado.")

        if ejecutar(accion, despues=self._on_change):
            self.txt_comentario.delete("1.0", "end")
