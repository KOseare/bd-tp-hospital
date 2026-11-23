"""Excepciones de dominio y base de datos del Sistema Hospitalario."""

from __future__ import annotations


class AppError(Exception):
    """Excepción base de la aplicación."""

    def __init__(
        self,
        mensaje: str,
        *,
        codigo_ora: int | None = None,
        detalle: str | None = None,
    ) -> None:
        self.mensaje = mensaje
        self.codigo_ora = codigo_ora
        self.detalle = detalle
        super().__init__(mensaje)


class ReglaError(AppError):
    """Violación de una regla de negocio o restricción del modelo."""


class ErrorTrigger(ReglaError):
    """Error de regla de negocio lanzado por un trigger de Oracle (ORA-20000..20999)."""

    def __init__(self, codigo: int, mensaje: str) -> None:
        self.codigo = codigo
        super().__init__(mensaje, codigo_ora=codigo)


class ErrorConcurrencia(ReglaError):
    """Conflicto de bloqueo concurrente (ORA-00054 / ORA-30006)."""


class ErrorConexion(AppError):
    """Error de autenticación o red al conectar con Oracle."""


class ErrorBaseDatos(AppError):
    """Error técnico de Oracle no clasificado como regla de negocio."""
