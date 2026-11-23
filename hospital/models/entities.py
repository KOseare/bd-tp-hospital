"""Modelos (dataclasses) mapeados 1:1 al esquema Oracle del hospital."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable


@dataclass
class Paciente:
    dni: str
    apellido: str
    nombre: str
    fecha_nacimiento: date
    sexo: str

    @property
    def nombre_completo(self) -> str:
        return f"{self.apellido}, {self.nombre}"


@dataclass
class EspecialidadMedico:
    nombre_especialidad: str
    hace_guardia: bool  # True = 'S', False = 'N'

    @property
    def hace_guardia_char(self) -> str:
        return "S" if self.hace_guardia else "N"


@dataclass
class Medico:
    matricula: int
    dni: str
    apellido: str
    nombre: str
    cuil_cuit: str
    fecha_ingreso: datetime
    cantidad_guardias: int
    foto: bytes | None = None
    especialidades: list[EspecialidadMedico] = field(default_factory=list)

    @property
    def nombre_completo(self) -> str:
        return f"{self.apellido}, {self.nombre}"


@dataclass
class ResumenSector:
    nombre_sector: str
    camas_disponibles: int


@dataclass
class CamaDisponible:
    nombre_sector: str
    nro_habitacion: int
    piso: int
    orientacion: str
    nro_cama: int


@dataclass
class CamaEstado:
    nombre_sector: str
    nro_habitacion: int
    piso: int
    orientacion: str
    nro_cama: int
    ocupada: bool
    id_internacion_activa: int | None = None
    dni_paciente: str | None = None
    nombre_paciente: str | None = None
    fecha_asignacion: datetime | None = None


@dataclass
class Internacion:
    id_internacion: int
    dni: str
    paciente: str
    matricula_medico: int
    medico: str
    fecha_inicio: datetime
    fecha_terminacion: datetime | None = None
    nro_habitacion: int | None = None
    nro_cama: int | None = None
    nombre_sector: str | None = None

    @property
    def esta_activa(self) -> bool:
        return self.fecha_terminacion is None


@dataclass
class OcupacionCama:
    id_internacion: int
    nro_habitacion: int
    nro_cama: int
    nombre_sector: str
    piso: int
    orientacion: str
    fecha_asignacion: datetime
    fecha_terminacion: datetime | None = None


@dataclass
class Ronda:
    id_ronda: int
    dia_ronda: str
    turno_ronda: int
    habitaciones: list[int] = field(default_factory=list)


@dataclass
class Recorrido:
    id_recorrido: int
    id_ronda: int
    dia_ronda: str
    turno_ronda: int
    matricula_medico: int
    medico: str
    fecha_recorrido: datetime
    cantidad_comentarios: int = 0


@dataclass
class ComentarioVisita:
    fecha_recorrido: datetime
    turno_ronda: int
    apellido_medico: str
    nombre_medico: str
    texto_comentario: str


@dataclass
class Guardia:
    id_guardia: int
    matricula_medico: int
    medico: str
    nombre_especialidad: str
    fecha_inicio: datetime
    fecha_fin: datetime
    turnos: list[str] = field(default_factory=list)


@dataclass
class Vacacion:
    matricula_medico: int
    medico: str
    fecha_inicio: datetime
    fecha_fin: datetime


@dataclass
class AuditoriaGuardia:
    id_auditoria: int
    fecha_hora: datetime
    usuario_bd: str
    usuario_so: str | None
    tabla_afectada: str
    operacion: str
    clave_registro: str
    detalle_cambio: str | None


@dataclass
class CasoPrueba:
    codigo: str
    grupo: str
    tipo: str  # "OK" o "FALLA"
    nombre: str
    esperado: str
    descripcion: str
    sql_resumen: str
    ejecutor: Callable[[], tuple[bool, str]]
