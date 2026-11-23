"""Validadores puros de entrada reutilizados por los controladores."""

from __future__ import annotations

import re
from datetime import date, datetime

from hospital.models.exceptions import ReglaError

DIAS_SEMANA = {
    0: "LUNES",
    1: "MARTES",
    2: "MIERCOLES",
    3: "JUEVES",
    4: "VIERNES",
    5: "SABADO",
    6: "DOMINGO",
}


def validar_dni(dni: str) -> str:
    limpio = (dni or "").strip()
    if not re.fullmatch(r"[0-9]{6,9}", limpio):
        raise ReglaError("El DNI debe tener entre 6 y 9 dígitos numéricos.")
    return limpio


def validar_cuil(cuil: str) -> str:
    limpio = (cuil or "").strip().replace("-", "")
    if not re.fullmatch(r"[0-9]{11}", limpio):
        raise ReglaError("El CUIL/CUIT debe tener exactamente 11 dígitos numéricos.")
    return limpio


def validar_texto(valor: str, nombre_campo: str, max_len: int = 100) -> str:
    limpio = (valor or "").strip()
    if not limpio:
        raise ReglaError(f"Falta completar: {nombre_campo}.")
    if len(limpio) > max_len:
        raise ReglaError(f"{nombre_campo} no puede superar los {max_len} caracteres.")
    return limpio


def validar_sexo(sexo: str) -> str:
    limpio = (sexo or "").strip().upper()
    if limpio not in ("F", "M", "X"):
        raise ReglaError("El sexo debe ser F, M o X.")
    return limpio


def validar_fecha_nacimiento(fecha_nac: date) -> date:
    if isinstance(fecha_nac, datetime):
        fecha_nac = fecha_nac.date()
    if not isinstance(fecha_nac, date):
        raise ReglaError("Fecha de nacimiento inválida.")
    if fecha_nac > date.today():
        raise ReglaError("La fecha de nacimiento no puede ser futura.")
    return fecha_nac


def validar_matricula(matricula: int) -> int:
    if not isinstance(matricula, int) or isinstance(matricula, bool) or matricula <= 0:
        raise ReglaError("La matrícula debe ser un número entero positivo.")
    return matricula


def validar_max_guardias(max_guardias: int) -> int:
    if not isinstance(max_guardias, int) or isinstance(max_guardias, bool) or max_guardias < 0:
        raise ReglaError("El máximo de guardias por mes no puede ser negativo.")
    return max_guardias


def _normalizar_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None and dt.utcoffset() is not None:
        try:
            return dt.astimezone().replace(tzinfo=None)
        except (OSError, OverflowError, ValueError):
            return dt.replace(tzinfo=None)
    return dt


def comparar_datetimes(dt_a: datetime, dt_b: datetime) -> int:
    """Compara dos datetimes de forma segura (incluso naive vs timezone-aware)."""
    a = _normalizar_naive(dt_a)
    b = _normalizar_naive(dt_b)
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def dia_semana_es(dt: datetime | date) -> str:
    """Devuelve el nombre del día en el formato de `RONDA.dia_ronda` (LUNES..DOMINGO)."""
    return DIAS_SEMANA[dt.weekday()]
