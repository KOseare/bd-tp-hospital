"""DAO de las tablas MEDICO, ESPECIALIDAD, POSEE y VACACION."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import oracledb

from hospital.models.entities import EspecialidadMedico, Medico, Vacacion


def _leer_blob(val: Any) -> bytes | None:
    if val is None:
        return None
    if hasattr(val, "read"):
        return bytes(val.read())
    return bytes(val)


def listar(cur: Any, filtro: str | None = None) -> list[Medico]:
    sql = """
        SELECT m.matricula_medico, m.dni, pe.apellido, pe.nombre,
               m.cuil_cuit, m.fecha_de_ingreso, m.cantidad_guardias, m.foto
          FROM medico m
          JOIN persona pe ON pe.dni = m.dni
    """
    params: dict[str, Any] = {}
    if filtro:
        sql += """
         WHERE TO_CHAR(m.matricula_medico) LIKE :q
            OR LOWER(m.dni) LIKE :q
            OR LOWER(pe.apellido) LIKE :q
            OR LOWER(pe.nombre) LIKE :q
            OR m.cuil_cuit LIKE :q
        """
        params["q"] = f"%{filtro.lower()}%"
    sql += " ORDER BY pe.apellido, pe.nombre"
    cur.execute(sql, params)
    return [
        Medico(
            matricula=int(f[0]),
            dni=str(f[1]),
            apellido=str(f[2]),
            nombre=str(f[3]),
            cuil_cuit=str(f[4]),
            fecha_ingreso=f[5],
            cantidad_guardias=int(f[6]),
            foto=_leer_blob(f[7]),
        )
        for f in cur.fetchall()
    ]


def obtener_por_matricula(cur: Any, matricula: int) -> Medico | None:
    cur.execute(
        """
        SELECT m.matricula_medico, m.dni, pe.apellido, pe.nombre,
               m.cuil_cuit, m.fecha_de_ingreso, m.cantidad_guardias, m.foto
          FROM medico m
          JOIN persona pe ON pe.dni = m.dni
         WHERE m.matricula_medico = :mat
        """,
        mat=matricula,
    )
    f = cur.fetchone()
    if f is None:
        return None
    return Medico(
        matricula=int(f[0]),
        dni=str(f[1]),
        apellido=str(f[2]),
        nombre=str(f[3]),
        cuil_cuit=str(f[4]),
        fecha_ingreso=f[5],
        cantidad_guardias=int(f[6]),
        foto=_leer_blob(f[7]),
    )


def existe_matricula(cur: Any, matricula: int) -> bool:
    cur.execute("SELECT COUNT(*) FROM medico WHERE matricula_medico = :m", m=matricula)
    return int(cur.fetchone()[0]) > 0


def existe_dni(cur: Any, dni: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM medico WHERE dni = :dni", dni=dni)
    return int(cur.fetchone()[0]) > 0


def existe_cuil(cur: Any, cuil: str, excluir_matricula: int | None = None) -> bool:
    if excluir_matricula is None:
        cur.execute("SELECT COUNT(*) FROM medico WHERE cuil_cuit = :c", c=cuil)
    else:
        cur.execute(
            "SELECT COUNT(*) FROM medico WHERE cuil_cuit = :c AND matricula_medico <> :m",
            c=cuil,
            m=excluir_matricula,
        )
    return int(cur.fetchone()[0]) > 0


def bloquear(cur: Any, matricula: int) -> bool:
    cur.execute(
        "SELECT 1 FROM medico WHERE matricula_medico = :m FOR UPDATE WAIT 5",
        m=matricula,
    )
    return cur.fetchone() is not None


def insertar(
    cur: Any,
    matricula: int,
    dni: str,
    cuil: str,
    fecha_ingreso: datetime,
    cantidad_guardias: int,
    foto: bytes | None,
) -> None:
    with cur.connection.cursor() as cur_med:
        if foto:
            cur_med.setinputsizes(foto=oracledb.DB_TYPE_BLOB)
        cur_med.execute(
            """
            INSERT INTO medico (matricula_medico, dni, foto, cuil_cuit,
                                fecha_de_ingreso, cantidad_guardias)
            VALUES (:mat, :dni, :foto, :cuil, :ing, :maxg)
            """,
            mat=matricula,
            dni=dni,
            foto=foto or None,
            cuil=cuil,
            ing=fecha_ingreso,
            maxg=cantidad_guardias,
        )


def actualizar(
    cur: Any,
    matricula: int,
    cuil: str,
    fecha_ingreso: datetime,
    cantidad_guardias: int,
    foto: bytes | None = None,
    actualizar_foto: bool = False,
) -> int:
    if actualizar_foto:
        with cur.connection.cursor() as cur_med:
            if foto:
                cur_med.setinputsizes(foto=oracledb.DB_TYPE_BLOB)
            cur_med.execute(
                """
                UPDATE medico
                   SET cuil_cuit = :cuil,
                       fecha_de_ingreso = :ing,
                       cantidad_guardias = :maxg,
                       foto = :foto
                 WHERE matricula_medico = :mat
                """,
                cuil=cuil,
                ing=fecha_ingreso,
                maxg=cantidad_guardias,
                foto=foto or None,
                mat=matricula,
            )
            return cur_med.rowcount

    cur.execute(
        """
        UPDATE medico
           SET cuil_cuit = :cuil,
               fecha_de_ingreso = :ing,
               cantidad_guardias = :maxg
         WHERE matricula_medico = :mat
        """,
        cuil=cuil,
        ing=fecha_ingreso,
        maxg=cantidad_guardias,
        mat=matricula,
    )
    return cur.rowcount


def listar_especialidades(cur: Any) -> list[str]:
    cur.execute("SELECT nombre_especialidad FROM especialidad ORDER BY 1")
    return [str(f[0]) for f in cur.fetchall()]


def existe_especialidad(cur: Any, nombre_especialidad: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM especialidad WHERE nombre_especialidad = :e",
        e=nombre_especialidad,
    )
    return int(cur.fetchone()[0]) > 0


def bloquear_especialidad(cur: Any, nombre_especialidad: str) -> bool:
    """Bloquea la especialidad con FOR UPDATE WAIT 5 para serializar asignaciones concurrentes."""
    cur.execute(
        "SELECT 1 FROM especialidad WHERE nombre_especialidad = :e FOR UPDATE WAIT 5",
        e=nombre_especialidad,
    )
    return cur.fetchone() is not None


def insertar_especialidad(cur: Any, nombre_especialidad: str) -> None:
    cur.execute(
        "INSERT INTO especialidad (nombre_especialidad) VALUES (:e)",
        e=nombre_especialidad,
    )


def listar_especialidades_medico(cur: Any, matricula: int) -> list[EspecialidadMedico]:
    cur.execute(
        """
        SELECT nombre_especialidad, hace_guardia
          FROM posee
         WHERE matricula_medico = :mat
         ORDER BY nombre_especialidad
        """,
        mat=matricula,
    )
    return [
        EspecialidadMedico(
            nombre_especialidad=str(f[0]),
            hace_guardia=(str(f[1]).upper() == "S"),
        )
        for f in cur.fetchall()
    ]


def especialidades_de_guardia(cur: Any, matricula: int) -> list[str]:
    cur.execute(
        """
        SELECT nombre_especialidad
          FROM posee
         WHERE matricula_medico = :mat AND hace_guardia = 'S'
         ORDER BY 1
        """,
        mat=matricula,
    )
    return [str(f[0]) for f in cur.fetchall()]


def posee_especialidad(cur: Any, matricula: int, nombre_especialidad: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) FROM posee
         WHERE matricula_medico = :m AND nombre_especialidad = :e
        """,
        m=matricula,
        e=nombre_especialidad,
    )
    return int(cur.fetchone()[0]) > 0


