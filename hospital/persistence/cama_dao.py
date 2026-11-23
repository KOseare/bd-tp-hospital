"""DAO de solo lectura para SECTOR, HABITACION y CAMA (+ bloqueo FOR UPDATE WAIT 5)."""

from __future__ import annotations

from typing import Any

from hospital.models.entities import CamaEstado


def listar_sectores(cur: Any) -> list[str]:
    cur.execute("SELECT nombre_sector FROM sector ORDER BY nombre_sector")
    return [str(f[0]) for f in cur.fetchall()]


def listar_camas_libres(cur: Any) -> list[tuple[int, int, str]]:
    cur.execute(
        """
        SELECT nro_habitacion, nro_cama, nombre_sector
          FROM vw_cama_disponible
         ORDER BY nro_habitacion, nro_cama
        """
    )
    return [(int(f[0]), int(f[1]), str(f[2])) for f in cur.fetchall()]


def listar_todas_con_estado(
    cur: Any,
    nombre_sector: str | None = None,
    solo_disponibles: bool | None = None,
) -> list[CamaEstado]:
    """Lista todas las camas derivando si están Libres u Ocupadas desde OCUPA."""
    sql = """
        SELECT h.nombre_sector,
               c.nro_habitacion,
               h.piso,
               h.orientacion,
               c.nro_cama,
               oa.id_internacion,
               oa.dni,
               oa.paciente,
               oa.fecha_asignacion_cama
          FROM cama c
          JOIN habitacion h ON h.nro_habitacion = c.nro_habitacion
          LEFT JOIN (
              SELECT o.nro_habitacion,
                     o.nro_cama,
                     o.id_internacion,
                     i.dni,
                     pe.apellido || ', ' || pe.nombre AS paciente,
                     o.fecha_asignacion_cama
                FROM ocupa o
                JOIN internacion i ON i.id_internacion = o.id_internacion
                JOIN persona pe ON pe.dni = i.dni
               WHERE o.fecha_asignacion_cama <= SYSTIMESTAMP
                 AND (o.fecha_terminacion_cama IS NULL OR o.fecha_terminacion_cama > SYSTIMESTAMP)
          ) oa
            ON oa.nro_habitacion = c.nro_habitacion
           AND oa.nro_cama = c.nro_cama
    """
    condiciones: list[str] = []
    params: dict[str, Any] = {}
    if nombre_sector:
        condiciones.append("h.nombre_sector = :sec")
        params["sec"] = nombre_sector
    if solo_disponibles is True:
        condiciones.append("oa.id_internacion IS NULL")
    elif solo_disponibles is False:
        condiciones.append("oa.id_internacion IS NOT NULL")

    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY h.nombre_sector, c.nro_habitacion, c.nro_cama"

    cur.execute(sql, params)
    return [
        CamaEstado(
            nombre_sector=str(f[0]),
            nro_habitacion=int(f[1]),
            piso=int(f[2]),
            orientacion=str(f[3]),
            nro_cama=int(f[4]),
            ocupada=(f[5] is not None),
            id_internacion_activa=int(f[5]) if f[5] is not None else None,
            dni_paciente=str(f[6]) if f[6] is not None else None,
            nombre_paciente=str(f[7]) if f[7] is not None else None,
            fecha_asignacion=f[8],
        )
        for f in cur.fetchall()
    ]


def bloquear_cama(cur: Any, nro_habitacion: int, nro_cama: int) -> bool:
    """Bloquea la fila de CAMA con WAIT 5 para serializar asignaciones sin colgar la UI."""
    cur.execute(
        """
        SELECT 1
          FROM cama
         WHERE nro_habitacion = :h AND nro_cama = :c
           FOR UPDATE WAIT 5
        """,
        h=nro_habitacion,
        c=nro_cama,
    )
    return cur.fetchone() is not None
