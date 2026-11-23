"""Vista Tkinter de la batería interactiva de pruebas (desacoplada de SQL/oracledb)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from hospital.controllers.pruebas_controller import PruebasController
from hospital.models.entities import CasoPrueba


class PruebasView(ttk.Frame):
    def __init__(self, parent: tk.Widget, pruebas_ctrl: PruebasController) -> None:
        super().__init__(parent)
        self._ctrl = pruebas_ctrl
        self._resultados: dict[str, tuple[Optional[bool], str]] = {}
        self._construir_ui()

    def _construir_ui(self) -> None:
        barra = ttk.Frame(self)
        barra.pack(fill="x", padx=10, pady=8)

        ttk.Button(barra, text="Ejecutar seleccionada", command=self.ejecutar_seleccionada).pack(
            side="left", padx=4
        )
        ttk.Button(barra, text="Ejecutar grupo", command=self.ejecutar_grupo).pack(
            side="left", padx=4
        )
        ttk.Button(barra, text="Ejecutar toda la batería", command=self.ejecutar_todas).pack(
            side="left", padx=4
        )
        ttk.Button(barra, text="Limpiar", command=self.limpiar).pack(side="left", padx=4)

        total = len(self._ctrl.casos)
        self.lbl_resumen = ttk.Label(
            barra, text=f"0 / {total} ejecutadas (cada prueba hace ROLLBACK automático)"
        )
        self.lbl_resumen.pack(side="right", padx=6)

        marco_tabla = ttk.Frame(self)
        marco_tabla.pack(expand=True, fill="both", padx=10)

        cols = ("codigo", "grupo", "tipo", "caso", "esperado", "estado")
        self.tabla = ttk.Treeview(marco_tabla, columns=cols, show="headings", height=14)
        anchos = {
            "codigo": 55,
            "grupo": 175,
            "tipo": 65,
            "caso": 370,
            "esperado": 130,
            "estado": 90,
        }
        titulos = {
            "codigo": "#",
            "grupo": "Grupo / Requerimiento",
            "tipo": "Tipo",
            "caso": "Caso de prueba",
            "esperado": "Esperado",
            "estado": "Estado",
        }
        for c in cols:
            self.tabla.heading(c, text=titulos[c], anchor="center")
            self.tabla.column(c, width=anchos[c], anchor="center")

        self.tabla.tag_configure("pass", background="#dff5e1")
        self.tabla.tag_configure("fail", background="#fadbd8")
        self.tabla.tag_configure("pend", background="")

        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", expand=True, fill="both")
        scroll.pack(side="right", fill="y")

        self.tabla.bind("<<TreeviewSelect>>", self._mostrar_detalle)
        self.tabla.bind("<Double-1>", lambda _e: self.ejecutar_seleccionada())

        marco_det = ttk.LabelFrame(
            self, text="Detalle del caso (doble clic en una fila para ejecutarla)"
        )
        marco_det.pack(fill="x", padx=10, pady=8)
        self.txt_detalle = tk.Text(
            marco_det, height=8, wrap="word", state="disabled", font=("Consolas", 9)
        )
        self.txt_detalle.pack(fill="both", expand=True, padx=6, pady=4)

        self._cargar_filas()

    def _cargar_filas(self) -> None:
        self.tabla.delete(*self.tabla.get_children())
        for c in self._ctrl.casos:
            self.tabla.insert(
                "",
                "end",
                iid=c.codigo,
                values=(c.codigo, c.grupo, c.tipo, c.nombre, c.esperado, "Pendiente"),
                tags=("pend",),
            )

    def _correr_caso(self, caso: CasoPrueba) -> None:
        ok, detalle = self._ctrl.ejecutar_caso(caso)
        self._resultados[caso.codigo] = (ok, detalle)
        estado = "PASS" if ok else "FAIL"
        tag = "pass" if ok else "fail"
        self.tabla.item(
            caso.codigo,
            values=(caso.codigo, caso.grupo, caso.tipo, caso.nombre, caso.esperado, estado),
            tags=(tag,),
        )

    def _actualizar_resumen(self) -> None:
        total = len(self._ctrl.casos)
        ejecutadas = len(self._resultados)
        ok_n = sum(1 for ok, _ in self._resultados.values() if ok)
        fail_n = ejecutadas - ok_n
        self.lbl_resumen.config(
            text=f"Ejecutadas: {ejecutadas}/{total} | PASS: {ok_n} | FAIL: {fail_n} (base intacta con ROLLBACK)"
        )

    def _mostrar_detalle(self, _event: object = None) -> None:
        sel = self.tabla.selection()
        if not sel:
            return
        caso = self._ctrl.obtener_caso(sel[0])
        if not caso:
            return
        res = self._resultados.get(caso.codigo)
        lineas = [
            f"[{caso.codigo}] {caso.grupo} - {caso.nombre} ({caso.tipo})",
            f"Descripción: {caso.descripcion}",
            f"Operación  : {caso.sql_resumen}",
            f"Esperado   : {caso.esperado}",
            "-" * 80,
        ]
        if res is None:
            lineas.append("Estado: Pendiente (hacé doble clic o presioná 'Ejecutar seleccionada').")
        else:
            ok, detalle = res
            lineas.append(f"Resultado: {'PASS' if ok else 'FAIL'}")
            lineas.append(detalle)

        self.txt_detalle.config(state="normal")
        self.txt_detalle.delete("1.0", "end")
        self.txt_detalle.insert("1.0", "\n".join(lineas))
        self.txt_detalle.config(state="disabled")

    def ejecutar_seleccionada(self) -> None:
        casos = self._ctrl.casos
        if not casos:
            return
        sel = self.tabla.selection()
        if not sel:
            self.tabla.selection_set(casos[0].codigo)
            sel = (casos[0].codigo,)
        caso = self._ctrl.obtener_caso(sel[0])
        if caso:
            self._correr_caso(caso)
            self._actualizar_resumen()
            self._mostrar_detalle()

    def ejecutar_grupo(self) -> None:
        casos = self._ctrl.casos
        if not casos:
            return
        sel = self.tabla.selection()
        if not sel:
            self.tabla.selection_set(casos[0].codigo)
            sel = (casos[0].codigo,)
        actual = self._ctrl.obtener_caso(sel[0])
        if not actual:
            return
        for c in casos:
            if c.grupo == actual.grupo:
                self._correr_caso(c)
                self.update_idletasks()
        self._actualizar_resumen()
        self._mostrar_detalle()

    def ejecutar_todas(self) -> None:
        casos = self._ctrl.casos
        for c in casos:
            self._correr_caso(c)
            self.update_idletasks()
        self._actualizar_resumen()
        if casos and not self.tabla.selection():
            self.tabla.selection_set(casos[0].codigo)
        self._mostrar_detalle()

    def limpiar(self) -> None:
        self._resultados.clear()
        self._cargar_filas()
        self.lbl_resumen.config(
            text=f"0 / {len(self._ctrl.casos)} ejecutadas (cada prueba hace ROLLBACK automático)"
        )
        self.txt_detalle.config(state="normal")
        self.txt_detalle.delete("1.0", "end")
        self.txt_detalle.config(state="disabled")
