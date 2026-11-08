-- Casos de uso invalidos para el esquema del hospital.
-- Cada caso crea todo el contexto que necesita. No depende de
-- 03_casos_de_uso.sql ni de los casos anteriores, y puede ejecutarse solo
-- sobre un esquema vacio.
-- Las claves de este archivo no se pisan con las de 03_casos_de_uso.sql.
--
-- Parte 1. La sentencia indicada debe fallar. El contexto previo de ese
--          caso si se inserta. Si el cliente corta en el primer error, el
--          resto de los casos no llega a ejecutarse.
-- Parte 2. El enunciado los hace invalidos, pero el DDL actual los acepta.
--          Cada caso abre un SAVEPOINT y vuelve atras con
--          ROLLBACK TO SAVEPOINT, asi no deja filas ni borra otros casos.
--          Con autocommit ese ROLLBACK no alcanza.

-- #############################################################################
-- Parte 1. Deben fallar
-- #############################################################################

-- =============================================================================
-- Caso de uso: Sector ya existente
-- El caso crea el sector y vuelve a insertar el mismo nombre.
-- Debe fallar el segundo INSERT: PK pk_sector.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I01'
);

INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I01'
);

-- =============================================================================
-- Caso de uso: Habitacion de un sector que no existe
-- La habitacion apunta a un sector que este caso no crea.
-- Debe fallar: FK fk_habitacion_sector.
-- =============================================================================
INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7021,
   7,
   'NORTE',
   'Oncologia I02'
);

-- =============================================================================
-- Caso de uso: Habitacion sin piso
-- El caso crea el sector. El piso de la habitacion va en null.
-- Debe fallar: NOT NULL de habitacion.piso.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I03'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7031,
   null,
   'NORTE',
   'Maternidad I03'
);

-- =============================================================================
-- Caso de uso: Cama en una habitacion que no existe
-- La habitacion 7041 no se crea en este caso.
-- Debe fallar: FK fk_cama_habitacion.
-- =============================================================================
INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7041,
   1
);

-- =============================================================================
-- Caso de uso: Cama ya registrada
-- El caso crea la habitacion y la cama 1, y vuelve a insertar esa cama.
-- Debe fallar el segundo INSERT de CAMA: PK pk_cama.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I05'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7051,
   3,
   'NORTE',
   'Maternidad I05'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7051,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7051,
   1
);

-- =============================================================================
-- Caso de uso: Numero de cama menor a 1
-- El caso crea la habitacion. La cama 0 no es valida.
-- Debe fallar: CK ck_cama_nro.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I06'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7061,
   3,
   'NORTE',
   'Maternidad I06'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7061,
   0
);

-- =============================================================================
-- Caso de uso: Paciente sin persona
-- El DNI no se inserta en PERSONA.
-- Debe fallar: FK fk_paciente_persona.
-- =============================================================================
INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '40700001',
   date '1999-01-01',
   'F'
);

-- =============================================================================
-- Caso de uso: Medico cuyo DNI no esta en persona
-- La matricula usa un DNI que este caso no carga en PERSONA.
-- Debe fallar: FK fk_medico_persona.
-- =============================================================================
INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   9081,
   '40800001',
   null,
   '27408000019',
   timestamp '2022-01-01 00:00:00',
   2
);

-- =============================================================================
-- Caso de uso: Otro medico con el mismo DNI
-- El caso crea a la persona y al primer medico, y despues otra matricula
-- con el mismo DNI.
-- Debe fallar el segundo INSERT de MEDICO: UNIQUE uq_medico_dni.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '40900001',
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
   9091,
   '40900001',
   null,
   '27409000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   9092,
   '40900001',
   null,
   '27409000029',
   timestamp '2022-01-01 00:00:00',
   2
);

