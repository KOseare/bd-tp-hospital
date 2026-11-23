"""DAO de reportes respaldados por los Stored Procedures de `05_procedures.sql`."""

from __future__ import annotations

from typing import Any

from hospital.models.entities import CamaDisponible, ComentarioVisita, ResumenSector


def ejecutar_pr_camas_disponibles(
    cnx: Any,
) -> tuple[list[ResumenSector], list[CamaDisponible]]:
    """Invoca `pr_camas_disponibles(cursor_cantidad, cursor_detalle)`."""
    with cnx.cursor() as cur, cnx.cursor() as c_cant, cnx.cursor() as c_det:
        cur.callproc("pr_camas_disponibles", [c_cant, c_det])
        resumen = [
            ResumenSector(nombre_sector=str(f[0]), camas_disponibles=int(f[1]))
            for f in c_cant.fetchall()
        ]
        detalle = [
            CamaDisponible(
                nombre_sector=str(f[0]),
                nro_habitacion=int(f[1]),
                piso=int(f[2]),
                orientacion=str(f[3]),
                nro_cama=int(f[4]),
            )
            for f in c_det.fetchall()
        ]
        return resumen, detalle


def ejecutar_pr_comentarios_internacion(
    cnx: Any,
    id_internacion: int,
    dni_paciente: str,
) -> list[ComentarioVisita]:
    """Invoca `pr_comentarios_internacion(p_id_internacion, p_dni_paciente, cursor)`."""
    with cnx.cursor() as cur, cnx.cursor() as c_com:
        cur.callproc("pr_comentarios_internacion", [id_internacion, dni_paciente, c_com])
        return [
            ComentarioVisita(
                fecha_recorrido=f[0],
                turno_ronda=int(f[1]),
                apellido_medico=str(f[2]),
                nombre_medico=str(f[3]),
                texto_comentario=str(f[4]),
            )
            for f in c_com.fetchall()
        ]
