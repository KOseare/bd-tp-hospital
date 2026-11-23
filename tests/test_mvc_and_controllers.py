"""Pruebas de arquitectura MVC, traducción de errores, transacciones ACID, Rondas y UI Tkinter."""

from __future__ import annotations

import pathlib
import re
import tkinter as tk
from copy import deepcopy
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from hospital.config import OracleConfig
from hospital.controllers import AppControllers, calcular_intervalo
from hospital.models.entities import (
    AuditoriaGuardia,
    CamaDisponible,
    CamaEstado,
    EspecialidadMedico,
    Guardia,
    Internacion,
    Medico,
    OcupacionCama,
    Paciente,
    Recorrido,
    ResumenSector,
    Ronda,
    Vacacion,
)
from hospital.models.exceptions import (
    ErrorBaseDatos,
    ErrorConcurrencia,
    ErrorConexion,
    ErrorTrigger,
    ReglaError,
)
from hospital.persistence.connection import ConnectionManager, traducir_error_oracle
from hospital.views.main_window import MainWindow

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. Auditoría de arquitectura MVC + Capa de Persistencia y regresiones
# ---------------------------------------------------------------------------
class TestArquitecturaMVC:
    def test_vistas_no_importan_oracledb_ni_persistencia(self) -> None:
        views_dir = ROOT / "hospital" / "views"
        for py in views_dir.rglob("*.py"):
            txt = py.read_text(encoding="utf-8")
            assert "import oracledb" not in txt, f"{py.name} importa oracledb directamente"
            assert "hospital.persistence" not in txt, f"{py.name} accede directo a persistencia"

    def test_sin_emojis_ni_clave_hardcodeada(self) -> None:
        emoji_re = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
        targets = list((ROOT / "hospital").rglob("*.py")) + [ROOT / "app.py", ROOT / "pruebas.py"]
        for py in targets:
            txt = py.read_text(encoding="utf-8")
            assert not emoji_re.findall(txt), f"Se encontró emoji en {py.name}"
            assert "potentia" not in txt, f"Clave hardcodeada encontrada en {py.name}"

    def test_todos_los_for_update_usan_wait(self) -> None:
        pers_dir = ROOT / "hospital" / "persistence"
        for py in pers_dir.rglob("*.py"):
            txt = py.read_text(encoding="utf-8")
            for m in re.finditer(r"FOR\s+UPDATE([^\n\"']*)", txt, re.IGNORECASE):
                assert "WAIT" in m.group(1).upper(), (
                    f"{py.name} tiene FOR UPDATE sin WAIT: {m.group(0)!r}"
                )

    def test_oracle_config_oculta_clave_en_repr(self) -> None:
        cfg = OracleConfig(usuario="hospital", clave="secreta", dsn="localhost:1521/FREEPDB1")
        assert "secreta" not in repr(cfg)
        assert cfg.esta_configurado is True


# ---------------------------------------------------------------------------
# 2. Traducción de errores Oracle
# ---------------------------------------------------------------------------
class _FakeOraErr:
    def __init__(self, code: int | None, message: str) -> None:
        self.code = code
        self.message = message


class _FakeOraExc(Exception):
    def __init__(self, code: int | None, message: str) -> None:
        super().__init__(_FakeOraErr(code, message))


class TestTraductorErroresOracle:
    def test_traduce_triggers_ora_20xxx(self) -> None:
        exc = traducir_error_oracle(
            _FakeOraExc(20001, "ORA-20001: Un medico no puede ser su propio medico principal.\nORA-06512: ...")
        )
        assert isinstance(exc, ErrorTrigger)
        assert exc.codigo == 20001
        assert "propio medico principal" in str(exc)

    def test_traduce_concurrencia_ora_30006_y_00054(self) -> None:
        for code in (54, 30006):
            exc = traducir_error_oracle(_FakeOraExc(code, f"ORA-{code:05d}: resource busy"))
            assert isinstance(exc, ErrorConcurrencia)
            assert exc.codigo_ora == code

    def test_traduce_unique_sin_colision_prefijo_pk_guardia(self) -> None:
        exc_m = traducir_error_oracle(
            _FakeOraExc(1, "ORA-00001: unique constraint (HOSPITAL.PK_GUARDIA_MANANA) violated")
        )
        assert isinstance(exc_m, ReglaError)
        assert "turno mañana" in str(exc_m).lower()

        exc_g = traducir_error_oracle(
            _FakeOraExc(1, "ORA-00001: unique constraint (HOSPITAL.PK_GUARDIA) violated")
        )
        assert isinstance(exc_g, ReglaError)
        assert "identificador" in str(exc_g).lower()

    def test_traduce_checks_fks_y_conexion(self) -> None:
        ck = traducir_error_oracle(
            _FakeOraExc(2290, "ORA-02290: check constraint (HOSPITAL.CK_OCUPA_FECHAS) violated")
        )
        assert isinstance(ck, ReglaError)
        assert "liberación de cama" in str(ck)

        fk_p = traducir_error_oracle(
            _FakeOraExc(2291, "ORA-02291: integrity constraint (HOSPITAL.FK_OCUPA_CAMA) violated")
        )
        assert isinstance(fk_p, ReglaError)
        assert "cama indicada" in str(fk_p).lower()

        fk_c = traducir_error_oracle(
            _FakeOraExc(2292, "ORA-02292: integrity constraint (HOSPITAL.FK_DESEMPENA_POSEE) violated")
        )
        assert isinstance(fk_c, ReglaError)
        assert "guardias asignadas" in str(fk_c).lower()

        conn = traducir_error_oracle(_FakeOraExc(1017, "ORA-01017: invalid username/password"))
        assert isinstance(conn, ErrorConexion)

        gen = traducir_error_oracle(_FakeOraExc(942, "ORA-00942: table or view does not exist"))
        assert isinstance(gen, ErrorBaseDatos)


