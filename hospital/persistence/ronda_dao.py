"""DAO de las tablas RONDA, ES_VISITADA, RECORRIDO y COMENTARIO."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hospital.models.entities import Recorrido, Ronda


def listar_rondas(cur: Any) -> list[Ronda]:
    cur.execute(
        """
        SELECT id_ronda, dia_ronda, turno_ronda
          FROM ronda
         ORDER BY id_ronda
        """
    )
    rondas = [
        Ronda(id_ronda=int(f[0]), dia_ronda=str(f[1]), turno_ronda=int(f[2]))
        for f in cur.fetchall()
    ]
    if not rondas:
        return []

    cur.execute(
        """
        SELECT id_ronda, nro_habitacion
          FROM es_visitada
         ORDER BY id_ronda, nro_habitacion
        """
    )
    habs_por_ronda: dict[int, list[int]] = {}
    for id_r, nro_h in cur.fetchall():
        habs_por_ronda.setdefault(int(id_r), []).append(int(nro_h))

    for ronda in rondas:
        ronda.habitaciones = habs_por_ronda.get(ronda.id_ronda, [])
    return rondas


def obtener_ronda(cur: Any, id_ronda: int) -> Ronda | None:
    cur.execute(
        "SELECT id_ronda, dia_ronda, turno_ronda FROM ronda WHERE id_ronda = :r",
        r=id_ronda,
    )
    f = cur.fetchone()
    if f is None:
        return None
    cur.execute(
        "SELECT nro_habitacion FROM es_visitada WHERE id_ronda = :r ORDER BY nro_habitacion",
        r=id_ronda,
    )
    habs = [int(row[0]) for row in cur.fetchall()]
    return Ronda(
        id_ronda=int(f[0]),
        dia_ronda=str(f[1]),
        turno_ronda=int(f[2]),
        habitaciones=habs,
    )


def contar_camas_en_ronda(cur: Any, id_ronda: int) -> int:
    """Devuelve la suma de camas de todas las habitaciones asignadas a la ronda."""
    cur.execute(
        """
        SELECT COUNT(*)
          FROM es_visitada ev
          JOIN cama c ON c.nro_habitacion = ev.nro_habitacion
         WHERE ev.id_ronda = :r
        """,
        r=id_ronda,
    )
    return int(cur.fetchone()[0])


def listar_recorridos(
    cur: Any,
    id_ronda: int | None = None,
    matricula_medico: int | None = None,
) -> list[Recorrido]:
    sql = """
        SELECT rec.id_recorrido,
               rec.id_ronda,
               rd.dia_ronda,
               rd.turno_ronda,
               rec.matricula_medico,
               pe.apellido || ', ' || pe.nombre AS medico,
               rec.fecha_recorrido,
               (SELECT COUNT(*) FROM comentario c WHERE c.id_recorrido = rec.id_recorrido) AS cant_com
          FROM recorrido rec
          JOIN ronda rd ON rd.id_ronda = rec.id_ronda
          JOIN medico m ON m.matricula_medico = rec.matricula_medico
          JOIN persona pe ON pe.dni = m.dni
    """
    condiciones: list[str] = []
    params: dict[str, Any] = {}
    if id_ronda is not None:
        condiciones.append("rec.id_ronda = :r")
        params["r"] = id_ronda
    if matricula_medico is not None:
        condiciones.append("rec.matricula_medico = :m")
        params["m"] = matricula_medico
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY rec.fecha_recorrido DESC, rec.id_recorrido DESC"

    cur.execute(sql, params)
    return [
        Recorrido(
            id_recorrido=int(f[0]),
            id_ronda=int(f[1]),
            dia_ronda=str(f[2]),
            turno_ronda=int(f[3]),
            matricula_medico=int(f[4]),
            medico=str(f[5]),
            fecha_recorrido=f[6],
            cantidad_comentarios=int(f[7]),
        )
        for f in cur.fetchall()
    ]


def obtener_recorrido(cur: Any, id_recorrido: int) -> Recorrido | None:
    cur.execute(
        """
        SELECT rec.id_recorrido,
               rec.id_ronda,
               rd.dia_ronda,
               rd.turno_ronda,
               rec.matricula_medico,
               pe.apellido || ', ' || pe.nombre AS medico,
               rec.fecha_recorrido,
               (SELECT COUNT(*) FROM comentario c WHERE c.id_recorrido = rec.id_recorrido) AS cant_com
          FROM recorrido rec
          JOIN ronda rd ON rd.id_ronda = rec.id_ronda
          JOIN medico m ON m.matricula_medico = rec.matricula_medico
          JOIN persona pe ON pe.dni = m.dni
         WHERE rec.id_recorrido = :id
        """,
        id=id_recorrido,
    )
    f = cur.fetchone()
    if f is None:
        return None
    return Recorrido(
        id_recorrido=int(f[0]),
        id_ronda=int(f[1]),
        dia_ronda=str(f[2]),
        turno_ronda=int(f[3]),
        matricula_medico=int(f[4]),
        medico=str(f[5]),
        fecha_recorrido=f[6],
        cantidad_comentarios=int(f[7]),
    )


def bloquear_recorrido(cur: Any, id_recorrido: int) -> bool:
    """Bloquea el recorrido con FOR UPDATE WAIT 5 para serializar la carga de comentarios."""
    cur.execute(
        "SELECT 1 FROM recorrido WHERE id_recorrido = :id FOR UPDATE WAIT 5",
        id=id_recorrido,
    )
    return cur.fetchone() is not None


def contar_comentarios_recorrido(cur: Any, id_recorrido: int) -> int:
    cur.execute(
        "SELECT COUNT(*) FROM comentario WHERE id_recorrido = :rec",
        rec=id_recorrido,
    )
    return int(cur.fetchone()[0])


def insertar_recorrido(
    cur: Any,
    id_ronda: int,
    matricula_medico: int,
    fecha_recorrido: datetime,
) -> int:
    nuevo_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido)
        VALUES (:r, :m, :f)
        RETURNING id_recorrido INTO :nuevo_id
        """,
        r=id_ronda,
        m=matricula_medico,
        f=fecha_recorrido,
        nuevo_id=nuevo_id,
    )
    val = nuevo_id.getvalue()
    return int(val[0] if isinstance(val, list) else val)


def insertar_comentario(
    cur: Any,
    id_internacion: int,
    id_recorrido: int,
    texto_comentario: str,
) -> int:
    nuevo_id = cur.var(int)
    cur.execute(
        """
        INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
        VALUES (:i, :r, :txt)
        RETURNING id_comentario INTO :nuevo_id
        """,
        i=id_internacion,
        r=id_recorrido,
        txt=texto_comentario,
        nuevo_id=nuevo_id,
    )
    val = nuevo_id.getvalue()
    return int(val[0] if isinstance(val, list) else val)


def listar_comentarios_de_recorrido(cur: Any, id_recorrido: int) -> list[tuple[int, int, str, str, str]]:
    """Lista los comentarios registrados en un recorrido: (id_com, id_int, dni, paciente, texto)."""
    cur.execute(
        """
        SELECT c.id_comentario,
               c.id_internacion,
               i.dni,
               pe.apellido || ', ' || pe.nombre AS paciente,
               c.texto_comentario
          FROM comentario c
          JOIN internacion i ON i.id_internacion = c.id_internacion
          JOIN persona pe ON pe.dni = i.dni
         WHERE c.id_recorrido = :rec
         ORDER BY c.id_comentario
        """,
        rec=id_recorrido,
    )
    return [
        (int(f[0]), int(f[1]), str(f[2]), str(f[3]), str(f[4]))
        for f in cur.fetchall()
    ]
