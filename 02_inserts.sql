-- ---------- Sectores, habitaciones y camas ----------
INSERT INTO sector VALUES
   ( 'Maternidad' );
INSERT INTO sector VALUES
   ( 'Neonatologia' );
INSERT INTO sector VALUES
   ( 'Clinica Medica' );
INSERT INTO sector VALUES
   ( 'Terapia Intensiva' );
INSERT INTO sector VALUES
   ( 'Pediatria' );   -- sin habitaciones: prueba el "0 camas" de la vista

INSERT INTO habitacion VALUES
   ( 101,
     1,
     'NORTE',
     'Maternidad' );
INSERT INTO habitacion VALUES
   ( 102,
     1,
     'SUR',
     'Maternidad' );
INSERT INTO habitacion VALUES
   ( 201,
     2,
     'ESTE',
     'Neonatologia' );
INSERT INTO habitacion VALUES
   ( 301,
     3,
     'NORTE',
     'Clinica Medica' );
INSERT INTO habitacion VALUES
   ( 302,
     3,
     'SUR',
     'Clinica Medica' );
INSERT INTO habitacion VALUES
   ( 401,
     4,
     'OESTE',
     'Terapia Intensiva' );

INSERT INTO cama VALUES
   ( 101,
     1 );
INSERT INTO cama VALUES
   ( 101,
     2 );
INSERT INTO cama VALUES
   ( 102,
     1 );
INSERT INTO cama VALUES
   ( 102,
     2 );
INSERT INTO cama VALUES
   ( 102,
     4 );          -- cama 4 sin cama 3 (numeracion no correlativa)
INSERT INTO cama VALUES
   ( 201,
     1 );
INSERT INTO cama VALUES
   ( 201,
     2 );
INSERT INTO cama VALUES
   ( 201,
     3 );
INSERT INTO cama VALUES
   ( 301,
     1 );
INSERT INTO cama VALUES
   ( 301,
     2 );
INSERT INTO cama VALUES
   ( 302,
     1 );
INSERT INTO cama VALUES
   ( 401,
     1 );
INSERT INTO cama VALUES
   ( 401,
     2 );
 
-- ---------- Personas, pacientes y medicos ----------
-- Medicos
INSERT INTO persona VALUES
   ( '20111111',
     'Laura',
     'Gomez' );
INSERT INTO persona VALUES
   ( '22222222',
     'Martin',
     'Perez' );
INSERT INTO persona VALUES
   ( '23333333',
     'Carla',
     'Rossi' );
INSERT INTO persona VALUES
   ( '24444444',
     'Sergio',
     'Diaz' );     -- medico Y tambien paciente
-- Pacientes
INSERT INTO persona VALUES
   ( '30111111',
     'Ana',
     'Lopez' );
INSERT INTO persona VALUES
   ( '30222222',
     'Juan',
     'Fernandez' );
INSERT INTO persona VALUES
   ( '30333333',
     'Sofia',
     'Martinez' );
INSERT INTO persona VALUES
   ( '30444444',
     'Pedro',
     'Suarez' );
INSERT INTO persona VALUES
   ( '30555555',
     'Lucia',
     'Torres' );

INSERT INTO paciente VALUES
   ( '30111111',
     date '1990-05-14',
     'F' );
INSERT INTO paciente VALUES
   ( '30222222',
     date '1984-11-02',
     'M' );
INSERT INTO paciente VALUES
   ( '30333333',
     date '1978-07-23',
     'F' );
INSERT INTO paciente VALUES
   ( '30444444',
     date '2001-01-30',
     'M' );
INSERT INTO paciente VALUES
   ( '30555555',
     date '1995-09-09',
     'F' );
INSERT INTO paciente VALUES
   ( '24444444',
     date '1975-03-02',
     'M' );  -- el Dr. Diaz como paciente
 
