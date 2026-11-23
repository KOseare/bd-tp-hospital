"""DAO auxiliar para ejecutar la batería de pruebas siempre dentro de un ROLLBACK aislado."""

from __future__ import annotations

import atexit
from typing import Any, Callable

from hospital.persistence.connection import ConnectionManager


class _RollbackConnectionProxy:
    """Envuelve una conexión Oracle única para ejercitar controladores reales sin persistir cambios.

    - Cada adquisición de conexión dentro de la prueba marca un SAVEPOINT.
    - `commit()` mantiene los cambios visibles en la misma sesión sin confirmarlos en disco.
    - `rollback()` revierte únicamente hasta el SAVEPOINT de la transacción fallida.
    - `close()` es no-op; el `ROLLBACK` total y cierre reales los hace el bloque externo.
    """

    def __init__(self, cnx: Any) -> None:
        self._cnx = cnx
        self.autocommit = False

    def marcar_savepoint(self) -> None:
        with self._cnx.cursor() as cur:
            cur.execute("SAVEPOINT sp_bateria_tx")

    def cursor(self) -> Any:
        return self._cnx.cursor()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        with self._cnx.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT sp_bateria_tx")

    def close(self) -> None:
        pass


def ejecutar_en_rollback(db: ConnectionManager, fn: Callable[[Any, Any], Any]) -> Any:
    """Abre una conexión del pool, ejecuta `fn(cnx, cur)` y SIEMPRE revierte con ROLLBACK."""
    cnx = db.adquirir_conexion()
    cnx.autocommit = False
    cur = cnx.cursor()
    try:
        return fn(cnx, cur)
    finally:
        try:
            cnx.rollback()
        finally:
            try:
                cur.close()
            finally:
                cnx.close()


def ejecutar_controladores_en_rollback(
    db: ConnectionManager,
    fn: Callable[[ConnectionManager], Any],
) -> Any:
    """Ejecuta `fn(db_aislado)` sobre controladores reales revirtiendo todo con ROLLBACK final."""
    cnx = db.adquirir_conexion()
    cnx.autocommit = False
    proxy = _RollbackConnectionProxy(cnx)

    def _factory() -> _RollbackConnectionProxy:
        proxy.marcar_savepoint()
        return proxy

    db_aislado = ConnectionManager(db.config, connection_factory=_factory)
    try:
        return fn(db_aislado)
    finally:
        atexit.unregister(db_aislado.cerrar)
        try:
            cnx.rollback()
        finally:
            cnx.close()


def ejecutar_con_cama_bloqueada(
    db: ConnectionManager,
    nro_hab: int,
    nro_cama: int,
    fn: Callable[[], Any],
) -> Any:
    """Bloquea una cama en una conexión dedicada (`FOR UPDATE WAIT 5`) mientras ejecuta `fn()`."""
    cnx = db.adquirir_conexion()
    cnx.autocommit = False
    cur = cnx.cursor()
    try:
        cur.execute(
            """
            SELECT 1
              FROM cama
             WHERE nro_habitacion = :h
               AND nro_cama = :c
               FOR UPDATE WAIT 5
            """,
            h=int(nro_hab),
            c=int(nro_cama),
        )
        if cur.fetchone() is None:
            raise RuntimeError(f"La cama {nro_hab}-{nro_cama} no existe.")
        return fn()
    finally:
        try:
            cnx.rollback()
        finally:
            try:
                cur.close()
            finally:
                cnx.close()
