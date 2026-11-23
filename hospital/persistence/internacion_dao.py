"""DAO de las tablas INTERNACION y OCUPA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hospital.models.entities import Internacion, OcupacionCama


def listar(
    cur: Any,
    solo_activas: bool = True,
    dni_paciente: str | None = None,
) -> list[Internacion]:
    sql = """
        SELECT i.id_internacion,
               i.dni,
               pp.apellido || ', ' || pp.nombre AS paciente,
               i.matricula_medico,
               pm.apellido || ', ' || pm.nombre AS medico,
               i.fecha_inicio_internacion,
               i.fecha_terminacion_internacion,
               o.nro_habitacion,
               o.nro_cama,
               h.nombre_sector
          FROM internacion i
          JOIN persona pp ON pp.dni = i.dni
          JOIN medico m ON m.matricula_medico = i.matricula_medico
          JOIN persona pm ON pm.dni = m.dni
          LEFT JOIN ocupa o
            ON o.id_internacion = i.id_internacion
           AND o.fecha_terminacion_cama IS NULL
          LEFT JOIN habitacion h
            ON h.nro_habitacion = o.nro_habitacion
    """
    condiciones: list[str] = []
    params: dict[str, Any] = {}
    if solo_activas:
        condiciones.append("i.fecha_terminacion_internacion IS NULL")
    if dni_paciente:
        condiciones.append("i.dni = :dni")
        params["dni"] = dni_paciente
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY i.id_internacion DESC"

    cur.execute(sql, params)
    return [
        Internacion(
            id_internacion=int(f[0]),
            dni=str(f[1]),
            paciente=str(f[2]),
            matricula_medico=int(f[3]),
            medico=str(f[4]),
            fecha_inicio=f[5],
            fecha_terminacion=f[6],
            nro_habitacion=int(f[7]) if f[7] is not None else None,
            nro_cama=int(f[8]) if f[8] is not None else None,
            nombre_sector=str(f[9]) if f[9] is not None else None,
        )
        for f in cur.fetchall()
    ]


def tiene_internacion_abierta(cur: Any, dni: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*)
          FROM internacion
         WHERE dni = :dni AND fecha_terminacion_internacion IS NULL
        """,
        dni=dni,
    )
    return int(cur.fetchone()[0]) > 0


def bloquear_internacion(cur: Any, id_internacion: int) -> tuple[datetime, datetime | None] | None:
    """Bloquea la internación con FOR UPDATE WAIT 5 y devuelve (inicio, terminacion)."""
    cur.execute(
        """
        SELECT fecha_inicio_internacion, fecha_terminacion_internacion
          FROM internacion
         WHERE id_internacion = :i
           FOR UPDATE WAIT 5
        """,
        i=id_internacion,
    )
    fila = cur.fetchone()
    if fila is None:
        return None
    return (fila[0], fila[1])


def insertar_internacion(
    cur: Any,
    fecha_inicio: datetime,
    matricula_medico: int,
    dni: str,
) -> int:
    nuevo_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO internacion (fecha_inicio_internacion, matricula_medico, dni)
        VALUES (:ini, :mat, :dni)
        RETURNING id_internacion INTO :nuevo_id
        """,
        ini=fecha_inicio,
        mat=matricula_medico,
        dni=dni,
        nuevo_id=nuevo_id,
    )
    val = nuevo_id.getvalue()
    return int(val[0] if isinstance(val, list) else val)


def cerrar_internacion(cur: Any, id_internacion: int, fecha_terminacion: datetime) -> int:
    cur.execute(
        """
        UPDATE internacion
           SET fecha_terminacion_internacion = :fin
         WHERE id_internacion = :i
        """,
        fin=fecha_terminacion,
        i=id_internacion,
    )
    return cur.rowcount


def bloquear_ocupacion_activa(
    cur: Any,
    id_internacion: int,
) -> tuple[int, int, datetime] | None:
    """Bloquea la fila activa de OCUPA y devuelve (nro_hab, nro_cama, fecha_asignacion)."""
    cur.execute(
        """
        SELECT nro_habitacion, nro_cama, fecha_asignacion_cama
          FROM ocupa
         WHERE id_internacion = :i AND fecha_terminacion_cama IS NULL
           FOR UPDATE WAIT 5
        """,
        i=id_internacion,
    )
    fila = cur.fetchone()
    if fila is None:
        return None
    return (int(fila[0]), int(fila[1]), fila[2])


def insertar_ocupa(
    cur: Any,
    id_internacion: int,
    fecha_asignacion: datetime,
    nro_habitacion: int,
    nro_cama: int,
) -> None:
    cur.execute(
        """
        INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama)
        VALUES (:i, :asig, :h, :c)
        """,
        i=id_internacion,
        asig=fecha_asignacion,
        h=nro_habitacion,
        c=nro_cama,
    )


def cerrar_ocupacion_activa(cur: Any, id_internacion: int, fecha_terminacion: datetime) -> int:
    cur.execute(
        """
        UPDATE ocupa
           SET fecha_terminacion_cama = :fin
         WHERE id_internacion = :i AND fecha_terminacion_cama IS NULL
        """,
        fin=fecha_terminacion,
        i=id_internacion,
    )
    return cur.rowcount


def listar_ocupaciones(cur: Any, id_internacion: int) -> list[OcupacionCama]:
    cur.execute(
        """
        SELECT o.id_internacion,
               o.nro_habitacion,
               o.nro_cama,
               h.nombre_sector,
               h.piso,
               h.orientacion,
               o.fecha_asignacion_cama,
               o.fecha_terminacion_cama
          FROM ocupa o
          JOIN habitacion h ON h.nro_habitacion = o.nro_habitacion
         WHERE o.id_internacion = :i
         ORDER BY o.fecha_asignacion_cama ASC
        """,
        i=id_internacion,
    )
    return [
        OcupacionCama(
            id_internacion=int(f[0]),
            nro_habitacion=int(f[1]),
            nro_cama=int(f[2]),
            nombre_sector=str(f[3]),
            piso=int(f[4]),
            orientacion=str(f[5]),
            fecha_asignacion=f[6],
            fecha_terminacion=f[7],
        )
        for f in cur.fetchall()
    ]