-- =============================================================================
-- Caso de uso: Otro medico con el mismo CUIL
-- El caso crea dos personas y el medico de Elena. Ana se da de alta como
-- medica con ese mismo CUIL.
-- Debe fallar el segundo INSERT de MEDICO: UNIQUE uq_medico_cuil.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41000001',
   'Elena',
   'Vargas'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41000002',
   'Ana',
   'Ruiz'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   9101,
   '41000001',
   null,
   '27410000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   9102,
   '41000002',
   null,
   '27410000019',
   timestamp '2022-01-01 00:00:00',
   2
);

-- =============================================================================
-- Caso de uso: Internar a quien no es paciente
-- El caso crea a Lucia como persona y medica, no como paciente, y crea al
-- medico principal. La internacion usa el DNI de Lucia.
-- Debe fallar: FK fk_internacion_paciente.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41100001',
   'Lucia',
   'Ferreyra'
);

INSERT INTO medico (
   matricula_medico,
   dni,
   foto,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES (
   9111,
   '41100001',
   null,
   '27411000019',
   timestamp '2021-05-03 00:00:00',
   0
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41100002',
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
   9112,
   '41100002',
   null,
   '27411000029',
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
   6111,
   timestamp '2026-11-06 08:00:00',
   null,
   9112,
   '41100001'
);

-- =============================================================================
-- Caso de uso: Internacion con un medico que no existe
-- El caso crea a la paciente. La matricula 9999 no se carga.
-- Debe fallar: FK fk_internacion_medico.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41200001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '41200001',
   date '1992-04-12',
   'F'
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   6121,
   timestamp '2026-11-06 08:00:00',
   null,
   9999,
   '41200001'
);

-- =============================================================================
-- Caso de uso: Internacion que no termina despues de empezar
-- El caso crea paciente y medico. El fin tiene que ser estrictamente
-- posterior al inicio. La primera fila termina antes; la segunda, en el
-- mismo instante.
-- Deben fallar las dos: CK ck_internacion_fechas.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41300001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '41300001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41300002',
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
   9131,
   '41300002',
   null,
   '27413000029',
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
   6131,
   timestamp '2026-04-02 10:00:00',
   timestamp '2026-04-02 09:00:00',
   9131,
   '41300001'
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   6132,
   timestamp '2026-04-02 10:00:00',
   timestamp '2026-04-02 10:00:00',
   9131,
   '41300001'
);

-- =============================================================================
-- Caso de uso: Ocupar una cama que no existe
-- El caso crea la habitacion con las camas 1, 2 y 4, la internacion y
-- despues asigna la cama 3, que no esta cargada.
-- Debe fallar: FK fk_ocupa_cama.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I14'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7141,
   3,
   'NORTE',
   'Maternidad I14'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7141,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7141,
   2
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7141,
   4
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41400001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '41400001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41400002',
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
   9141,
   '41400002',
   null,
   '27414000029',
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
   6141,
   timestamp '2026-11-02 08:30:00',
   null,
   9141,
   '41400001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6141,
   timestamp '2026-11-02 08:45:00',
   7141,
   3,
   null
);

-- =============================================================================
-- Caso de uso: Liberar la cama antes de ocuparla, o en el mismo instante
-- El caso crea la cama, la paciente y el medico. El fin de la ocupacion
-- tiene que ser estrictamente posterior al inicio.
-- Deben fallar las dos: CK ck_ocupa_fechas.
-- =============================================================================
INSERT INTO sector (
   nombre_sector
) VALUES (
   'Clinica I15'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7151,
   2,
   'SUR',
   'Clinica I15'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7151,
   1
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41500001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '41500001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41500002',
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
   9151,
   '41500002',
   null,
   '27415000029',
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
   6151,
   timestamp '2026-11-02 08:30:00',
   null,
   9151,
   '41500001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6151,
   timestamp '2026-11-04 10:00:00',
   7151,
   1,
   timestamp '2026-11-04 09:00:00'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6151,
   timestamp '2026-11-04 11:00:00',
   7151,
   1,
   timestamp '2026-11-04 11:00:00'
);

