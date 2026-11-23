"""DAO de la tabla PACIENTE (CRUD completo junto con PERSONA)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from hospital.models.entities import Paciente


def _a_date(val: Any) -> date:
    if isinstance(val, datetime):
        return val.date()
    return val


def listar(cur: Any, filtro: str | None = None) -> list[Paciente]:
    sql = """
        SELECT p.dni, pe.apellido, pe.nombre,
               p.fecha_nacimiento_paciente, p.sexo_paciente
          FROM paciente p
          JOIN persona pe ON pe.dni = p.dni
    """
    params: dict[str, Any] = {}
    if filtro:
        sql += """
         WHERE LOWER(p.dni) LIKE :q
            OR LOWER(pe.apellido) LIKE :q
            OR LOWER(pe.nombre) LIKE :q
        """
        params["q"] = f"%{filtro.lower()}%"
    sql += " ORDER BY pe.apellido, pe.nombre"
    cur.execute(sql, params)
    return [
        Paciente(
            dni=str(f[0]),
            apellido=str(f[1]),
            nombre=str(f[2]),
            fecha_nacimiento=_a_date(f[3]),
            sexo=str(f[4]),
        )
        for f in cur.fetchall()
    ]


def obtener_por_dni(cur: Any, dni: str) -> Paciente | None:
    cur.execute(
        """
        SELECT p.dni, pe.apellido, pe.nombre,
               p.fecha_nacimiento_paciente, p.sexo_paciente
          FROM paciente p
          JOIN persona pe ON pe.dni = p.dni
         WHERE p.dni = :dni
        """,
        dni=dni,
    )
    f = cur.fetchone()
    if f is None:
        return None
    return Paciente(
        dni=str(f[0]),
        apellido=str(f[1]),
        nombre=str(f[2]),
        fecha_nacimiento=_a_date(f[3]),
        sexo=str(f[4]),
    )


def existe(cur: Any, dni: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM paciente WHERE dni = :dni", dni=dni)
    return int(cur.fetchone()[0]) > 0


def bloquear(cur: Any, dni: str) -> bool:
    cur.execute("SELECT 1 FROM paciente WHERE dni = :dni FOR UPDATE WAIT 5", dni=dni)
    return cur.fetchone() is not None


def insertar(cur: Any, dni: str, fecha_nacimiento: date, sexo: str) -> None:
    cur.execute(
        """
        INSERT INTO paciente (dni, fecha_nacimiento_paciente, sexo_paciente)
        VALUES (:dni, :nac, :sexo)
        """,
        dni=dni,
        nac=fecha_nacimiento,
        sexo=sexo,
    )


def actualizar(cur: Any, dni: str, fecha_nacimiento: date, sexo: str) -> int:
    cur.execute(
        """
        UPDATE paciente
           SET fecha_nacimiento_paciente = :nac,
               sexo_paciente = :sexo
         WHERE dni = :dni
        """,
        nac=fecha_nacimiento,
        sexo=sexo,
        dni=dni,
    )
    return cur.rowcount


def eliminar(cur: Any, dni: str) -> int:
    cur.execute("DELETE FROM paciente WHERE dni = :dni", dni=dni)
    return cur.rowcount


def tiene_internaciones(cur: Any, dni: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM internacion WHERE dni = :dni", dni=dni)
    return int(cur.fetchone()[0]) > 0
