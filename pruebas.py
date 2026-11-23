"""Punto de entrada standalone para la Batería interactiva de pruebas (MVC + Persistencia).

Ejecución:
    .\.venv\Scripts\python.exe pruebas.py
"""

from __future__ import annotations

import tkinter as tk

from hospital.config import cargar_config
from hospital.controllers.container import AppControllers
from hospital.views.pruebas_view import PruebasView
from hospital.views.widgets import pedir_credenciales


def main() -> None:
    root = tk.Tk()

    cfg = cargar_config()
    controllers: AppControllers | None = None
    if cfg.esta_configurado:
        candidato = AppControllers.desde_config(cfg)
        try:
            candidato.db.probar_conexion()
            controllers = candidato
        except Exception:
            candidato.db.cerrar()

    if controllers is None:
        controllers = pedir_credenciales(root, cfg)
    if controllers is None:
        try:
            root.destroy()
        except tk.TclError:
            pass
        return

    root.title("Hospital - Batería de pruebas")
    root.geometry("1120x680")
    PruebasView(root, controllers.pruebas).pack(expand=True, fill="both")
    try:
        root.mainloop()
    finally:
        controllers.db.cerrar()


if __name__ == "__main__":
    main()
