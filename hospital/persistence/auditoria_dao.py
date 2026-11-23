"""DAO de solo lectura sobre la tabla AUDITORIA_GUARDIAS."""

from __future__ import annotations

from typing import Any

from hospital.models.entities import AuditoriaGuardia


def listar(
    cur: Any,
    tabla_afectada: str | None = None,
    limite: int = 300,
) -> list[AuditoriaGuardia]:
    sql = """
        SELECT id_auditoria, fecha_hora, usuario_bd, usuario_so,
               tabla_afectada, operacion, clave_registro, detalle_cambio
          FROM auditoria_guardias
    """
    params: dict[str, Any] = {"lim": int(limite)}
    if tabla_afectada:
        sql += " WHERE tabla_afectada = :tab"
        params["tab"] = tabla_afectada
    sql += " ORDER BY id_auditoria DESC FETCH FIRST :lim ROWS ONLY"

    cur.execute(sql, params)
    return [
        AuditoriaGuardia(
            id_auditoria=int(f[0]),
            fecha_hora=f[1],
            usuario_bd=str(f[2]),
            usuario_so=str(f[3]) if f[3] is not None else None,
            tabla_afectada=str(f[4]),
            operacion=str(f[5]),
            clave_registro=str(f[6]),
            detalle_cambio=str(f[7]) if f[7] is not None else None,
        )
        for f in cur.fetchall()
    ]


def contar_total(cur: Any) -> int:
    cur.execute("SELECT COUNT(*) FROM auditoria_guardias")
    return int(cur.fetchone()[0])
