"""Helpers reutilizables de Tkinter: formularios, manejo de errores, login y tabla paginada."""

from __future__ import annotations

import math
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Any, Callable, Sequence

from hospital.config import OracleConfig
from hospital.controllers.container import AppControllers
from hospital.models.exceptions import (
    AppError,
    ErrorConcurrencia,
    ErrorConexion,
    ErrorTrigger,
    ReglaError,
)


def ejecutar(
    accion: Callable[[], Any],
    mensaje_ok: str | None = None,
    despues: Callable[[], Any] | None = None,
) -> Any:
    """Ejecuta `accion()` manejando errores de negocio, triggers y BD de forma uniforme."""
    try:
        resultado = accion()
    except ErrorTrigger as e:
        messagebox.showwarning(f"Regla de negocio (ORA-{e.codigo})", str(e))
        return None
    except ErrorConcurrencia as e:
        messagebox.showwarning("Recurso ocupado", str(e))
        return None
    except ReglaError as e:
        messagebox.showwarning("No se pudo completar", str(e))
        return None
    except ErrorConexion as e:
        messagebox.showerror("Error de conexión", str(e))
        return None
    except AppError as e:
        messagebox.showerror("Error de base de datos", str(e))
        return None
    except ValueError as e:
        messagebox.showwarning("Dato inválido", str(e))
        return None
    except Exception as e:
        messagebox.showerror("Error inesperado", str(e))
        return None

    if mensaje_ok:
        messagebox.showinfo("Listo", mensaje_ok)
    if despues:
        despues()
    return resultado if resultado is not None else True