# ---------------------------------------------------------------------------
# 3. Doble transaccional en memoria para probar Controladores (COMMIT / ROLLBACK)
# ---------------------------------------------------------------------------
class _FakeVar:
    def __init__(self) -> None:
        self._val: list[int] = []

    def setvalue(self, v: int) -> None:
        self._val = [v]

    def getvalue(self) -> list[int]:
        return self._val


class _FakeStateDB:
    """Simula tablas Oracle clave con COMMIT / ROLLBACK real para tests de controladores."""

    def __init__(self) -> None:
        self.data = {
            "persona": {
                "20111111": ("Laura", "Gomez"),
                "24444444": ("Sergio", "Diaz"),
                "30111111": ("Ana", "Lopez"),
                "30333333": ("Sofia", "Martinez"),
            },
            "paciente": {
                "24444444": (date(1975, 3, 2), "M"),
                "30111111": (date(1990, 5, 14), "F"),
                "30333333": (date(1978, 7, 23), "F"),
            },
            "medico": {
                1001: ("20111111", "27201111115", datetime(2015, 3, 1), 8, None),
                1004: ("24444444", "20244444447", datetime(2012, 6, 20), 2, None),
            },
            "especialidad": {"Clinica Medica", "Cardiologia", "Terapia Intensiva"},
            "posee": {
                (1001, "Clinica Medica"): "S",
                (1001, "Cardiologia"): "N",
                (1004, "Clinica Medica"): "S",
                (1004, "Terapia Intensiva"): "S",
            },
            "cama": {(101, 1): "Maternidad", (101, 2): "Maternidad", (102, 1): "Maternidad"},
            "internacion": {
                1: (datetime(2026, 10, 20, 10, 0), None, 1001, "30111111"),
            },
            "ocupa": [
                [1, datetime(2026, 10, 20, 10, 0), 101, 1, None],
            ],
            "ronda": {
                1: ("MARTES", 3, [101, 102]),
            },
            "recorrido": {
                1: (1, 1001, datetime(2026, 10, 20, 16, 0)),
            },
            "comentario": [
                (1, 1, 1, "Evolucion favorable."),
            ],
            "guardia": {},
            "turnos": [],
            "desempena": [],
        }
        self.commits = 0
        self.rollbacks = 0
        self.locks_acquired: list[str] = []
        self.fail_on_pattern: tuple[str, Exception] | None = None
        self.next_int_id = 2
        self.next_rec_id = 2
        self.next_com_id = 2
        self.next_gua_id = 1

    def make_connection(self) -> _FakeConn:
        return _FakeConn(self)


class _FakeConn:
    def __init__(self, store: _FakeStateDB) -> None:
        self._store = store
        self.autocommit = False
        self._work = deepcopy(store.data)

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        self._store.data = deepcopy(self._work)
        self._store.commits += 1

    def rollback(self) -> None:
        self._work = deepcopy(self._store.data)
        self._store.rollbacks += 1

    def close(self) -> None:
        pass

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *_a: object) -> None:
        self.close()


