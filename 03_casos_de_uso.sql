-- Casos de uso validos para el esquema del hospital.
-- Cada caso crea todo el contexto que necesita y usa claves propias.
-- Puede ejecutarse solo, sobre un esquema vacio, o junto con el resto
-- de este archivo: las claves no se pisan entre casos.
-- Ejecutar despues de 01_tablas_ddl.sql. No mezclar con 02_inserts.sql.
-- Todas las sentencias de un caso deben funcionar.
-- El estado libre/ocupada de una cama no se guarda: se deriva de OCUPA.

-- =============================================================================
-- Caso de uso: Habitacion con camas no correlativas
-- La habitacion 345 esta en el piso 3, orientacion norte, del sector que
-- este caso crea. Tiene las camas 1, 2 y 4. La cama 3 no existe: el numero
-- de cama es un dato libre mayor o igual a 1, no una secuencia sin huecos.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad V02'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   345,
   3,
   'NORTE',
   'Maternidad V02'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   345,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   345,
   2
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   345,
   4
);

COMMIT;

-- =============================================================================
-- Caso de uso: El mismo numero de cama en otra habitacion
-- Este caso crea las dos habitaciones. La 651 y la 652 tienen una cama 2.
-- La cama se identifica por el par (habitacion, numero), asi que son camas
-- distintas. Ambas pertenecen al sector que crea el caso.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Clinica V03'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   651,
   6,
   'SUR',
   'Clinica V03'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   651,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   651,
   2
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   652,
   6,
   'NORTE',
   'Clinica V03'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   652,
   2
);

COMMIT;

-- =============================================================================
-- Caso de uso: Alta de pacientes
-- Un paciente es una persona mas fecha de nacimiento y sexo. El sexo admite
-- F, M y X. Los tres pacientes de este caso cubren ese dominio.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '30600001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '30600001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '30600002',
   'Marcos',
   'Vidal'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '30600002',
   date '1980-08-19',
   'M'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '30600003',
   'Noel',
   'Ibanez'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '30600003',
   date '2003-12-01',
   'X'
);

COMMIT;

-- =============================================================================
-- Caso de uso: Alta de medicos con datos de liquidacion y sin foto
-- Este caso crea a las personas y a los medicos. La matricula identifica al
-- medico. El CUIL, la fecha de ingreso y el maximo de guardias por mes quedan
-- cargados. La foto queda en null.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '30700001',
   'Elena',
   'Vargas'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8071,
   '30700001',
   null,
   '27307000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '30700002',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8072,
   '30700002',
   null,
   '27307000029',
   timestamp '2019-09-01 00:00:00',
   4
);

COMMIT;

-- =============================================================================
-- Caso de uso: Medico que tambien es paciente
-- Este caso crea una sola persona y la registra como paciente y como medico.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '30800001',
   'Ines',
   'Molina'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '30800001',
   date '1982-02-02',
   'F'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8081,
   '30800001',
   null,
   '27308000019',
   timestamp '2014-01-15 00:00:00',
   3
);

COMMIT;

-- =============================================================================
-- Caso de uso: Especialidades y disposicion a hacer guardia
-- Este caso crea los medicos, las especialidades y la relacion. Tener la
-- especialidad no implica hacer guardia: Elena tiene Clinica Medica con
-- hace_guardia = 'N' y Obstetricia con 'S'.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31000001',
   'Elena',
   'Vargas'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8101,
   '31000001',
   null,
   '27310000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31000002',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8102,
   '31000002',
   null,
   '27310000029',
   timestamp '2019-09-01 00:00:00',
   4
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Obstetricia V10'
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Clinica Medica V10'
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Cardiologia V10'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   8101,
   'Obstetricia V10',
   'S'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   8101,
   'Clinica Medica V10',
   'N'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   8102,
   'Clinica Medica V10',
   'S'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   8102,
   'Cardiologia V10',
   'S'
);

COMMIT;

-- =============================================================================
-- Caso de uso: Paciente nuevo en internacion y asignado a una cama
-- Este caso crea el sector, la habitacion, la cama, la paciente y el medico.
-- Ana inicia una internacion abierta el 2026-11-02 con Elena como unico
-- medico principal y queda en la cama 1. La asignacion guarda habitacion,
-- cama y la fecha y hora de entrada. Los dos fines quedan en null.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad V11'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2111,
   3,
   'NORTE',
   'Maternidad V11'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2111,
   1
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31100001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '31100001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31100002',
   'Elena',
   'Vargas'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8111,
   '31100002',
   null,
   '27311000029',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   3111,
   timestamp '2026-11-02 08:30:00',
   null,
   8111,
   '31100001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3111,
   timestamp '2026-11-02 08:45:00',
   2111,
   1,
   null
);

COMMIT;

