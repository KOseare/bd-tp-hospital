"""Vista de Médicos: alta, edición, consulta de foto BLOB, especialidades y vacaciones."""

from __future__ import annotations

import io
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from PIL import Image, ImageTk

from hospital.controllers.container import AppControllers
from hospital.views.widgets import (
    TablaPaginada,
    campo,
    ejecutar,
    parsear_entero,
    parsear_fecha,
)


class MedicosView(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        controllers: AppControllers,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._ctrl = controllers
        self._on_change = on_change
        self._esp_pendientes: dict[str, bool] = {}
        self._matricula_en_edicion: int | None = None
        self._construir_ui()

    def _construir_ui(self) -> None:
        self.form = ttk.LabelFrame(self, text="Alta de médico")
        self.form.pack(fill="x", padx=10, pady=8)

        self.m_mat = campo(self.form, 0, "Matrícula:", 15)
        self.m_dni = campo(self.form, 1, "DNI:", 15)
        self.m_nombre = campo(self.form, 2, "Nombre:", 28)
        self.m_apellido = campo(self.form, 3, "Apellido:", 28)
        self.m_cuil = campo(self.form, 4, "CUIL/CUIT (11 dígitos):", 15)
        self.m_ingreso = campo(self.form, 5, "Fecha de ingreso (AAAA-MM-DD):", 15)
        self.m_ingreso.insert(0, date.today().isoformat())
        self.m_maxg = campo(self.form, 6, "Máx. guardias por mes:", 8)
        self.m_maxg.insert(0, "0")
        self.m_foto = campo(self.form, 7, "Foto (opcional):", 34)
        ttk.Button(self.form, text="Elegir...", command=self.elegir_foto).grid(
            row=7, column=2, padx=4
        )

        # Panel de especialidades (POSEE)
        esp = ttk.LabelFrame(self.form, text="Especialidades")
        esp.grid(row=0, column=3, rowspan=8, padx=16, sticky="n")
        self.cb_esp = ttk.Combobox(esp, width=24)
        self.cb_esp.grid(row=0, column=0, padx=4, pady=3)
        self.var_hace_guardia = tk.BooleanVar(value=True)
        ttk.Checkbutton(esp, text="Hace guardia", variable=self.var_hace_guardia).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(esp, text="Agregar", command=self.agregar_especialidad).grid(
            row=0, column=2, padx=4
        )

        self.t_esp = ttk.Treeview(esp, columns=("especialidad", "guardia"), show="headings", height=4)
        for c, tit in (("especialidad", "Especialidad"), ("guardia", "Guardia")):
            self.t_esp.heading(c, text=tit, anchor="center")
            self.t_esp.column(c, width=130, anchor="center")
        self.t_esp.grid(row=1, column=0, columnspan=3, padx=4, pady=4)
        ttk.Button(esp, text="Quitar seleccionada", command=self.quitar_especialidad).grid(
            row=2, column=0, columnspan=3, pady=2
        )

        botones = ttk.Frame(self.form)
        botones.grid(row=8, column=0, columnspan=3, pady=8)
        self.btn_guardar = ttk.Button(botones, text="Guardar médico", command=self.guardar)
        self.btn_guardar.pack(side="left", padx=4)
        self.btn_cancelar = ttk.Button(
            botones, text="Cancelar edición", command=self.cancelar_edicion, state="disabled"
        )
        self.btn_cancelar.pack(side="left", padx=4)

        # Barra de búsqueda y acciones
        barra = ttk.Frame(self)
        barra.pack(fill="x", padx=10, pady=(2, 4))
        ttk.Label(barra, text="Buscar:").pack(side="left", padx=(0, 4))
        self.e_buscar = ttk.Entry(barra, width=28)
        self.e_buscar.pack(side="left", padx=(0, 8))
        self.e_buscar.bind("<KeyRelease>", lambda _e: ejecutar(self.refrescar))

        ttk.Button(barra, text="Ver ficha / foto y vacaciones", command=self.ver_ficha).pack(
            side="right", padx=4
        )
        ttk.Button(barra, text="Editar seleccionado", command=self.cargar_para_editar).pack(
            side="right", padx=4
        )

        self.t_medicos = TablaPaginada(
            self,
            ("matricula", "dni", "apellido", "nombre", "cuil_cuit", "max_guardias", "especialidades", "foto"),
            anchos_columna={
                "matricula": 85,
                "dni": 95,
                "apellido": 120,
                "nombre": 120,
                "cuil_cuit": 115,
                "max_guardias": 95,
                "especialidades": 240,
                "foto": 55,
            },
            titulos={
                "matricula": "Matrícula",
                "dni": "DNI",
                "apellido": "Apellido",
                "nombre": "Nombre",
                "cuil_cuit": "CUIL/CUIT",
                "max_guardias": "Máx. guardias",
                "especialidades": "Especialidades",
                "foto": "Foto",
            },
            altura=9,
        )
        self.t_medicos.pack(expand=True, fill="both", padx=10, pady=(0, 8))

    def refrescar(self) -> None:
        self.cb_esp["values"] = self._ctrl.medicos.listar_especialidades()
        filtro = self.e_buscar.get().strip() or None
        medicos = self._ctrl.medicos.listar(filtro=filtro)
        self.t_medicos.cargar(
            [
                (
                    m.matricula,
                    m.dni,
                    m.apellido,
                    m.nombre,
                    m.cuil_cuit,
                    m.cantidad_guardias,
                    ", ".join(
                        f"{e.nombre_especialidad} ({e.hace_guardia_char})"
                        for e in m.especialidades
                    )
                    or "-",
                    "Sí" if m.foto else "No",
                )
                for m in medicos
            ]
        )

    def elegir_foto(self) -> None:
        ruta = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Todos", "*.*")]
        )
        if ruta:
            self.m_foto.delete(0, "end")
            self.m_foto.insert(0, ruta)

    def agregar_especialidad(self) -> None:
        nombre = self.cb_esp.get().strip()
        if not nombre:
            return
        self._esp_pendientes[nombre] = self.var_hace_guardia.get()
        self._mostrar_esp_pendientes()

    def quitar_especialidad(self) -> None:
        sel = self.t_esp.selection()
        if sel:
            self._esp_pendientes.pop(str(self.t_esp.item(sel[0])["values"][0]), None)
            self._mostrar_esp_pendientes()

    def _mostrar_esp_pendientes(self) -> None:
        self.t_esp.delete(*self.t_esp.get_children())
        for nombre, hg in self._esp_pendientes.items():
            self.t_esp.insert("", "end", values=(nombre, "S" if hg else "N"))

    def _limpiar_form(self) -> None:
        self._matricula_en_edicion = None
        self.form.config(text="Alta de médico")
        self.btn_guardar.config(text="Guardar médico")
        self.btn_cancelar.config(state="disabled")
        self.m_mat.config(state="normal")
        self.m_dni.config(state="normal")
        for e in (self.m_mat, self.m_dni, self.m_nombre, self.m_apellido, self.m_cuil, self.m_foto):
            e.delete(0, "end")
        self.m_ingreso.delete(0, "end")
        self.m_ingreso.insert(0, date.today().isoformat())
        self.m_maxg.delete(0, "end")
        self.m_maxg.insert(0, "0")
        self._esp_pendientes.clear()
        self._mostrar_esp_pendientes()

    def cancelar_edicion(self) -> None:
        self._limpiar_form()

    def cargar_para_editar(self) -> None:
        def accion() -> None:
            fila = self.t_medicos.fila_seleccionada("Seleccioná un médico de la lista.")
            mat = int(fila[0])
            med = self._ctrl.medicos.obtener(mat)

            self._matricula_en_edicion = med.matricula
            self.form.config(text=f"Editando médico (Mat. {med.matricula})")
            self.btn_guardar.config(text="Guardar cambios")
            self.btn_cancelar.config(state="normal")

            self.m_mat.config(state="normal")
            self.m_mat.delete(0, "end")
            self.m_mat.insert(0, str(med.matricula))
            self.m_mat.config(state="disabled")

            self.m_dni.config(state="normal")
            self.m_dni.delete(0, "end")
            self.m_dni.insert(0, med.dni)
            self.m_dni.config(state="disabled")

            self.m_nombre.delete(0, "end")
            self.m_nombre.insert(0, med.nombre)
            self.m_apellido.delete(0, "end")
            self.m_apellido.insert(0, med.apellido)
            self.m_cuil.delete(0, "end")
            self.m_cuil.insert(0, med.cuil_cuit)
            self.m_ingreso.delete(0, "end")
            self.m_ingreso.insert(0, med.fecha_ingreso.strftime("%Y-%m-%d"))
            self.m_maxg.delete(0, "end")
            self.m_maxg.insert(0, str(med.cantidad_guardias))
            self.m_foto.delete(0, "end")

            self._esp_pendientes = {
                e.nombre_especialidad: e.hace_guardia for e in med.especialidades
            }
            self._mostrar_esp_pendientes()

        ejecutar(accion)

    def _leer_foto_opcional(self) -> tuple[bytes | None, bool]:
        ruta = self.m_foto.get().strip()
        if not ruta:
            return None, False
        try:
            with open(ruta, "rb") as f:
                return f.read(), True
        except OSError as e:
            raise ValueError(f"No se pudo leer la foto: {e}") from e

    def guardar(self) -> None:
        esp_lista = list(self._esp_pendientes.items())
        nuevas = self._ctrl.medicos.detectar_especialidades_nuevas(esp_lista)
        permitir_nuevas = False
        if nuevas:
            permitir_nuevas = messagebox.askyesno(
                "Confirmar nueva especialidad",
                "Las siguientes especialidades no existen en el catálogo:\n"
                + ", ".join(nuevas)
                + "\n\n¿Querés crearlas igualmente?",
            )
            if not permitir_nuevas:
                return

        if self._matricula_en_edicion is not None:
            mat_edit = self._matricula_en_edicion

            def accion_edit() -> None:
                foto, actualizar_foto = self._leer_foto_opcional()
                ing = parsear_fecha(self.m_ingreso.get(), "Fecha de ingreso")
                self._ctrl.medicos.editar(
                    matricula=mat_edit,
                    nombre=self.m_nombre.get(),
                    apellido=self.m_apellido.get(),
                    cuil=self.m_cuil.get().strip(),
                    fecha_ingreso=datetime.combine(ing, datetime.min.time()),
                    max_guardias=parsear_entero(self.m_maxg.get(), "Máx. guardias"),
                    especialidades=esp_lista,
                    foto=foto,
                    actualizar_foto=actualizar_foto,
                    permitir_nuevas_especialidades=permitir_nuevas,
                )

            if ejecutar(accion_edit, "Médico actualizado.", self._on_change):
                self._limpiar_form()
            return

        def accion_alta() -> None:
            foto, _ = self._leer_foto_opcional()
            ing = parsear_fecha(self.m_ingreso.get(), "Fecha de ingreso")
            self._ctrl.medicos.alta(
                matricula=parsear_entero(self.m_mat.get(), "Matrícula"),
                dni=self.m_dni.get().strip(),
                nombre=self.m_nombre.get(),
                apellido=self.m_apellido.get(),
                cuil=self.m_cuil.get().strip(),
                fecha_ingreso=datetime.combine(ing, datetime.min.time()),
                max_guardias=parsear_entero(self.m_maxg.get(), "Máx. guardias"),
                foto=foto,
                especialidades=esp_lista,
                permitir_nuevas_especialidades=permitir_nuevas,
            )

        if ejecutar(accion_alta, "Médico guardado.", self._on_change):
            self._limpiar_form()

    def ver_ficha(self) -> None:
        def accion() -> None:
            fila = self.t_medicos.fila_seleccionada("Seleccioná un médico de la lista.")
            mat = int(fila[0])
            med = self._ctrl.medicos.obtener(mat)
            vacaciones = self._ctrl.medicos.listar_vacaciones(matricula=mat)

            win = tk.Toplevel(self)
            win.title(f"Ficha del médico - Mat. {med.matricula}")
            win.geometry("560x440")
            marco = ttk.Frame(win, padding=12)
            marco.pack(fill="both", expand=True)

            sup = ttk.Frame(marco)
            sup.pack(fill="x")

            # Foto BLOB
            if med.foto:
                try:
                    img = Image.open(io.BytesIO(med.foto))
                    img.thumbnail((150, 150))
                    tk_img = ImageTk.PhotoImage(img)
                    lbl_foto = ttk.Label(sup, image=tk_img)
                    lbl_foto.image = tk_img  # type: ignore[attr-defined]
                    lbl_foto.pack(side="left", padx=(0, 14))
                except Exception:
                    ttk.Label(sup, text=f"Foto cargada ({len(med.foto)} bytes)").pack(
                        side="left", padx=(0, 14)
                    )
            else:
                ttk.Label(sup, text="Sin foto").pack(side="left", padx=(0, 14))

            datos = ttk.Frame(sup)
            datos.pack(side="left", fill="x", expand=True)
            ttk.Label(datos, text=med.nombre_completo, font=("TkDefaultFont", 11, "bold")).pack(
                anchor="w"
            )
            ttk.Label(datos, text=f"Matrícula: {med.matricula}   |   DNI: {med.dni}").pack(
                anchor="w", pady=2
            )
            ttk.Label(datos, text=f"CUIL/CUIT: {med.cuil_cuit}").pack(anchor="w", pady=2)
            ttk.Label(
                datos,
                text=f"Ingreso: {med.fecha_ingreso.strftime('%Y-%m-%d')}   |   Máx. guardias/mes: {med.cantidad_guardias}",
            ).pack(anchor="w", pady=2)

            esp_txt = (
                ", ".join(
                    f"{e.nombre_especialidad} ({'hace guardia' if e.hace_guardia else 'no hace guardia'})"
                    for e in med.especialidades
                )
                or "Sin especialidades"
            )
            ttk.Label(datos, text=f"Especialidades: {esp_txt}", wraplength=340).pack(
                anchor="w", pady=2
            )

            ttk.Label(marco, text="Vacaciones registradas:").pack(anchor="w", pady=(12, 4))
            tbl_vac = TablaPaginada(
                marco,
                ("inicio", "fin"),
                ancho=220,
                titulos={"inicio": "Inicio", "fin": "Fin"},
                altura=6,
                page_size=10,
            )
            tbl_vac.pack(expand=True, fill="both")
            tbl_vac.cargar([(v.fecha_inicio, v.fecha_fin) for v in vacaciones])

        ejecutar(accion)