-- =============================================================================
-- Caso de uso: Guardia en una especialidad que el medico no tiene
-- El caso crea las dos especialidades, pero el medico solo posee Obstetricia.
-- La guardia existe. Desempenar Cardiologia no tiene fila en POSEE.
-- Debe fallar: FK fk_desempena_posee.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41600001',
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
   9161,
   '41600001',
   null,
   '27416000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Obstetricia I16'
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Cardiologia I16'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   9161,
   'Obstetricia I16',
   'S'
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   6161,
   timestamp '2026-11-09 06:00:00',
   timestamp '2026-11-09 14:00:00'
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   9161,
   'Cardiologia I16',
   6161
);

-- =============================================================================
-- Caso de uso: Comentario de un recorrido que no existe
-- El caso crea la internacion. El recorrido 6179 no se carga.
-- Debe fallar: FK fk_comentario_recorrido.
-- =============================================================================
INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41700001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '41700001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41700002',
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
   9171,
   '41700002',
   null,
   '27417000029',
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
   6171,
   timestamp '2026-11-02 08:30:00',
   null,
   9171,
   '41700001'
);

INSERT INTO comentario (
   id_comentario,
   id_internacion,
   id_recorrido,
   texto_comentario
) VALUES (
   6171,
   6171,
   6179,
   'Nota de un recorrido que no existe.'
);

-- #############################################################################
-- Parte 2. Invalidos para el enunciado, aceptados por el DDL actual
-- Cada caso crea su contexto, inserta el escenario invalido y lo deshace.
-- #############################################################################

-- =============================================================================
-- Caso de uso: Habitacion sin ninguna cama
-- El enunciado pide que una habitacion tenga 1 o mas camas. Este caso crea
-- el sector y la habitacion, y no inserta camas.
-- Resultado de hoy: el INSERT de la habitacion funciona. El SAVEPOINT lo deshace.
-- =============================================================================
SAVEPOINT caso_i18;

INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I18'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7181,
   7,
   'SUR',
   'Maternidad I18'
);

ROLLBACK TO SAVEPOINT caso_i18;

-- =============================================================================
-- Caso de uso: Dos internaciones abiertas del mismo paciente
-- El caso crea a la paciente, al medico y dos internaciones abiertas que se
-- solapan. El enunciado habla de muchas internaciones en la vida, no de dos
-- estadías simultaneas. El DDL no impide el solapamiento.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i19;

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41900001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '41900001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '41900002',
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
   9191,
   '41900002',
   null,
   '27419000029',
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
   6191,
   timestamp '2026-11-02 08:30:00',
   null,
   9191,
   '41900001'
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   6192,
   timestamp '2026-11-04 08:00:00',
   null,
   9191,
   '41900001'
);

ROLLBACK TO SAVEPOINT caso_i19;

-- =============================================================================
-- Caso de uso: Dos camas abiertas a la vez en la misma internacion
-- El caso crea dos camas y una internacion. La primera ocupacion sigue
-- abierta cuando se abre la segunda. El modelo asume una sola cama a la vez.
-- No hay constraint de exclusion.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i20;

INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I20'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7201,
   3,
   'NORTE',
   'Maternidad I20'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7201,
   1
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7201,
   2
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42000001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '42000001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42000002',
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
   9201,
   '42000002',
   null,
   '27420000029',
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
   6201,
   timestamp '2026-11-02 08:30:00',
   null,
   9201,
   '42000001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6201,
   timestamp '2026-11-02 08:45:00',
   7201,
   1,
   null
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6201,
   timestamp '2026-11-03 09:00:00',
   7201,
   2,
   null
);

ROLLBACK TO SAVEPOINT caso_i20;

-- =============================================================================
-- Caso de uso: Dos pacientes en la misma cama al mismo tiempo
-- El caso crea una cama, dos pacientes y dos internaciones abiertas. Las dos
-- ocupaciones de esa cama se solapan. El estado libre/ocupada no se guarda.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i21;