-- =============================================================================
-- Caso de uso: El paciente repite una cama y despues recibe el alta
-- Este caso crea la habitacion con dos camas, a Ines como paciente y a Pablo
-- como medico principal. Ines usa la cama 1, pasa a la cama 2 y vuelve a la
-- cama 1. Cada asignacion tiene su propia fecha de inicio. La internacion y
-- la ultima asignacion terminan el 2026-08-12.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Terapia Intensiva V13'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2131,
   6,
   'NORTE',
   'Terapia Intensiva V13'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2131,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2131,
   2
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31300001',
   'Ines',
   'Molina'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '31300001',
   date '1982-02-02',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31300002',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8131,
   '31300002',
   null,
   '27313000029',
   timestamp '2019-09-01 00:00:00',
   4
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   3131,
   timestamp '2026-08-01 07:00:00',
   timestamp '2026-08-12 11:00:00',
   8131,
   '31300001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3131,
   timestamp '2026-08-01 07:30:00',
   2131,
   1,
   timestamp '2026-08-04 10:00:00'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3131,
   timestamp '2026-08-04 10:00:00',
   2131,
   2,
   timestamp '2026-08-08 18:00:00'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3131,
   timestamp '2026-08-08 18:00:00',
   2131,
   1,
   timestamp '2026-08-12 11:00:00'
);

COMMIT;

-- =============================================================================
-- Caso de uso: Nueva internacion de un paciente que ya tuvo una
-- Este caso crea las dos internaciones de Noel. La primera, de junio, ya
-- termino con Pablo como medico principal. La segunda empieza el 2026-10-20
-- con Elena y usa la cama 4 de una habitacion que no tiene cama 3.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad V15'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2151,
   3,
   'NORTE',
   'Maternidad V15'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2151,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2151,
   2
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2151,
   4
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31500001',
   'Noel',
   'Ibanez'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '31500001',
   date '2003-12-01',
   'X'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31500002',
   'Elena',
   'Vargas'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8151,
   '31500002',
   null,
   '27315000029',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '31500003',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8152,
   '31500003',
   null,
   '27315000039',
   timestamp '2019-09-01 00:00:00',
   4
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   3151,
   timestamp '2026-06-01 10:00:00',
   timestamp '2026-06-04 09:00:00',
   8152,
   '31500001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3151,
   timestamp '2026-06-01 10:20:00',
   2151,
   2,
   timestamp '2026-06-04 09:00:00'
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   3152,
   timestamp '2026-10-20 14:00:00',
   null,
   8151,
   '31500001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3152,
   timestamp '2026-10-20 14:20:00',
   2151,
   4,
   null
);

COMMIT;

-- =============================================================================
-- Caso de uso: Una habitacion pertenece a mas de una ronda
-- Este caso crea tres habitaciones y dos rondas. La 2181 esta en la ronda de
-- los martes y tambien en la de los jueves. Ninguna ronda repite habitaciones.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Clinica V18'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2181,
   3,
   'NORTE',
   'Clinica V18'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2181,
   1
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2182,
   4,
   'ESTE',
   'Clinica V18'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2182,
   1
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2183,
   6,
   'SUR',
   'Clinica V18'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2183,
   1
);

INSERT INTO ronda (
   id_ronda,
   dia_ronda,
   turno_ronda
) VALUES (
   3181,
   'MARTES',
   4
);

INSERT INTO es_visitada (
   id_ronda,
   nro_habitacion
) VALUES (
   3181,
   2181
);

INSERT INTO es_visitada (
   id_ronda,
   nro_habitacion
) VALUES (
   3181,
   2182
);

INSERT INTO ronda (
   id_ronda,
   dia_ronda,
   turno_ronda
) VALUES (
   3182,
   'JUEVES',
   1
);

INSERT INTO es_visitada (
   id_ronda,
   nro_habitacion
) VALUES (
   3182,
   2181
);

INSERT INTO es_visitada (
   id_ronda,
   nro_habitacion
) VALUES (
   3182,
   2183
);

COMMIT;

-- =============================================================================
-- Caso de uso: Varios comentarios en la misma internacion
-- Este caso crea una internacion abierta y tres recorridos de los jueves,
-- de Elena y de Pablo. Cada recorrido agrega un comentario a esa internacion.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Clinica V22'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   2221,
   3,
   'NORTE',
   'Clinica V22'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   2221,
   1
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '32200001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '32200001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '32200002',
   'Elena',
   'Vargas'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8221,
   '32200002',
   null,
   '27322000029',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '32200003',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8222,
   '32200003',
   null,
   '27322000039',
   timestamp '2019-09-01 00:00:00',
   4
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   3221,
   timestamp '2026-11-02 08:30:00',
   null,
   8221,
   '32200001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   3221,
   timestamp '2026-11-02 08:45:00',
   2221,
   1,
   null
);