class _FakeCursor:
    def __init__(self, conn: _FakeConn) -> None:
        self.connection = conn
        self._rows: list[tuple] = []
        self.rowcount = 0

    def var(self, _typ: object) -> _FakeVar:
        return _FakeVar()

    def setinputsizes(self, **_kw: object) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_a: object) -> None:
        self.close()

    def fetchone(self) -> tuple | None:
        return self._rows.pop(0) if self._rows else None

    def fetchall(self) -> list[tuple]:
        res = list(self._rows)
        self._rows.clear()
        return res

    def execute(self, sql: str, params: dict | None = None, **kw: object) -> None:
        p = dict(params or {})
        p.update(kw)
        s = " ".join(sql.split())
        su = s.upper()
        w = self.connection._work
        store = self.connection._store

        if store.fail_on_pattern is not None:
            pat, exc = store.fail_on_pattern
            if pat.upper() in su:
                raise exc

        self._rows = []
        self.rowcount = 0

        # PERSONA
        if su.startswith("SELECT COUNT(*) FROM PERSONA WHERE DNI"):
            self._rows = [(1 if p["dni"] in w["persona"] else 0,)]
        elif su.startswith("INSERT INTO PERSONA"):
            w["persona"][p["dni"]] = (p["nom"], p["ape"])
            self.rowcount = 1
        elif su.startswith("UPDATE PERSONA SET"):
            if p["dni"] in w["persona"]:
                w["persona"][p["dni"]] = (p["nom"], p["ape"])
                self.rowcount = 1
        elif su.startswith("DELETE FROM PERSONA WHERE DNI"):
            self.rowcount = 1 if w["persona"].pop(p["dni"], None) is not None else 0

        # PACIENTE
        elif su.startswith("SELECT COUNT(*) FROM PACIENTE WHERE DNI"):
            self._rows = [(1 if p["dni"] in w["paciente"] else 0,)]
        elif su.startswith("SELECT 1 FROM PACIENTE WHERE DNI"):
            self._rows = [(1,)] if p["dni"] in w["paciente"] else []
        elif su.startswith("INSERT INTO PACIENTE"):
            w["paciente"][p["dni"]] = (p["nac"], p["sexo"])
            self.rowcount = 1
        elif su.startswith("UPDATE PACIENTE"):
            if p["dni"] in w["paciente"]:
                w["paciente"][p["dni"]] = (p["nac"], p["sexo"])
                self.rowcount = 1
        elif su.startswith("DELETE FROM PACIENTE WHERE DNI"):
            self.rowcount = 1 if w["paciente"].pop(p["dni"], None) is not None else 0
        elif "FROM PACIENTE P JOIN PERSONA PE" in su and "WHERE P.DNI" in su:
            dni = p["dni"]
            if dni in w["paciente"]:
                nom, ape = w["persona"][dni]
                nac, sexo = w["paciente"][dni]
                self._rows = [(dni, ape, nom, nac, sexo)]

        # MEDICO / ESPECIALIDAD / POSEE
        elif su.startswith("SELECT COUNT(*) FROM MEDICO WHERE MATRICULA_MEDICO"):
            self._rows = [(1 if p["m"] in w["medico"] else 0,)]
        elif su.startswith("SELECT COUNT(*) FROM MEDICO WHERE DNI"):
            self._rows = [(sum(1 for v in w["medico"].values() if v[0] == p["dni"]),)]
        elif su.startswith("SELECT COUNT(*) FROM MEDICO WHERE CUIL_CUIT"):
            excl = p.get("m")
            cnt = sum(1 for m, v in w["medico"].items() if v[1] == p["c"] and m != excl)
            self._rows = [(cnt,)]
        elif su.startswith("SELECT 1 FROM MEDICO WHERE MATRICULA_MEDICO"):
            store.locks_acquired.append(f"MEDICO:{p['m']}")
            self._rows = [(1,)] if p["m"] in w["medico"] else []
        elif su.startswith("SELECT DNI FROM MEDICO WHERE MATRICULA_MEDICO"):
            v = w["medico"].get(p["m"])
            self._rows = [(v[0],)] if v else []
        elif su.startswith("SELECT CANTIDAD_GUARDIAS FROM MEDICO WHERE MATRICULA_MEDICO"):
            v = w["medico"].get(p["m"])
            self._rows = [(v[3],)] if v else []
        elif su.startswith("SELECT HACE_GUARDIA FROM POSEE"):
            key = (p.get("m", p.get("mat")), p.get("e", p.get("esp")))
            self._rows = [(w["posee"][key],)] if key in w["posee"] else []
        elif su.startswith("SELECT COUNT(*) FROM VACACION"):
            self._rows = [(0,)]
        elif su.startswith("INSERT INTO MEDICO"):
            w["medico"][p["mat"]] = (p["dni"], p["cuil"], p["ing"], p["maxg"], p["foto"])
            self.rowcount = 1
        elif su.startswith("UPDATE MEDICO"):
            mat = p["mat"]
            if mat in w["medico"]:
                dni, _, _, _, old_foto = w["medico"][mat]
                foto = p["foto"] if "foto" in p else old_foto
                w["medico"][mat] = (dni, p["cuil"], p["ing"], p["maxg"], foto)
                self.rowcount = 1
        elif "FROM MEDICO M JOIN PERSONA PE" in su and "WHERE M.MATRICULA_MEDICO" in su:
            mat = p["mat"]
            if mat in w["medico"]:
                dni, cuil, ing, maxg, foto = w["medico"][mat]
                nom, ape = w["persona"][dni]
                self._rows = [(mat, dni, ape, nom, cuil, ing, maxg, foto)]
        elif su.startswith("SELECT NOMBRE_ESPECIALIDAD FROM ESPECIALIDAD"):
            self._rows = [(e,) for e in sorted(w["especialidad"])]
        elif su.startswith("SELECT COUNT(*) FROM ESPECIALIDAD WHERE"):
            self._rows = [(1 if p["e"] in w["especialidad"] else 0,)]
        elif su.startswith("SELECT 1 FROM ESPECIALIDAD WHERE"):
            store.locks_acquired.append(f"ESPECIALIDAD:{p['e']}")
            self._rows = [(1,)] if p["e"] in w["especialidad"] else []
        elif su.startswith("INSERT INTO ESPECIALIDAD"):
            w["especialidad"].add(p["e"])
        elif su.startswith("SELECT NOMBRE_ESPECIALIDAD, HACE_GUARDIA FROM POSEE"):
            mat = p["mat"]
            self._rows = [(e, hg) for (m, e), hg in sorted(w["posee"].items()) if m == mat]
        elif su.startswith("SELECT COUNT(*) FROM POSEE WHERE"):
            self._rows = [(1 if (p["m"], p["e"]) in w["posee"] else 0,)]
        elif su.startswith("SELECT HACE_GUARDIA FROM POSEE"):
            key = (p["mat"], p["esp"])
            self._rows = [(w["posee"][key],)] if key in w["posee"] else []
        elif su.startswith("INSERT INTO POSEE"):
            w["posee"][(p["mat"], p["esp"])] = p["hg"]
        elif su.startswith("UPDATE POSEE"):
            w["posee"][(p["mat"], p["esp"])] = p["hg"]
        elif su.startswith("DELETE FROM POSEE"):
            w["posee"].pop((p["mat"], p["esp"]), None)

        # CAMA
        elif su.startswith("SELECT 1 FROM CAMA"):
            self._rows = [(1,)] if (p["h"], p["c"]) in w["cama"] else []

        # INTERNACION / OCUPA
        elif su.startswith("SELECT COUNT(*) FROM INTERNACION WHERE DNI = :DNI AND :INI"):
            cnt = 0
            for v in w["internacion"].values():
                fin = v[1] or datetime(9999, 12, 31, 23, 59, 59)
                if v[3] == p["dni"] and p["ini"] <= fin and p["fin"] >= v[0]:
                    cnt += 1
            self._rows = [(cnt,)]
        elif su.startswith("SELECT DNI FROM INTERNACION WHERE ID_INTERNACION"):
            row = w["internacion"].get(p["i"])
            self._rows = [(row[3],)] if row else []
        elif su.startswith("SELECT COUNT(*) FROM OCUPA WHERE NRO_HABITACION"):
            cnt = 0
            for oc in w["ocupa"]:
                if oc[2] == p["h"] and oc[3] == p["c"]:
                    if oc[0] == p["i"] and oc[1] == p["ini"]:
                        continue
                    fin = oc[4] or datetime(9999, 12, 31, 23, 59, 59)
                    if fin > p["ini"]:
                        cnt += 1
            self._rows = [(cnt,)]
        elif su.startswith("SELECT COUNT(*) FROM DESEMPENA D JOIN GUARDIA G ON G.ID_GUARDIA = D.ID_GUARDIA WHERE D.MATRICULA_MEDICO = :M AND EXTRACT"):
            cnt = 0
            for mat, _esp, id_g in w["desempena"]:
                g_ini = w["guardia"][id_g][0]
                if mat == p["m"] and g_ini.year == p["anio"] and g_ini.month == p["mes"]:
                    cnt += 1
            self._rows = [(cnt,)]
        elif su.startswith("SELECT COUNT(*) FROM INTERNACION WHERE DNI = :DNI AND FECHA_TERMINACION"):
            cnt = sum(1 for v in w["internacion"].values() if v[3] == p["dni"] and v[1] is None)
            self._rows = [(cnt,)]
        elif su.startswith("SELECT COUNT(*) FROM INTERNACION WHERE DNI = :DNI"):
            cnt = sum(1 for v in w["internacion"].values() if v[3] == p["dni"])
            self._rows = [(cnt,)]
        elif su.startswith("SELECT FECHA_INICIO_INTERNACION, FECHA_TERMINACION_INTERNACION FROM INTERNACION"):
            store.locks_acquired.append(f"INTERNACION:{p['i']}")
            row = w["internacion"].get(p["i"])
            self._rows = [(row[0], row[1])] if row else []
        elif su.startswith("INSERT INTO INTERNACION"):
            nid = store.next_int_id
            store.next_int_id += 1
            w["internacion"][nid] = (p["ini"], None, p["mat"], p["dni"])
            p["nuevo_id"].setvalue(nid)
        elif su.startswith("UPDATE INTERNACION SET FECHA_TERMINACION_INTERNACION"):
            row = w["internacion"][p["i"]]
            w["internacion"][p["i"]] = (row[0], p["fin"], row[2], row[3])
            self.rowcount = 1
        elif su.startswith("SELECT NRO_HABITACION, NRO_CAMA, FECHA_ASIGNACION_CAMA FROM OCUPA"):
            for oc in w["ocupa"]:
                if oc[0] == p["i"] and oc[4] is None:
                    self._rows = [(oc[2], oc[3], oc[1])]
                    break
        elif su.startswith("INSERT INTO OCUPA"):
            w["ocupa"].append([p["i"], p["asig"], p["h"], p["c"], None])
        elif su.startswith("UPDATE OCUPA SET FECHA_TERMINACION_CAMA"):
            for oc in w["ocupa"]:
                if oc[0] == p["i"] and oc[4] is None:
                    oc[4] = p["fin"]
                    self.rowcount += 1

        # RONDA / RECORRIDO / COMENTARIO
        elif su.startswith("SELECT ID_RONDA, DIA_RONDA, TURNO_RONDA FROM RONDA WHERE ID_RONDA"):
            r = w["ronda"].get(p["r"])
            self._rows = [(p["r"], r[0], r[1])] if r else []
        elif su.startswith("SELECT NRO_HABITACION FROM ES_VISITADA WHERE ID_RONDA"):
            r = w["ronda"].get(p["r"])
            self._rows = [(h,) for h in (r[2] if r else [])]
        elif su.startswith("SELECT COUNT(*) FROM ES_VISITADA EV JOIN CAMA C"):
            r = w["ronda"].get(p["r"])
            habs = set(r[2]) if r else set()
            cnt = sum(1 for (h, _c) in w["cama"] if h in habs)
            self._rows = [(cnt,)]
        elif su.startswith("INSERT INTO RECORRIDO"):
            nid = store.next_rec_id
            store.next_rec_id += 1
            w["recorrido"][nid] = (p["r"], p["m"], p["f"])
            p["nuevo_id"].setvalue(nid)
        elif su.startswith("SELECT 1 FROM RECORRIDO WHERE ID_RECORRIDO"):
            store.locks_acquired.append(f"RECORRIDO:{p['id']}")
            self._rows = [(1,)] if p["id"] in w["recorrido"] else []
        elif "FROM RECORRIDO REC" in su and "WHERE REC.ID_RECORRIDO" in su:
            rec = w["recorrido"].get(p["id"])
            if rec:
                id_r, mat, fecha = rec
                dia, turno, _ = w["ronda"][id_r]
                dni_m = w["medico"][mat][0]
                nom, ape = w["persona"][dni_m]
                cant = sum(1 for c in w["comentario"] if c[2] == p["id"])
                self._rows = [(p["id"], id_r, dia, turno, mat, f"{ape}, {nom}", fecha, cant)]
        elif su.startswith("SELECT COUNT(*) FROM COMENTARIO WHERE ID_RECORRIDO"):
            self._rows = [(sum(1 for c in w["comentario"] if c[2] == p["rec"]),)]
        elif su.startswith("INSERT INTO COMENTARIO"):
            nid = store.next_com_id
            store.next_com_id += 1
            w["comentario"].append((nid, p["i"], p["r"], p["txt"]))
            p["nuevo_id"].setvalue(nid)

        # GUARDIA / DESEMPENA
        elif "FROM DESEMPENA D JOIN GUARDIA G" in su and "WHERE D.MATRICULA_MEDICO" in su:
            cnt = 0
            for mat, _esp, id_g in w["desempena"]:
                g_ini, g_fin = w["guardia"][id_g]
                if mat == p["m"] and g_ini < p["fin"] and g_fin > p["ini"]:
                    cnt += 1
            self._rows = [(cnt,)]
        elif "FROM DESEMPENA D JOIN GUARDIA G" in su and "WHERE D.NOMBRE_ESPECIALIDAD" in su:
            cnt = 0
            for _mat, esp, id_g in w["desempena"]:
                g_ini, g_fin = w["guardia"][id_g]
                if esp == p["e"] and g_ini < p["fin"] and g_fin > p["ini"]:
                    cnt += 1
            self._rows = [(cnt,)]
        elif su.startswith("INSERT INTO GUARDIA ("):
            nid = store.next_gua_id
            store.next_gua_id += 1
            w["guardia"][nid] = (p["ini"], p["fin"])
            p["nuevo_id"].setvalue(nid)
        elif su.startswith("INSERT INTO GUARDIA_TURNO_"):
            w["turnos"].append((su.split()[2], p["g"]))
        elif su.startswith("INSERT INTO DESEMPENA"):
            w["desempena"].append((p["m"], p["e"], p["g"]))
        else:
            raise AssertionError(f"SQL no soportado en FakeCursor: {s}")


