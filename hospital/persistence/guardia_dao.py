"""DAO de las tablas GUARDIA, GUARDIA_TURNO_* y DESEMPENA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hospital.config import TABLAS_TURNO_GUARDIA
from hospital.models.entities import Guardia


def listar(
    cur: Any,
    matricula_medico: int | None = None,
    nombre_especialidad: str | None = None,
) -> list[Guardia]:
    sql = """
        SELECT g.id_guardia,
               d.matricula_medico,
               pe.apellido || ', ' || pe.nombre AS medico,
               d.nombre_especialidad,
               g.fecha_inicio_guardia,
               g.fecha_fin_guardia,
               CASE WHEN gm.id_guardia IS NOT NULL THEN 1 ELSE 0 END AS t_manana,
               CASE WHEN gt.id_guardia IS NOT NULL THEN 1 ELSE 0 END AS t_tarde,
               CASE WHEN gn.id_guardia IS NOT NULL THEN 1 ELSE 0 END AS t_noche
          FROM guardia g
          JOIN desempena d ON d.id_guardia = g.id_guardia
          JOIN medico m ON m.matricula_medico = d.matricula_medico
          JOIN persona pe ON pe.dni = m.dni
          LEFT JOIN guardia_turno_manana gm ON gm.id_guardia = g.id_guardia
          LEFT JOIN guardia_turno_tarde gt ON gt.id_guardia = g.id_guardia
          LEFT JOIN guardia_turno_noche gn ON gn.id_guardia = g.id_guardia
    """
    condiciones: list[str] = []
    params: dict[str, Any] = {}
    if matricula_medico is not None:
        condiciones.append("d.matricula_medico = :mat")
        params["mat"] = matricula_medico
    if nombre_especialidad:
        condiciones.append("d.nombre_especialidad = :esp")
        params["esp"] = nombre_especialidad
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY g.fecha_inicio_guardia DESC, g.id_guardia DESC FETCH FIRST 300 ROWS ONLY"

    cur.execute(sql, params)
    resultado: list[Guardia] = []
    for f in cur.fetchall():
        turnos: list[str] = []
        if f[6]:
            turnos.append("Mañana")
        if f[7]:
            turnos.append("Tarde")
        if f[8]:
            turnos.append("Noche")
        resultado.append(
            Guardia(
                id_guardia=int(f[0]),
                matricula_medico=int(f[1]),
                medico=str(f[2]),
                nombre_especialidad=str(f[3]),
                fecha_inicio=f[4],
                fecha_fin=f[5],
                turnos=turnos,
            )
        )
    return resultado


def existe_solapamiento_especialidad(
    cur: Any,
    especialidad: str,
    inicio: datetime,
    fin: datetime,
) -> bool:
    cur.execute(
        """
        SELECT COUNT(*)
          FROM desempena d
          JOIN guardia g ON g.id_guardia = d.id_guardia
         WHERE d.nombre_especialidad = :e
           AND g.fecha_inicio_guardia < :fin
           AND g.fecha_fin_guardia > :ini
        """,
        e=especialidad,
        ini=inicio,
        fin=fin,
    )
    return int(cur.fetchone()[0]) > 0


def existe_solapamiento_medico(
    cur: Any,
    matricula: int,
    inicio: datetime,
    fin: datetime,
) -> bool:
    """Verifica que el mismo médico no tenga otra guardia superpuesta en ninguna especialidad."""
    cur.execute(
        """
        SELECT COUNT(*)
          FROM desempena d
          JOIN guardia g ON g.id_guardia = d.id_guardia
         WHERE d.matricula_medico = :m
           AND g.fecha_inicio_guardia < :fin
           AND g.fecha_fin_guardia > :ini
        """,
        m=matricula,
        ini=inicio,
        fin=fin,
    )
    return int(cur.fetchone()[0]) > 0


def insertar_guardia(cur: Any, inicio: datetime, fin: datetime) -> int:
    nuevo_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
        VALUES (:ini, :fin)
        RETURNING id_guardia INTO :nuevo_id
        """,
        ini=inicio,
        fin=fin,
        nuevo_id=nuevo_id,
    )
    val = nuevo_id.getvalue()
    return int(val[0] if isinstance(val, list) else val)


def insertar_turno(cur: Any, id_guardia: int, turno: int) -> None:
    tabla = TABLAS_TURNO_GUARDIA.get(turno)
    if tabla is None:
        raise ValueError(f"Turno de guardia inválido: {turno}")
    cur.execute(f"INSERT INTO {tabla} (id_guardia) VALUES (:g)", g=id_guardia)


def insertar_desempena(cur: Any, matricula: int, especialidad: str, id_guardia: int) -> None:
    cur.execute(
        """
        INSERT INTO desempena (matricula_medico, nombre_especialidad, id_guardia)
        VALUES (:m, :e, :g)
        """,
        m=matricula,
        e=especialidad,
        g=id_guardia,
    )
