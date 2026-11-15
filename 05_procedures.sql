-- Camas disponibles
-- Una cama esta disponible cuando no exista fila en OCUPA que tenga
-- fechas de asignacion y terminacion que cubran el instante actual,
-- o que la fecha de terminacion sea null (el paciente sigue en la cama).
CREATE OR REPLACE VIEW vw_cama_disponible AS
   SELECT H.nombre_sector,
         H.nro_habitacion,
         H.piso,
         H.orientacion,
         C.nro_cama
   FROM cama C
   JOIN habitacion H ON H.nro_habitacion = C.nro_habitacion
   WHERE NOT EXISTS (
      SELECT 1
      FROM ocupa O
      WHERE O.nro_habitacion = C.nro_habitacion
         AND O.nro_cama = C.nro_cama
         AND O.fecha_asignacion_cama <= systimestamp
         AND ( O.fecha_terminacion_cama IS NULL
            OR O.fecha_terminacion_cama > systimestamp )
   );

-- PROCEDURE con dos cursores:
--   cursor_cantidad: nombre del sector y cantidad de camas disponibles
--   cursor_detalle:  nombre del sector, numero de habitacion, piso, orientacion y numero de cama
CREATE OR REPLACE PROCEDURE pr_camas_disponibles (
   cursor_cantidad OUT sys_refcursor,
   cursor_detalle  OUT sys_refcursor
) AS
BEGIN
   OPEN cursor_cantidad FOR
      SELECT S.nombre_sector,
             COUNT(D.nro_cama) AS cantidad_camas_disponibles
        FROM sector S
        LEFT JOIN vw_cama_disponible D
          ON D.nombre_sector = S.nombre_sector
       GROUP BY S.nombre_sector
       ORDER BY S.nombre_sector;

   OPEN cursor_detalle FOR
      SELECT D.nombre_sector,
             D.nro_habitacion,
             D.piso,
             D.orientacion,
             D.nro_cama
        FROM vw_cama_disponible D
       ORDER BY D.nombre_sector,
                D.nro_habitacion,
                D.nro_cama;
END;
/

-- Para probar en terminal:
-- VARIABLE cant REFCURSOR;
-- VARIABLE deta REFCURSOR;
-- EXECUTE pr_camas_disponibles(:cant, :deta);
-- PRINT cant;
-- PRINT deta;


-- -----------------------------------------------------------------------------

-- Comentarios de las visitas medicas a un paciente en una internacion.
-- La fecha y el medico que escribio salen del recorrido; el turno sale de
-- la ronda de ese recorrido. El comentario solo guarda el texto.
-- Si la internacion no es de ese paciente, el cursor vuelve vacio.
CREATE OR REPLACE PROCEDURE pr_comentarios_internacion (
   p_id_internacion   IN internacion.id_internacion%TYPE,
   p_dni_paciente     IN internacion.dni%TYPE,
   cursor_comentarios OUT sys_refcursor
) AS
BEGIN
   OPEN cursor_comentarios FOR
      SELECT R.fecha_recorrido,
             RD.turno_ronda,
             P.apellido,
             P.nombre,
             C.texto_comentario
        FROM internacion I
        JOIN comentario C
          ON C.id_internacion = I.id_internacion
        JOIN recorrido R
          ON R.id_recorrido = C.id_recorrido
        JOIN ronda RD
          ON RD.id_ronda = R.id_ronda
        JOIN medico M
          ON M.matricula_medico = R.matricula_medico
        JOIN persona P
          ON P.dni = M.dni
       WHERE I.id_internacion = p_id_internacion
         AND I.dni = p_dni_paciente
       ORDER BY R.fecha_recorrido,
                C.id_comentario;
END;
/
-- Tiene muchos JOINs que son necesarios para obtener los datos.
-- Sin embargo no son tan costosos porque buscan por clave primaria.

-- Posible indice que puede mejorar el rendimiento:
-- CREATE INDEX ix_comentario_internacion ON comentario (
--   id_internacion
--);

-- Para probar en terminal:
-- VARIABLE comen REFCURSOR;
-- EXECUTE pr_comentarios_internacion(1, '30111111', :comen);
-- PRINT comen;