@pytest.fixture
def fake_env():
    store = _FakeStateDB()
    cfg = OracleConfig(usuario="hospital", clave="ok", dsn="localhost:1521/FREEPDB1")
    db = ConnectionManager(cfg, connection_factory=store.make_connection)
    ctrls = AppControllers.desde_connection_manager(db)
    return store, ctrls


class TestControladoresYTransacciones:
    def test_paciente_crud_completo_y_medico_paciente(self, fake_env) -> None:
        store, ctrls = fake_env

        # Fecha futura rechazada (bug fix)
        with pytest.raises(ReglaError, match="futura"):
            ctrls.pacientes.alta("40111222", "Juan", "Nuevo", date.today() + timedelta(days=1), "M")

        # Alta normal
        creado = ctrls.pacientes.alta("40111222", "Juan", "Nuevo", date(1995, 4, 10), "M")
        assert creado.dni == "40111222"
        assert "40111222" in store.data["persona"]

        # Editar atómico
        editado = ctrls.pacientes.editar("40111222", "Juan Carlos", "Nuevo", date(1995, 4, 10), "M")
        assert editado.nombre == "Juan Carlos"
        assert store.data["persona"]["40111222"] == ("Juan Carlos", "Nuevo")

        # Eliminar paciente sin internaciones borra también PERSONA
        ctrls.pacientes.eliminar("40111222")
        assert "40111222" not in store.data["paciente"]
        assert "40111111" not in store.data["persona"]
        assert "40111222" not in store.data["persona"]

        # Eliminar paciente con internaciones rechazado
        with pytest.raises(ReglaError, match="internaciones registradas"):
            ctrls.pacientes.eliminar("30111111")

        # Eliminar paciente que también es médico conserva PERSONA
        ctrls.pacientes.eliminar("24444444")
        assert "24444444" not in store.data["paciente"]
        assert "24444444" in store.data["persona"]

    def test_paciente_rollback_si_falla_insert_paciente(self, fake_env) -> None:
        store, ctrls = fake_env
        store.fail_on_pattern = ("INSERT INTO PACIENTE", RuntimeError("fallo simulado"))

        with pytest.raises(RuntimeError):
            ctrls.pacientes.alta("40999888", "Test", "Rollback", date(1990, 1, 1), "F")

        assert "40999888" not in store.data["persona"]
        assert "40999888" not in store.data["paciente"]
        assert store.rollbacks == 1

    def test_medico_valida_matricula_positiva_y_bloquea_especialidad_no_confirmada(self, fake_env) -> None:
        store, ctrls = fake_env

        with pytest.raises(ReglaError, match="positivo"):
            ctrls.medicos.alta(0, "35111222", "Ana", "Med", "27351112221", datetime(2024, 1, 1), 4, None, [])

        with pytest.raises(ReglaError, match="no existe en el catálogo"):
            ctrls.medicos.alta(
                2001, "35111222", "Ana", "Med", "27351112221", datetime(2024, 1, 1), 4, None,
                [("CardilogiaTypo", True)], permitir_nuevas_especialidades=False,
            )
        assert "35111222" not in store.data["persona"]
        assert 2001 not in store.data["medico"]
        assert store.rollbacks == 1

        # Con confirmación explícita sí la crea junto con el médico
        creado = ctrls.medicos.alta(
            2001, "35111222", "Ana", "Med", "27351112221", datetime(2024, 1, 1), 4, b"img",
            [("Neurologia", True)], permitir_nuevas_especialidades=True,
        )
        assert creado.matricula == 2001
        assert "Neurologia" in store.data["especialidad"]

    def test_internacion_delega_en_triggers_oracle_y_hace_rollback(self, fake_env) -> None:
        store, ctrls = fake_env

        # Trigger trg_internacion_medico_paciente (ORA-20001) en BD -> propaga ErrorTrigger y hace ROLLBACK
        int_antes = len(store.data["internacion"])
        ocupa_antes = len(store.data["ocupa"])
        store.fail_on_pattern = (
            "INSERT INTO INTERNACION",
            ErrorTrigger(20001, "Un medico no puede ser su propio medico principal."),
        )
        with pytest.raises(ErrorTrigger) as exc_info:
            ctrls.internaciones.internar("24444444", 1004, 101, 2)
        assert exc_info.value.codigo == 20001
        assert len(store.data["internacion"]) == int_antes
        assert len(store.data["ocupa"]) == ocupa_antes

        # Trigger trg_validar_ocupa (ORA-20011) en OCUPA -> revierte la INTERNACION ya insertada
        store.fail_on_pattern = (
            "INSERT INTO OCUPA",
            ErrorTrigger(20011, "La cama ya se encuentra ocupada en ese intervalo."),
        )
        with pytest.raises(ErrorTrigger) as exc_info2:
            ctrls.internaciones.internar("30333333", 1001, 101, 1)
        assert exc_info2.value.codigo == 20011
        assert len(store.data["internacion"]) == int_antes
        assert len(store.data["ocupa"]) == ocupa_antes

    def test_internacion_cambiar_cama_y_alta_validan_fechas_y_hacen_rollback(self, fake_env) -> None:
        store, ctrls = fake_env

        # Traslado con fecha <= asignación actual rechazado antes de golpear CK_OCUPA_FECHAS
        with pytest.raises(ReglaError, match="posterior a la fecha de asignación"):
            ctrls.internaciones.cambiar_cama(1, 101, 2, fecha_cambio=datetime(2026, 10, 20, 10, 0))

        # ROLLBACK si falla el INSERT de la nueva cama tras cerrar la anterior
        store.fail_on_pattern = ("INSERT INTO OCUPA", RuntimeError("error en nueva cama"))
        with pytest.raises(RuntimeError):
            ctrls.internaciones.cambiar_cama(1, 101, 2, fecha_cambio=datetime(2026, 10, 21, 10, 0))
        # La cama 101-1 sigue abierta (fecha_terminacion == None)
        assert store.data["ocupa"][0][4] is None

        # Traslado exitoso
        store.fail_on_pattern = None
        ctrls.internaciones.cambiar_cama(1, 101, 2, fecha_cambio=datetime(2026, 10, 21, 10, 0))
        assert len(store.data["ocupa"]) == 2
        assert store.data["ocupa"][0][4] == datetime(2026, 10, 21, 10, 0)
        assert store.data["ocupa"][1][2:4] == [101, 2]

        # Alta con fecha <= última asignación rechazada
        with pytest.raises(ReglaError, match="última asignación"):
            ctrls.internaciones.dar_alta(1, fecha_alta=datetime(2026, 10, 21, 10, 0))

        # Alta exitosa
        ctrls.internaciones.dar_alta(1, fecha_alta=datetime(2026, 10, 22, 9, 0))
        assert store.data["internacion"][1][1] == datetime(2026, 10, 22, 9, 0)
        assert store.data["ocupa"][1][4] == datetime(2026, 10, 22, 9, 0)

    def test_guardia_rechaza_solapamiento_del_mismo_medico_en_otra_especialidad(self, fake_env) -> None:
        store, ctrls = fake_env

        # Turnos no contiguos rechazados
        with pytest.raises(ReglaError, match="contiguos"):
            calcular_intervalo(date(2026, 12, 1), [1, 3])

        # Médico 1004 toma Clinica Medica el 2026-12-01 Mañana
        store.locks_acquired.clear()
        id_g = ctrls.guardias.alta_guardia(1004, "Clinica Medica", date(2026, 12, 1), [1])
        assert id_g == 1
        # Verifica orden fijo de bloqueos: ESPECIALIDAD -> MEDICO
        assert store.locks_acquired == ["ESPECIALIDAD:Clinica Medica", "MEDICO:1004"]

        # El mismo médico 1004 intenta Terapia Intensiva el mismo día y horario -> RECHAZADO (bug fix #3)
        with pytest.raises(ReglaError, match="ya tiene otra guardia asignada"):
            ctrls.guardias.alta_guardia(1004, "Terapia Intensiva", date(2026, 12, 1), [1])

        # ROLLBACK si falla INSERT INTO DESEMPENA (no queda GUARDIA huérfana)
        store.fail_on_pattern = ("INSERT INTO DESEMPENA", ErrorTrigger(20003, "En vacaciones"))
        with pytest.raises(ErrorTrigger):
            ctrls.guardias.alta_guardia(1001, "Clinica Medica", date(2026, 12, 2), [1])
        assert len(store.data["guardia"]) == 1

    def test_rondas_recorridos_y_comentarios(self, fake_env) -> None:
        store, ctrls = fake_env

        # Ronda 1 es MARTES -> 2026-11-25 es MIERCOLES -> debe rechazar
        with pytest.raises(ReglaError, match="MARTES"):
            ctrls.rondas.registrar_recorrido(1, 1001, datetime(2026, 11, 25, 10, 0))

        # 2026-11-24 es MARTES -> acepta
        id_rec = ctrls.rondas.registrar_recorrido(1, 1001, datetime(2026, 11, 24, 10, 0))
        assert id_rec == 2

        # Comentario válido en recorrido 2 (ronda 1 tiene 3 camas: 101-1, 101-2, 102-1)
        store.locks_acquired.clear()
        id_c = ctrls.rondas.registrar_comentario(id_rec, 1, "Paciente estable.")
        assert id_c == 2
        # Verifica orden fijo de bloqueos: RECORRIDO -> INTERNACION
        assert store.locks_acquired == [f"RECORRIDO:{id_rec}", "INTERNACION:1"]

        # 2 comentarios más llegan al tope de 3 camas de la ronda -> 4to debe rechazarse
        ctrls.rondas.registrar_comentario(id_rec, 1, "Control 2.")
        ctrls.rondas.registrar_comentario(id_rec, 1, "Control 3.")
        with pytest.raises(ReglaError, match="máximo de 3"):
            ctrls.rondas.registrar_comentario(id_rec, 1, "Control 4 excedido.")

    def test_bateria_tiene_42_casos(self, fake_env) -> None:
        _, ctrls = fake_env
        casos = ctrls.pruebas.casos
        assert len(casos) == 42
        codigos = [c.codigo for c in casos]
        assert len(set(codigos)) == 42
        for esperado in ("1A", "10D", "11A", "11B", "11C", "12A", "12B", "12C", "13A", "13B", "13C", "14A", "14B", "14C", "15A"):
            assert esperado in codigos