INSERT INTO sector (
   nombre_sector
) VALUES (
   'Maternidad I21'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7211,
   3,
   'NORTE',
   'Maternidad I21'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7211,
   1
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42100001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '42100001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42100002',
   'Ines',
   'Molina'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '42100002',
   date '1982-02-02',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42100003',
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
   9211,
   '42100003',
   null,
   '27421000039',
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
   6211,
   timestamp '2026-11-02 08:30:00',
   null,
   9211,
   '42100001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6211,
   timestamp '2026-11-02 08:45:00',
   7211,
   1,
   null
);

INSERT INTO internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) VALUES (
   6212,
   timestamp '2026-11-03 08:00:00',
   null,
   9211,
   '42100002'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6212,
   timestamp '2026-11-03 08:30:00',
   7211,
   1,
   null
);

ROLLBACK TO SAVEPOINT caso_i21;

-- =============================================================================
-- Caso de uso: Guardia en una especialidad que el medico no acepta cubrir
-- El caso crea la especialidad con hace_guardia = 'N', la guardia y la
-- asignacion. La FK contra POSEE se cumple porque la especialidad esta
-- declarada. El trigger que exigiria 'S' no esta creado.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i22;

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42200001',
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
   9221,
   '42200001',
   null,
   '27422000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Clinica Medica I22'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   9221,
   'Clinica Medica I22',
   'N'
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   6221,
   timestamp '2026-11-10 06:00:00',
   timestamp '2026-11-10 14:00:00'
);

INSERT INTO guardia_turno_manana (
   id_guardia
) VALUES (
   6221
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   9221,
   'Clinica Medica I22',
   6221
);

ROLLBACK TO SAVEPOINT caso_i22;

-- =============================================================================
-- Caso de uso: Mas guardias en el mes que el maximo declarado
-- El caso crea un medico con maximo 1 y le asigna dos guardias de noviembre
-- en una especialidad que si acepta. cantidad_guardias no se controla al
-- insertar en DESEMPENA.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i23;

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42300001',
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
   9231,
   '42300001',
   null,
   '27423000019',
   timestamp '2019-09-01 00:00:00',
   1
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Clinica Medica I23'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   9231,
   'Clinica Medica I23',
   'S'
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   6231,
   timestamp '2026-11-10 06:00:00',
   timestamp '2026-11-10 14:00:00'
);

INSERT INTO guardia_turno_manana (
   id_guardia
) VALUES (
   6231
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   9231,
   'Clinica Medica I23',
   6231
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   6232,
   timestamp '2026-11-12 06:00:00',
   timestamp '2026-11-12 14:00:00'
);

INSERT INTO guardia_turno_manana (
   id_guardia
) VALUES (
   6232
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   9231,
   'Clinica Medica I23',
   6232
);

ROLLBACK TO SAVEPOINT caso_i23;

-- =============================================================================
-- Caso de uso: Guardia durante las vacaciones
-- El caso crea las vacaciones del 2026-12-14 al 2026-12-28 y una guardia,
-- en una especialidad que el medico si acepta, el 2026-12-20. Nada en el DDL
-- cruza GUARDIA con VACACION.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i24;

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42400001',
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
   9241,
   '42400001',
   null,
   '27424000019',
   timestamp '2016-04-01 00:00:00',
   6
);

INSERT INTO especialidad (
   nombre_especialidad
) VALUES (
   'Obstetricia I24'
);

INSERT INTO posee (
   matricula_medico,
   nombre_especialidad,
   hace_guardia
) VALUES (
   9241,
   'Obstetricia I24',
   'S'
);

INSERT INTO vacacion (
   matricula_medico,
   fecha_inicio_vac,
   fecha_fin_vac
) VALUES (
   9241,
   timestamp '2026-12-14 00:00:00',
   timestamp '2026-12-28 00:00:00'
);

INSERT INTO guardia (
   id_guardia,
   fecha_inicio_guardia,
   fecha_fin_guardia
) VALUES (
   6241,
   timestamp '2026-12-20 06:00:00',
   timestamp '2026-12-20 14:00:00'
);

