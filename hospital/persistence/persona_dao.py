"""DAO de la tabla PERSONA."""

from __future__ import annotations

from typing import Any


def existe(cur: Any, dni: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM persona WHERE dni = :dni", dni=dni)
    return int(cur.fetchone()[0]) > 0


def insertar(cur: Any, dni: str, nombre: str, apellido: str) -> None:
    cur.execute(
        "INSERT INTO persona (dni, nombre, apellido) VALUES (:dni, :nom, :ape)",
        dni=dni,
        nom=nombre,
        ape=apellido,
    )


def actualizar(cur: Any, dni: str, nombre: str, apellido: str) -> int:
    cur.execute(
        "UPDATE persona SET nombre = :nom, apellido = :ape WHERE dni = :dni",
        nom=nombre,
        ape=apellido,
        dni=dni,
    )
    return cur.rowcount


def eliminar(cur: Any, dni: str) -> int:
    cur.execute("DELETE FROM persona WHERE dni = :dni", dni=dni)
    return cur.rowcount