# ---------------------------------------------------------------------------
# 4. Smoke test de la interfaz Tkinter (MainWindow + 9 pestañas + paginación)
# ---------------------------------------------------------------------------
class TestInterfazTkinter:
    def test_mainwindow_renderiza_todas_las_pestanas_y_pagina_tablas(self) -> None:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("No hay display Tkinter disponible en este entorno.")
        root.withdraw()

        try:
            ctrls = MagicMock()
            ctrls.reportes.camas_disponibles.return_value = (
                [ResumenSector("Maternidad", 2), ResumenSector("Pediatria", 0)],
                [CamaDisponible("Maternidad", 101, 1, "NORTE", i) for i in range(1, 18)],
            )
            ctrls.reportes.listar_sectores.return_value = ["Maternidad", "Pediatria"]
            ctrls.reportes.listar_todas_las_camas.return_value = [
                CamaEstado("Maternidad", 101, 1, "NORTE", i, ocupada=(i == 1))
                for i in range(1, 18)
            ]
            ctrls.reportes.listar_camas_libres.return_value = [(101, 2, "Maternidad")]
            ctrls.pacientes.listar.return_value = [
                Paciente("30111111", "Lopez", "Ana", date(1990, 5, 14), "F")
            ]
            ctrls.medicos.listar.return_value = [
                Medico(
                    1001, "20111111", "Gomez", "Laura", "27201111115",
                    datetime(2015, 3, 1), 8, None,
                    [EspecialidadMedico("Clinica Medica", True)],
                )
            ]
            ctrls.medicos.listar_especialidades.return_value = ["Clinica Medica"]
            ctrls.medicos.especialidades_de_guardia.return_value = ["Clinica Medica"]
            ctrls.medicos.listar_vacaciones.return_value = [
                Vacacion(1001, "Gomez, Laura", datetime(2026, 11, 20), datetime(2026, 12, 4))
            ]
            ctrls.internaciones.listar.return_value = [
                Internacion(1, "30111111", "Lopez, Ana", 1001, "Gomez, Laura", datetime(2026, 10, 20, 10, 0), None, 101, 1, "Maternidad")
            ]
            ctrls.internaciones.listar_ocupaciones.return_value = [
                OcupacionCama(1, 101, 1, "Maternidad", 1, "NORTE", datetime(2026, 10, 20, 10, 0), None)
            ]
            ctrls.rondas.listar_rondas.return_value = [Ronda(1, "MARTES", 3, [101, 102])]
            ctrls.rondas.listar_recorridos.return_value = [
                Recorrido(1, 1, "MARTES", 3, 1001, "Gomez, Laura", datetime(2026, 10, 20, 16, 0), 1)
            ]
            ctrls.rondas.listar_comentarios_de_recorrido.return_value = []
            ctrls.guardias.listar.return_value = [
                Guardia(1, 1001, "Gomez, Laura", "Clinica Medica", datetime(2026, 11, 2, 6, 0), datetime(2026, 11, 2, 14, 0), ["Mañana"])
            ]
            ctrls.guardias.listar_auditoria.return_value = [
                AuditoriaGuardia(1, datetime(2026, 11, 2, 6, 0), "HOSPITAL", "faust", "GUARDIA", "INSERT", "Guardia ID:1", "Alta")
            ]
            ctrls.pruebas.casos = []

            win = MainWindow(root, ctrls)
            assert win.nb.index("end") == 9

            # Verifica paginación en TablaPaginada (17 camas con page_size=15 -> 15 en pág 1, 2 en pág 2)
            assert len(win.v_camas.t_todas.tree.get_children()) == 15
            win.v_camas.t_todas._siguiente()
            assert len(win.v_camas.t_todas.tree.get_children()) == 2
            win.v_camas.t_todas._anterior()
            assert len(win.v_camas.t_todas.tree.get_children()) == 15

            # Bug fix #4: cb_esp_g se limpia si no hay médico seleccionado al refrescar
            win.v_guardias.cb_esp_g.set("Cardiologia")
            win.v_guardias.cb_medico_g.set("")
            win.v_guardias.refrescar()
            assert win.v_guardias.cb_esp_g.get() == ""
        finally:
            root.destroy()