INSERT INTO guardia_turno_manana (
   id_guardia
) VALUES (
   6241
);

INSERT INTO desempena (
   matricula_medico,
   nombre_especialidad,
   id_guardia
) VALUES (
   9241,
   'Obstetricia I24',
   6241
);

ROLLBACK TO SAVEPOINT caso_i24;

-- =============================================================================
-- Caso de uso: Comentario sobre un paciente que no esta en la ronda
-- El caso crea dos habitaciones. El paciente esta internado en la 7251. La
-- ronda del martes visita solo la 7252. El recorrido es el martes 2026-11-10,
-- con la internacion todavia abierta, y el comentario apunta a ese paciente.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i25;

INSERT INTO sector (
   nombre_sector
) VALUES (
   'Clinica I25'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7251,
   3,
   'NORTE',
   'Clinica I25'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7251,
   1
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7252,
   4,
   'ESTE',
   'Clinica I25'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7252,
   1
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42500001',
   'Ana',
   'Ruiz'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '42500001',
   date '1992-04-12',
   'F'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42500002',
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
   9251,
   '42500002',
   null,
   '27425000029',
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
   6251,
   timestamp '2026-11-02 08:30:00',
   null,
   9251,
   '42500001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6251,
   timestamp '2026-11-02 08:45:00',
   7251,
   1,
   null
);

INSERT INTO ronda (
   id_ronda,
   dia_ronda,
   turno_ronda
) VALUES (
   6255,
   'MARTES',
   4
);

INSERT INTO es_visitada (
   id_ronda,
   nro_habitacion
) VALUES (
   6255,
   7252
);

INSERT INTO recorrido (
   id_recorrido,
   id_ronda,
   matricula_medico,
   fecha_recorrido
) VALUES (
   6257,
   6255,
   9251,
   timestamp '2026-11-10 10:00:00'
);

INSERT INTO comentario (
   id_comentario,
   id_internacion,
   id_recorrido,
   texto_comentario
) VALUES (
   6257,
   6251,
   6257,
   'Nota de una ronda que no visita la habitacion del paciente.'
);

ROLLBACK TO SAVEPOINT caso_i25;

-- =============================================================================
-- Caso de uso: Cama asignada fuera de las fechas de la internacion
-- El caso crea una internacion que termina el 2026-06-04 a las 09:00 y una
-- ocupacion de la misma cama que empieza ese dia a las 12:00. OCUPA solo
-- controla sus propias fechas.
-- Resultado de hoy: los INSERT funcionan. El SAVEPOINT los deshace.
-- =============================================================================
SAVEPOINT caso_i26;

INSERT INTO sector (
   nombre_sector
) VALUES (
   'Clinica I26'
);

INSERT INTO habitacion (
   nro_habitacion,
   piso,
   orientacion,
   nombre_sector
) VALUES (
   7261,
   3,
   'NORTE',
   'Clinica I26'
);

INSERT INTO cama (
   nro_habitacion,
   nro_cama
) VALUES (
   7261,
   1
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42600001',
   'Noel',
   'Ibanez'
);

INSERT INTO paciente (
   dni,
   fecha_nacimiento_paciente,
   sexo_paciente
) VALUES (
   '42600001',
   date '2003-12-01',
   'X'
);

INSERT INTO persona (
   dni,
   nombre,
   apellido
) VALUES (
   '42600002',
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
   9261,
   '42600002',
   null,
   '27426000029',
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
   6261,
   timestamp '2026-06-01 10:00:00',
   timestamp '2026-06-04 09:00:00',
   9261,
   '42600001'
);

INSERT INTO ocupa (
   id_internacion,
   fecha_asignacion_cama,
   nro_habitacion,
   nro_cama,
   fecha_terminacion_cama
) VALUES (
   6261,
   timestamp '2026-06-04 12:00:00',
   7261,
   1,
   timestamp '2026-06-04 18:00:00'
);

ROLLBACK TO SAVEPOINT caso_i26;