-- La foto (BLOB) se deja en NULL
INSERT INTO medico (
   matricula_medico,
   dni,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES
   ( 1001,
     '20111111',
     '27201111115',
     timestamp '2015-03-01 00:00:00',
     8 );
INSERT INTO medico (
   matricula_medico,
   dni,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES
   ( 1002,
     '22222222',
     '20222222221',
     timestamp '2018-08-15 00:00:00',
     6 );
INSERT INTO medico (
   matricula_medico,
   dni,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES
   ( 1003,
     '23333333',
     '27233333338',
     timestamp '2020-02-10 00:00:00',
     4 );
INSERT INTO medico (
   matricula_medico,
   dni,
   cuil_cuit,
   fecha_de_ingreso,
   cantidad_guardias
) VALUES
   ( 1004,
     '24444444',
     '20244444447',
     timestamp '2012-06-20 00:00:00',
     2 );  -- tope bajo a proposito
 
-- ---------- Especialidades ----------
INSERT INTO especialidad VALUES
   ( 'Clinica Medica' );
INSERT INTO especialidad VALUES
   ( 'Cardiologia' );
INSERT INTO especialidad VALUES
   ( 'Pediatria' );
INSERT INTO especialidad VALUES
   ( 'Obstetricia' );
INSERT INTO especialidad VALUES
   ( 'Terapia Intensiva' );
 
-- hace_guardia: 'S' = dispuesto a hacer guardia en esa especialidad
INSERT INTO posee VALUES
   ( 1001,
     'Clinica Medica',
     'S' );
INSERT INTO posee VALUES
   ( 1001,
     'Cardiologia',
     'N' );   -- la tiene, pero no hace guardia
INSERT INTO posee VALUES
   ( 1002,
     'Cardiologia',
     'S' );
INSERT INTO posee VALUES
   ( 1002,
     'Terapia Intensiva',
     'S' );
INSERT INTO posee VALUES
   ( 1003,
     'Obstetricia',
     'S' );
INSERT INTO posee VALUES
   ( 1003,
     'Pediatria',
     'N' );
INSERT INTO posee VALUES
   ( 1004,
     'Clinica Medica',
     'S' );
 
-- ---------- Internaciones y ocupacion de camas ----------
-- I1: Ana Lopez, en curso. Cambia de cama: 101-1 -> 102-2
INSERT INTO internacion VALUES
   ( 1,
     timestamp '2026-10-20 10:00:00',
     null,
     1003,
     '30111111' );
INSERT INTO ocupa VALUES
   ( 1,
     timestamp '2026-10-20 10:00:00',
     101,
     1,
     timestamp '2026-10-22 09:00:00' );
INSERT INTO ocupa VALUES
   ( 1,
     timestamp '2026-10-22 09:00:00',
     102,
     2,
     null );
 
-- I2: Juan Fernandez, en curso, cama 301-1
INSERT INTO internacion VALUES
   ( 2,
     timestamp '2026-10-18 08:00:00',
     null,
     1001,
     '30222222' );
INSERT INTO ocupa VALUES
   ( 2,
     timestamp '2026-10-18 08:30:00',
     301,
     1,
     null );
 
-- I3: Sofia Martinez, terminada. Pasa 401-1 -> 401-2 y REPITE la 401-1 (permitido por el enunciado)
INSERT INTO internacion VALUES
   ( 3,
     timestamp '2026-10-01 08:00:00',
     timestamp '2026-10-08 09:00:00',
     1002,
     '30333333' );
INSERT INTO ocupa VALUES
   ( 3,
     timestamp '2026-10-01 12:00:00',
     401,
     1,
     timestamp '2026-10-05 12:00:00' );
INSERT INTO ocupa VALUES
   ( 3,
     timestamp '2026-10-05 12:00:00',
     401,
     2,
     timestamp '2026-10-07 12:00:00' );
INSERT INTO ocupa VALUES
   ( 3,
     timestamp '2026-10-07 12:00:00',
     401,
     1,
     timestamp '2026-10-08 09:00:00' );
 
-- I4: Pedro Suarez, terminada
INSERT INTO internacion VALUES
   ( 4,
     timestamp '2026-09-10 09:00:00',
     timestamp '2026-09-15 08:00:00',
     1003,
     '30444444' );
INSERT INTO ocupa VALUES
   ( 4,
     timestamp '2026-09-10 09:00:00',
     201,
     1,
     timestamp '2026-09-15 08:00:00' );
 
-- I5: el Dr. Diaz internado como PACIENTE, con otro medico (1001) como principal
INSERT INTO internacion VALUES
   ( 5,
     timestamp '2026-10-10 08:00:00',
     timestamp '2026-10-20 12:00:00',
     1001,
     '24444444' );
INSERT INTO ocupa VALUES
   ( 5,
     timestamp '2026-10-10 09:00:00',
     302,
     1,
     timestamp '2026-10-20 12:00:00' );
 
-- I6: Lucia Torres, en curso, 401-1
INSERT INTO internacion VALUES
   ( 6,
     timestamp '2026-10-24 14:00:00',
     null,
     1002,
     '30555555' );
INSERT INTO ocupa VALUES
   ( 6,
     timestamp '2026-10-24 15:00:00',
     401,
     1,
     null );
 
-- ---------- Rondas y recorridos ----------
INSERT INTO ronda VALUES
   ( 1,
     'MARTES',
     3 );
INSERT INTO ronda VALUES
   ( 2,
     'MIERCOLES',
     1 );
INSERT INTO ronda VALUES
   ( 3,
     'JUEVES',
     2 );
INSERT INTO ronda VALUES
   ( 4,
     'VIERNES',
     1 );
 
-- Ninguna habitacion repetida dentro de una ronda; todas estan en alguna ronda
INSERT INTO es_visitada VALUES
   ( 1,
     101 );
INSERT INTO es_visitada VALUES
   ( 1,
     102 );
INSERT INTO es_visitada VALUES
   ( 2,
     301 );
INSERT INTO es_visitada VALUES
   ( 2,
     302 );
INSERT INTO es_visitada VALUES
   ( 3,
     401 );
INSERT INTO es_visitada VALUES
   ( 3,
     102 );
INSERT INTO es_visitada VALUES
   ( 4,
     201 );
INSERT INTO es_visitada VALUES
   ( 4,
     301 );
INSERT INTO es_visitada VALUES
   ( 4,
     401 );
 
-- (id_recorrido, id_ronda, matricula_medico, fecha_recorrido)
INSERT INTO recorrido VALUES
   ( 1,
     3,
     1003,
     timestamp '2026-10-01 15:00:00' );  -- jueves
INSERT INTO recorrido VALUES
   ( 2,
     1,
     1001,
     timestamp '2026-10-20 16:00:00' );  -- martes
INSERT INTO recorrido VALUES
   ( 3,
     2,
     1003,
     timestamp '2026-10-21 09:00:00' );  -- miercoles
INSERT INTO recorrido VALUES
   ( 4,
     3,
     1002,
     timestamp '2026-10-22 11:00:00' );  -- jueves
INSERT INTO recorrido VALUES
   ( 5,
     4,
     1001,
     timestamp '2026-10-23 10:00:00' );  -- viernes
 
-- (id_comentario, id_internacion, id_recorrido, texto)
-- Cada paciente esta, en ese momento, en una habitacion de la ronda del recorrido
INSERT INTO comentario VALUES
   ( 1,
     3,
     1,
     'Paciente en terapia, signos vitales esTABLEs.' );
INSERT INTO comentario VALUES
   ( 2,
     1,
     2,
     'Evolucion favorable, sin fiebre.' );
INSERT INTO comentario VALUES
   ( 3,
     2,
     3,
     'Se ajusta medicacion segun laboratorio.' );
INSERT INTO comentario VALUES
   ( 4,
     1,
     4,
     'Traslado a nueva cama sin complicaciones.' );
INSERT INTO comentario VALUES
   ( 5,
     2,
     5,
     'Mejoria clinica, se evalua alta en 48 hs.' );
 
-- ---------- Vacaciones (sin superposicion dentro de cada medico) ----------
INSERT INTO vacacion VALUES
   ( 1001,
     timestamp '2026-11-20 00:00:00',
     timestamp '2026-12-04 23:59:59' );
INSERT INTO vacacion VALUES
   ( 1001,
     timestamp '2027-01-15 00:00:00',
     timestamp '2027-01-30 23:59:59' );
INSERT INTO vacacion VALUES
   ( 1002,
     timestamp '2026-12-15 00:00:00',
     timestamp '2027-01-05 23:59:59' );
INSERT INTO vacacion VALUES
   ( 1003,
     timestamp '2027-02-01 00:00:00',
     timestamp '2027-02-15 23:59:59' );
INSERT INTO vacacion VALUES
   ( 1004,
     timestamp '2027-01-10 00:00:00',
     timestamp '2027-01-24 23:59:59' );
 
-- ---------- Guardias ----------
INSERT INTO guardia VALUES
   ( 1,
     timestamp '2026-11-02 06:00:00',
     timestamp '2026-11-02 14:00:00' );  -- manana
INSERT INTO guardia VALUES
   ( 2,
     timestamp '2026-11-02 14:00:00',
     timestamp '2026-11-02 22:00:00' );  -- tarde
INSERT INTO guardia VALUES
   ( 3,
     timestamp '2026-11-02 22:00:00',
     timestamp '2026-11-03 06:00:00' );  -- noche
INSERT INTO guardia VALUES
   ( 4,
     timestamp '2026-11-03 06:00:00',
     timestamp '2026-11-03 14:00:00' );  -- manana
INSERT INTO guardia VALUES
   ( 5,
     timestamp '2026-11-10 06:00:00',
     timestamp '2026-11-10 14:00:00' );  -- manana

INSERT INTO guardia_turno_manana VALUES
   ( 1 );
INSERT INTO guardia_turno_manana VALUES
   ( 4 );
INSERT INTO guardia_turno_manana VALUES
   ( 5 );
INSERT INTO guardia_turno_tarde VALUES
   ( 2 );
INSERT INTO guardia_turno_noche VALUES
   ( 3 );
 
-- (matricula, especialidad, id_guardia). El Dr. Diaz (1004, maximo 2/mes) queda con 2 en noviembre
INSERT INTO desempena VALUES
   ( 1001,
     'Clinica Medica',
     1 );
INSERT INTO desempena VALUES
   ( 1001,
     'Clinica Medica',
     4 );
INSERT INTO desempena VALUES
   ( 1002,
     'Cardiologia',
     2 );
INSERT INTO desempena VALUES
   ( 1003,
     'Obstetricia',
     3 );
INSERT INTO desempena VALUES
   ( 1004,
     'Clinica Medica',
     2 );
INSERT INTO desempena VALUES
   ( 1004,
     'Clinica Medica',
     4 );


COMMIT;