def upsert_posee(cur: Any, matricula: int, nombre_especialidad: str, hace_guardia: bool) -> None:
    hg = "S" if hace_guardia else "N"
    cur.execute(
        """
        SELECT hace_guardia FROM posee
         WHERE matricula_medico = :mat AND nombre_especialidad = :esp
        """,
        mat=matricula,
        esp=nombre_especialidad,
    )
    existente = cur.fetchone()
    if existente is None:
        cur.execute(
            """
            INSERT INTO posee (matricula_medico, nombre_especialidad, hace_guardia)
            VALUES (:mat, :esp, :hg)
            """,
            mat=matricula,
            esp=nombre_especialidad,
            hg=hg,
        )
    elif str(existente[0]).upper() != hg:
        cur.execute(
            """
            UPDATE posee
               SET hace_guardia = :hg
             WHERE matricula_medico = :mat AND nombre_especialidad = :esp
            """,
            hg=hg,
            mat=matricula,
            esp=nombre_especialidad,
        )


def eliminar_posee(cur: Any, matricula: int, nombre_especialidad: str) -> int:
    cur.execute(
        """
        DELETE FROM posee
         WHERE matricula_medico = :mat AND nombre_especialidad = :esp
        """,
        mat=matricula,
        esp=nombre_especialidad,
    )
    return cur.rowcount


def listar_vacaciones(cur: Any, matricula: int | None = None) -> list[Vacacion]:
    sql = """
        SELECT v.matricula_medico,
               pe.apellido || ', ' || pe.nombre,
               v.fecha_inicio_vac,
               v.fecha_fin_vac
          FROM vacacion v
          JOIN medico m ON m.matricula_medico = v.matricula_medico
          JOIN persona pe ON pe.dni = m.dni
    """
    params: dict[str, Any] = {}
    if matricula is not None:
        sql += " WHERE v.matricula_medico = :mat"
        params["mat"] = matricula
    sql += " ORDER BY v.fecha_inicio_vac DESC"
    cur.execute(sql, params)
    return [
        Vacacion(
            matricula_medico=int(f[0]),
            medico=str(f[1]),
            fecha_inicio=f[2],
            fecha_fin=f[3],
        )
        for f in cur.fetchall()
    ]