def parsear_fecha(texto: str, nombre: str) -> date:
    try:
        return datetime.strptime((texto or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{nombre}: usá el formato AAAA-MM-DD (ej. 2026-11-21).") from exc


def parsear_fecha_hora(texto: str, nombre: str) -> datetime:
    limpio = (texto or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(limpio, fmt)
        except ValueError:
            continue
    raise ValueError(f"{nombre}: usá el formato AAAA-MM-DD HH:MM (ej. 2026-11-24 10:00).")


def parsear_entero(texto: str, nombre: str) -> int:
    try:
        return int((texto or "").strip())
    except ValueError as exc:
        raise ValueError(f"{nombre}: tiene que ser un número entero.") from exc


def texto_celda(valor: Any) -> Any:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%Y-%m-%d")
    return valor


def campo(parent: tk.Widget, fila: int, texto: str, ancho: int = 30) -> ttk.Entry:
    ttk.Label(parent, text=texto).grid(row=fila, column=0, sticky="e", padx=6, pady=3)
    entrada = ttk.Entry(parent, width=ancho)
    entrada.grid(row=fila, column=1, sticky="w", pady=3)
    return entrada


def combo(
    parent: tk.Widget,
    fila: int,
    texto: str,
    ancho: int = 45,
    solo_lectura: bool = True,
) -> ttk.Combobox:
    ttk.Label(parent, text=texto).grid(row=fila, column=0, sticky="e", padx=6, pady=3)
    cb = ttk.Combobox(parent, width=ancho, state="readonly" if solo_lectura else "normal")
    cb.grid(row=fila, column=1, sticky="w", pady=3)
    cb.mapa = {}  # type: ignore[attr-defined]
    return cb


def cargar_combo(cb: ttk.Combobox, items: Sequence[tuple[str, Any]]) -> None:
    """Carga un combobox con pares `(texto_visible, valor)` preservando selección si sigue vigente."""
    cb.mapa = dict(items)  # type: ignore[attr-defined]
    cb["values"] = [texto for texto, _ in items]
    if cb.get() not in cb.mapa:  # type: ignore[attr-defined]
        cb.set("")


def valor_combo(cb: ttk.Combobox, nombre: str) -> Any:
    mapa = getattr(cb, "mapa", {})
    if cb.get() not in mapa:
        raise ReglaError(f"Elegí una opción en: {nombre}.")
    return mapa[cb.get()]


class TablaPaginada(ttk.Frame):
    """Treeview con scrollbar vertical y paginación integrada para grandes volúmenes de datos."""

    def __init__(
        self,
        parent: tk.Widget,
        columnas: Sequence[str],
        ancho: int = 140,
        anchos_columna: dict[str, int] | None = None,
        titulos: dict[str, str] | None = None,
        altura: int = 8,
        page_size: int = 15,
    ) -> None:
        super().__init__(parent)
        self._filas: list[tuple[Any, ...]] = []
        self._pagina = 1
        self._page_size = page_size

        marco_tree = ttk.Frame(self)
        marco_tree.pack(expand=True, fill="both")

        self.tree = ttk.Treeview(marco_tree, columns=columnas, show="headings", height=altura)
        for c in columnas:
            titulo = (titulos or {}).get(c, c)
            col_w = (anchos_columna or {}).get(c, ancho)
            self.tree.heading(c, text=titulo, anchor="center")
            self.tree.column(c, width=col_w, anchor="center")

        scroll_y = ttk.Scrollbar(marco_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side="left", expand=True, fill="both")
        scroll_y.pack(side="right", fill="y")

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(4, 0))

        self.lbl_info = ttk.Label(barra, text="0 registros")
        self.lbl_info.pack(side="left", padx=4)

        self.btn_sig = ttk.Button(barra, text="Siguiente", width=10, command=self._siguiente)
        self.btn_sig.pack(side="right", padx=2)
        self.btn_ant = ttk.Button(barra, text="Anterior", width=10, command=self._anterior)
        self.btn_ant.pack(side="right", padx=2)

        ttk.Label(barra, text="Por página:").pack(side="right", padx=(8, 2))
        self.cb_tam = ttk.Combobox(
            barra,
            values=["10", "15", "25", "50"],
            width=4,
            state="readonly",
        )
        self.cb_tam.set(str(page_size))
        self.cb_tam.bind("<<ComboboxSelected>>", self._cambiar_tam)
        self.cb_tam.pack(side="right", padx=2)

    def cargar(self, filas: Sequence[Sequence[Any]], reset_pagina: bool = False) -> None:
        self._filas = [tuple(texto_celda(v) for v in f) for f in filas]
        if reset_pagina:
            self._pagina = 1
        self._render_pagina()

    def _total_paginas(self) -> int:
        if not self._filas:
            return 1
        return max(1, math.ceil(len(self._filas) / self._page_size))

    def _render_pagina(self) -> None:
        total = len(self._filas)
        total_pags = self._total_paginas()
        self._pagina = min(max(1, self._pagina), total_pags)

        self.tree.delete(*self.tree.get_children())
        inicio = (self._pagina - 1) * self._page_size
        fin = min(inicio + self._page_size, total)
        for fila in self._filas[inicio:fin]:
            self.tree.insert("", "end", values=fila)

        if total == 0:
            self.lbl_info.config(text="0 registros")
        else:
            self.lbl_info.config(
                text=f"Mostrando {inicio + 1}-{fin} de {total} (Pág. {self._pagina}/{total_pags})"
            )

        self.btn_ant.config(state="disabled" if self._pagina <= 1 else "normal")
        self.btn_sig.config(state="disabled" if self._pagina >= total_pags else "normal")

    def _anterior(self) -> None:
        if self._pagina > 1:
            self._pagina -= 1
            self._render_pagina()

    def _siguiente(self) -> None:
        if self._pagina < self._total_paginas():
            self._pagina += 1
            self._render_pagina()

    def _cambiar_tam(self, _event: Any = None) -> None:
        try:
            self._page_size = int(self.cb_tam.get())
        except ValueError:
            return
        self._pagina = 1
        self._render_pagina()

    def fila_seleccionada(self, mensaje: str) -> list[Any]:
        sel = self.tree.selection()
        if not sel:
            raise ReglaError(mensaje)
        return list(self.tree.item(sel[0])["values"])


def pedir_credenciales(
    root: tk.Tk,
    config_inicial: OracleConfig,
) -> AppControllers | None:
    """Muestra el login directamente en la ventana principal (visible y centrada en pantalla)."""
    resultado: dict[str, AppControllers | None] = {"controllers": None}
    finalizado = tk.BooleanVar(root, value=False)

    root.title("Hospital - Iniciar sesión")
    root.resizable(False, False)

    marco = ttk.Frame(root, padding=20)
    marco.pack(fill="both", expand=True)

    ttk.Label(marco, text="Sistema Hospitalario", font=("TkDefaultFont", 11, "bold")).grid(
        row=0, column=0, columnspan=2, pady=(0, 10)
    )

    e_user = campo(marco, 1, "Usuario:", 26)
    e_user.insert(0, config_inicial.usuario)
    ttk.Label(marco, text="Contraseña:").grid(row=2, column=0, sticky="e", padx=6, pady=3)
    e_pass = ttk.Entry(marco, width=26, show="*")
    e_pass.grid(row=2, column=1, sticky="w", pady=3)
    e_pass.insert(0, config_inicial.clave)

    lbl_err = ttk.Label(marco, text="", foreground="#b00020", wraplength=280)
    lbl_err.grid(row=3, column=0, columnspan=2, pady=(6, 4))

    def cerrar_sin_conectar() -> None:
        finalizado.set(True)

    def intentar_conectar(_event: Any = None) -> None:
        usuario = e_user.get().strip()
        clave = e_pass.get()
        if not usuario or not clave:
            lbl_err.config(text="Ingresá usuario y contraseña.")
            return
        lbl_err.config(text="Conectando...")
        root.update_idletasks()
        cfg = OracleConfig(
            usuario=usuario,
            clave=clave,
            dsn=config_inicial.dsn,
            pool_min=config_inicial.pool_min,
            pool_max=config_inicial.pool_max,
            pool_increment=config_inicial.pool_increment,
        )
        ctrls = AppControllers.desde_config(cfg)
        try:
            ctrls.db.probar_conexion()
        except Exception as exc:
            ctrls.db.cerrar()
            lbl_err.config(text=str(exc))
            return
        resultado["controllers"] = ctrls
        finalizado.set(True)

    botones = ttk.Frame(marco)
    botones.grid(row=4, column=0, columnspan=2, pady=(8, 0))
    ttk.Button(botones, text="Conectar", command=intentar_conectar).pack(side="left", padx=4)
    ttk.Button(botones, text="Salir", command=cerrar_sin_conectar).pack(side="left", padx=4)

    root.protocol("WM_DELETE_WINDOW", cerrar_sin_conectar)
    bind_id = root.bind("<Return>", intentar_conectar)

    root.update_idletasks()
    w = max(340, root.winfo_reqwidth())
    h = max(190, root.winfo_reqheight())
    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.deiconify()
    root.lift()
    root.focus_force()
    e_user.focus_set()

    root.wait_variable(finalizado)

    try:
        root.unbind("<Return>", bind_id)
        marco.destroy()
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        root.resizable(True, True)
    except tk.TclError:
        pass

    return resultado["controllers"]