INSERT INTO ronda (
   id_ronda,
   dia_ronda,
   turno_ronda
) VALUES (
   3225,
   'JUEVES',
   1
);

INSERT INTO es_visitada (
   id_ronda,
   nro_habitacion
) VALUES (
   3225,
   2221
);

INSERT INTO recorrido (
   id_recorrido,
   id_ronda,
   matricula_medico,
   fecha_recorrido
) VALUES (
   3227,
   3225,
   8222,
   timestamp '2026-11-05 09:30:00'
);

INSERT INTO comentario (
   id_comentario,
   id_internacion,
   id_recorrido,
   texto_comentario
) VALUES (
   3227,
   3221,
   3227,
   'Evolucion favorable, permanece en la misma cama.'
);

INSERT INTO recorrido (
   id_recorrido,
   id_ronda,
   matricula_medico,
   fecha_recorrido
) VALUES (
   3228,
   3225,
   8221,
   timestamp '2026-11-12 10:00:00'
);

INSERT INTO comentario (
   id_comentario,
   id_internacion,
   id_recorrido,
   texto_comentario
) VALUES (
   3228,
   3221,
   3228,
   'Sin fiebre. Se mantiene el plan indicado.'
);

INSERT INTO recorrido (
   id_recorrido,
   id_ronda,
   matricula_medico,
   fecha_recorrido
) VALUES (
   3229,
   3225,
   8222,
   timestamp '2026-11-19 11:15:00'
);

INSERT INTO comentario (
   id_comentario,
   id_internacion,
   id_recorrido,
   texto_comentario
) VALUES (
   3229,
   3221,
   3229,
   'Buena evolucion. Se evalua el alta.'
);

COMMIT;

-- =============================================================================
-- Caso de uso: Segundo periodo de vacaciones, sin superposicion
-- Este caso crea al medico y los dos periodos. El segundo empieza despues
-- de que termino el primero. Inicio y fin no se repiten.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '32500001',
   'Elena',
   'Vargas'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8251,
   '32500001',
   null,
   '27325000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO vacacion (
   matricula_medico,
   fecha_inicio_vac,
   fecha_fin_vac
) VALUES (
   8251,
   timestamp '2026-12-14 00:00:00',
   timestamp '2026-12-28 00:00:00'
);

INSERT INTO vacacion (
   matricula_medico,
   fecha_inicio_vac,
   fecha_fin_vac
) VALUES (
   8251,
   timestamp '2027-02-01 00:00:00',
   timestamp '2027-02-15 00:00:00'
);

COMMIT;

-- =============================================================================
-- Caso de uso: Los tres turnos diarios de guardia de una especialidad
-- Este caso crea al medico, la especialidad que acepta cubrir y las tres
-- guardias del 2026-11-10: manana, tarde y noche. Son 3 y su maximo es 4.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '32700001',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8271,
   '32700001',
   null,
   '27327000019',
   timestamp '2019-09-01 00:00:00',
   4
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Clinica Medica V27'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   8271,
   'Clinica Medica V27',
   'S'
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   3271,
   timestamp '2026-11-10 06:00:00',
   timestamp '2026-11-10 14:00:00'
);

INSERT INTO guardia_turno_manana (
   id_guardia
) VALUES (
   3271
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   8271,
   'Clinica Medica V27',
   3271
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   3272,
   timestamp '2026-11-10 14:00:00',
   timestamp '2026-11-10 22:00:00'
);

INSERT INTO guardia_turno_tarde (
   id_guardia
) VALUES (
   3272
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   8271,
   'Clinica Medica V27',
   3272
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   3273,
   timestamp '2026-11-10 22:00:00',
   timestamp '2026-11-11 06:00:00'
);

INSERT INTO guardia_turno_noche (
   id_guardia
) VALUES (
   3273
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   8271,
   'Clinica Medica V27',
   3273
);

COMMIT;

-- =============================================================================
-- Caso de uso: Una guardia que abarca dos turnos
-- Este caso crea al medico y una guardia del 2026-11-11 de 06:00 a 22:00.
-- Esa guardia queda en el turno manana y en el turno tarde. La especialidad
-- es una que el medico acepta, y es su unica guardia del mes.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '32800001',
   'Pablo',
   'Nunez'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   8281,
   '32800001',
   null,
   '27328000019',
   timestamp '2019-09-01 00:00:00',
   4
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Cardiologia V28'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   8281,
   'Cardiologia V28',
   'S'
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   3281,
   timestamp '2026-11-11 06:00:00',
   timestamp '2026-11-11 22:00:00'
);

INSERT INTO guardia_turno_manana (
   id_guardia
) VALUES (
   3281
);

INSERT INTO guardia_turno_tarde (
   id_guardia
) VALUES (
   3281
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   8281,
   'Cardiologia V28',
   3281
);

COMMIT;
