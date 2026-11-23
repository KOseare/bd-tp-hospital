"""Punto de entrada de la aplicación del Hospital (Tkinter + Oracle, MVC + Persistencia).

Ejecución:
    .\.venv\Scripts\python.exe app.py
"""

from __future__ import annotations

import tkinter as tk

from hospital.config import cargar_config
from hospital.controllers.container import AppControllers
from hospital.views.main_window import MainWindow
from hospital.views.widgets import pedir_credenciales


def _inicializar_controladores(root: tk.Tk) -> AppControllers | None:
    cfg = cargar_config()
    if cfg.esta_configurado:
        ctrls = AppControllers.desde_config(cfg)
        try:
            ctrls.db.probar_conexion()
            return ctrls
        except Exception:
            ctrls.db.cerrar()
    return pedir_credenciales(root, cfg)


def main() -> None:
    root = tk.Tk()

    controllers = _inicializar_controladores(root)
    if controllers is None:
        try:
            root.destroy()
        except tk.TclError:
            pass
        return

    MainWindow(root, controllers)
    try:
        root.mainloop()
    finally:
        controllers.db.cerrar()


if __name__ == "__main__":
    main()
