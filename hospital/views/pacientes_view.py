"""Vista CRUD completo de Pacientes (Alta, Listado con búsqueda, Editar y Eliminar)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

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


class PacientesView(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        controllers: AppControllers,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._ctrl = controllers
        self._on_change = on_change
        self._dni_en_edicion: str | None = None
        self._construir_ui()

    def _construir_ui(self) -> None:
        self.form = ttk.LabelFrame(self, text="Alta de paciente")
        self.form.pack(fill="x", padx=10, pady=8)

        self.p_dni = campo(self.form, 0, "DNI:", 16)
        self.p_nombre = campo(self.form, 1, "Nombre:", 30)
        self.p_apellido = campo(self.form, 2, "Apellido:", 30)
        self.p_nac = campo(self.form, 3, "Fecha nacimiento (AAAA-MM-DD):", 16)
        self.p_sexo = combo(self.form, 4, "Sexo:", 6)
        cargar_combo(self.p_sexo, [("F", "F"), ("M", "M"), ("X", "X")])

        botones = ttk.Frame(self.form)
        botones.grid(row=5, column=0, columnspan=2, pady=8)
        self.btn_guardar = ttk.Button(botones, text="Guardar paciente", command=self.guardar)
        self.btn_guardar.pack(side="left", padx=4)
        self.btn_cancelar = ttk.Button(
            botones, text="Cancelar edición", command=self.cancelar_edicion, state="disabled"
        )
        self.btn_cancelar.pack(side="left", padx=4)

        # Barra de búsqueda y acciones sobre la fila seleccionada
        barra = ttk.Frame(self)
        barra.pack(fill="x", padx=10, pady=(2, 4))
        ttk.Label(barra, text="Buscar:").pack(side="left", padx=(0, 4))
        self.e_buscar = ttk.Entry(barra, width=28)
        self.e_buscar.pack(side="left", padx=(0, 8))
        self.e_buscar.bind("<KeyRelease>", lambda _e: ejecutar(self.refrescar))

        ttk.Button(barra, text="Eliminar seleccionado", command=self.eliminar).pack(
            side="right", padx=4
        )
        ttk.Button(barra, text="Editar seleccionado", command=self.cargar_para_editar).pack(
            side="right", padx=4
        )

        self.t_pacientes = TablaPaginada(
            self,
            ("dni", "apellido", "nombre", "fecha_nac", "sexo"),
            ancho=180,
            titulos={
                "dni": "DNI",
                "apellido": "Apellido",
                "nombre": "Nombre",
                "fecha_nac": "Fecha nacimiento",
                "sexo": "Sexo",
            },
            altura=11,
        )
        self.t_pacientes.pack(expand=True, fill="both", padx=10, pady=(0, 8))

    def refrescar(self) -> None:
        filtro = self.e_buscar.get().strip() or None
        pacientes = self._ctrl.pacientes.listar(filtro=filtro)
        self.t_pacientes.cargar(
            [
                (p.dni, p.apellido, p.nombre, p.fecha_nacimiento, p.sexo)
                for p in pacientes
            ]
        )

    def _limpiar_form(self) -> None:
        self._dni_en_edicion = None
        self.form.config(text="Alta de paciente")
        self.btn_guardar.config(text="Guardar paciente")
        self.btn_cancelar.config(state="disabled")
        self.p_dni.config(state="normal")
        for e in (self.p_dni, self.p_nombre, self.p_apellido, self.p_nac):
            e.delete(0, "end")
        self.p_sexo.set("")

    def cancelar_edicion(self) -> None:
        self._limpiar_form()

    def cargar_para_editar(self) -> None:
        def accion() -> None:
            fila = self.t_pacientes.fila_seleccionada("Seleccioná un paciente de la lista.")
            dni, apellido, nombre, fecha_nac, sexo = [str(x) for x in fila]
            self._dni_en_edicion = dni
            self.form.config(text=f"Editando paciente (DNI {dni})")
            self.btn_guardar.config(text="Guardar cambios")
            self.btn_cancelar.config(state="normal")

            self.p_dni.config(state="normal")
            self.p_dni.delete(0, "end")
            self.p_dni.insert(0, dni)
            self.p_dni.config(state="disabled")

            self.p_nombre.delete(0, "end")
            self.p_nombre.insert(0, nombre)
            self.p_apellido.delete(0, "end")
            self.p_apellido.insert(0, apellido)
            self.p_nac.delete(0, "end")
            self.p_nac.insert(0, fecha_nac)
            self.p_sexo.set(sexo)

        ejecutar(accion)

    def guardar(self) -> None:
        if self._dni_en_edicion is not None:
            dni_edit = self._dni_en_edicion

            def accion_edit() -> None:
                self._ctrl.pacientes.editar(
                    dni_edit,
                    self.p_nombre.get(),
                    self.p_apellido.get(),
                    parsear_fecha(self.p_nac.get(), "Fecha de nacimiento"),
                    valor_combo(self.p_sexo, "Sexo"),
                )

            if ejecutar(accion_edit, "Paciente actualizado.", self._on_change):
                self._limpiar_form()
            return

        def accion_alta() -> None:
            self._ctrl.pacientes.alta(
                self.p_dni.get().strip(),
                self.p_nombre.get(),
                self.p_apellido.get(),
                parsear_fecha(self.p_nac.get(), "Fecha de nacimiento"),
                valor_combo(self.p_sexo, "Sexo"),
            )

        if ejecutar(accion_alta, "Paciente guardado.", self._on_change):
            self._limpiar_form()

    def eliminar(self) -> None:
        def accion() -> bool:
            fila = self.t_pacientes.fila_seleccionada("Seleccioná un paciente de la lista.")
            dni = str(fila[0])
            nombre = f"{fila[1]}, {fila[2]}"
            if not messagebox.askyesno(
                "Confirmar baja",
                f"¿Eliminar al paciente {nombre} (DNI {dni})?",
            ):
                return False
            self._ctrl.pacientes.eliminar(dni)
            return True

        res = ejecutar(accion)
        if res:
            messagebox.showinfo("Listo", "Paciente eliminado.")
            if self._dni_en_edicion is not None:
                self._limpiar_form()
            self._on_change()
