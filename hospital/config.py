"""Configuración de conexión Oracle cargada desde variables de entorno / archivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 1521
DEFAULT_SERVICE = "FREEPDB1"
DEFAULT_DSN = f"{DEFAULT_HOST}:{DEFAULT_PORT}/{DEFAULT_SERVICE}"

# Turnos de guardia: numero -> (nombre, hora_inicio). Cada turno dura 8 horas.
TURNOS_GUARDIA: dict[int, tuple[str, int]] = {
    1: ("Mañana", 6),
    2: ("Tarde", 14),
    3: ("Noche", 22),
}

TABLAS_TURNO_GUARDIA: dict[int, str] = {
    1: "guardia_turno_manana",
    2: "guardia_turno_tarde",
    3: "guardia_turno_noche",
}


@dataclass(frozen=True)
class OracleConfig:
    """Parámetros de conexión a Oracle (sin credenciales hardcodeadas)."""

    usuario: str = ""
    clave: str = ""
    dsn: str = DEFAULT_DSN
    pool_min: int = 1
    pool_max: int = 4
    pool_increment: int = 1

    @property
    def esta_configurado(self) -> bool:
        return bool(self.usuario.strip() and self.clave and self.dsn.strip())

    def __repr__(self) -> str:
        clave_mask = "***" if self.clave else ""
        return (
            f"OracleConfig(usuario={self.usuario!r}, clave={clave_mask!r}, "
            f"dsn={self.dsn!r}, pool_min={self.pool_min}, pool_max={self.pool_max})"
        )


def cargar_config(dotenv_path: str | Path | None = None) -> OracleConfig:
    """Carga la configuración desde `.env` (si existe) y variables de entorno.

    Soporta tanto `HOSPITAL_USER`/`HOSPITAL_PASSWORD`/`HOSPITAL_DSN` como
    `ORACLE_USER`/`ORACLE_PASSWORD`/`ORACLE_DSN` (o HOST/PORT/SERVICE_NAME).
    """
    if dotenv_path is not None:
        load_dotenv(dotenv_path=dotenv_path, override=False)
    else:
        raiz = Path(__file__).resolve().parent.parent
        load_dotenv(dotenv_path=raiz / ".env", override=False)

    usuario = (os.getenv("HOSPITAL_USER") or os.getenv("ORACLE_USER") or "").strip()
    clave = os.getenv("HOSPITAL_PASSWORD") or os.getenv("ORACLE_PASSWORD") or ""

    dsn = (os.getenv("HOSPITAL_DSN") or os.getenv("ORACLE_DSN") or "").strip()
    if not dsn:
        host = (os.getenv("ORACLE_HOST") or DEFAULT_HOST).strip()
        port = (os.getenv("ORACLE_PORT") or str(DEFAULT_PORT)).strip()
        service = (os.getenv("ORACLE_SERVICE_NAME") or DEFAULT_SERVICE).strip()
        dsn = f"{host}:{port}/{service}"

    return OracleConfig(
        usuario=usuario,
        clave=clave,
        dsn=dsn,
        pool_min=int(os.getenv("ORACLE_POOL_MIN", "1")),
        pool_max=int(os.getenv("ORACLE_POOL_MAX", "4")),
        pool_increment=int(os.getenv("ORACLE_POOL_INCREMENT", "1")),
    )
