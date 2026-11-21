-- =========================================================================
-- 04_triggers_restricciones.sql: Reglas de negocio de la Seccion 4
-- =========================================================================

-- 1. Un medico no puede ser su propio medico principal al internarse (Seccion 4.3)
CREATE OR REPLACE TRIGGER trg_internacion_medico_paciente
BEFORE INSERT OR UPDATE ON internacion
FOR EACH ROW
DECLARE
   v_dni_medico medico.dni%TYPE;
BEGIN
   SELECT dni INTO v_dni_medico
   FROM medico
   WHERE matricula_medico = :NEW.matricula_medico;

   IF v_dni_medico = :NEW.dni THEN
      RAISE_APPLICATION_ERROR(-20001, 'Un medico no puede ser su propio medico principal durante su internacion.');
   END IF;
END;
/

-- 2. Validaciones integrales al asignar una guardia en DESEMPENA (Seccion 4.2):
--    a) Que en POSEE tenga hace_guardia = 'S'
--    b) Que la guardia no se solape con vacaciones del medico
--    c) Que el medico no este internado como paciente durante la guardia
--    d) Que no supere cantidad_guardias en ese mes calendario
CCREATE OR REPLACE TRIGGER trg_validar_asignacion_guardia
FOR INSERT OR UPDATE ON desempena
COMPOUND TRIGGER

   TYPE t_asignacion IS RECORD (
      matricula_medico desempena.matricula_medico%TYPE,
      id_guardia       desempena.id_guardia%TYPE
   );
   TYPE t_asignaciones IS TABLE OF t_asignacion INDEX BY PLS_INTEGER;

   v_asig t_asignaciones;
   v_idx  PLS_INTEGER := 0;

   -- 1. A nivel fila: validamos contra las OTRAS tablas (posee, medico, guardia, vacacion, internacion)
   BEFORE EACH ROW IS
      v_hace_guardia  posee.hace_guardia%TYPE;
      v_dni_medico    medico.dni%TYPE;
      v_ini_guardia   guardia.fecha_inicio_guardia%TYPE;
      v_fin_guardia   guardia.fecha_fin_guardia%TYPE;
      v_en_vacaciones NUMBER;
      v_internado     NUMBER;
   BEGIN
      SELECT hace_guardia INTO v_hace_guardia
      FROM posee
      WHERE matricula_medico = :NEW.matricula_medico
        AND nombre_especialidad = :NEW.nombre_especialidad;

      IF v_hace_guardia <> 'S' THEN
         RAISE_APPLICATION_ERROR(-20002, 'El medico no esta dispuesto a hacer guardias en esa especialidad (hace_guardia <> S).');
      END IF;

      SELECT dni INTO v_dni_medico
      FROM medico
      WHERE matricula_medico = :NEW.matricula_medico;

      SELECT fecha_inicio_guardia, fecha_fin_guardia INTO v_ini_guardia, v_fin_guardia
      FROM guardia
      WHERE id_guardia = :NEW.id_guardia;

      SELECT COUNT(*) INTO v_en_vacaciones
      FROM vacacion
      WHERE matricula_medico = :NEW.matricula_medico
        AND v_ini_guardia <= fecha_fin_vac
        AND v_fin_guardia >= fecha_inicio_vac;

      IF v_en_vacaciones > 0 THEN
         RAISE_APPLICATION_ERROR(-20003, 'El medico se encuentra de vacaciones durante el horario de la guardia.');
      END IF;

      SELECT COUNT(*) INTO v_internado
      FROM internacion
      WHERE dni = v_dni_medico
        AND v_ini_guardia <= NVL(fecha_terminacion_internacion, TIMESTAMP '9999-12-31 23:59:59')
        AND v_fin_guardia >= fecha_inicio_internacion;

      IF v_internado > 0 THEN
         RAISE_APPLICATION_ERROR(-20004, 'El medico figura internado como paciente durante el periodo de la guardia.');
      END IF;

      v_idx := v_idx + 1;
      v_asig(v_idx).matricula_medico := :NEW.matricula_medico;
      v_asig(v_idx).id_guardia       := :NEW.id_guardia;
   END BEFORE EACH ROW;

   -- 2. Al terminar la sentencia: consultamos DESEMPENA sin riesgo de tabla mutante
   AFTER STATEMENT IS
      v_max_guardias medico.cantidad_guardias%TYPE;
      v_ini_guardia  guardia.fecha_inicio_guardia%TYPE;
      v_cant_mes     NUMBER;
   BEGIN
      FOR i IN 1 .. v_idx LOOP
         SELECT cantidad_guardias INTO v_max_guardias
         FROM medico
         WHERE matricula_medico = v_asig(i).matricula_medico;

         SELECT fecha_inicio_guardia INTO v_ini_guardia
         FROM guardia
         WHERE id_guardia = v_asig(i).id_guardia;

         SELECT COUNT(*) INTO v_cant_mes
         FROM desempena d
         JOIN guardia g ON g.id_guardia = d.id_guardia
         WHERE d.matricula_medico = v_asig(i).matricula_medico
           AND EXTRACT(YEAR FROM g.fecha_inicio_guardia) = EXTRACT(YEAR FROM v_ini_guardia)
           AND EXTRACT(MONTH FROM g.fecha_inicio_guardia) = EXTRACT(MONTH FROM v_ini_guardia);

         IF v_cant_mes > v_max_guardias THEN
            RAISE_APPLICATION_ERROR(-20005, 'El medico supera el maximo de guardias mensuales que acepta realizar.');
         END IF;
      END LOOP;
   END AFTER STATEMENT;

END trg_validar_asignacion_guardia;
/


-- 3. Evitar solapamiento de vacaciones de un mismo medico (Seccion 4.1)
--    Se usa COMPOUND TRIGGER para evitar ORA-04091 (tabla mutante) ante UPDATE o INSERT multiple
CREATE OR REPLACE TRIGGER trg_vacacion_no_solapa
FOR INSERT OR UPDATE ON vacacion
COMPOUND TRIGGER
   TYPE t_matriculas IS TABLE OF vacacion.matricula_medico%TYPE INDEX BY PLS_INTEGER;
   v_matriculas t_matriculas;
   v_idx        PLS_INTEGER := 0;

   AFTER EACH ROW IS
   BEGIN
      v_idx := v_idx + 1;
      v_matriculas(v_idx) := :NEW.matricula_medico;
   END AFTER EACH ROW;

   AFTER STATEMENT IS
      v_solapadas NUMBER;
   BEGIN
      FOR i IN 1 .. v_idx LOOP
         SELECT COUNT(*) INTO v_solapadas
         FROM vacacion v1
         JOIN vacacion v2
           ON v1.matricula_medico = v2.matricula_medico
          AND v1.ROWID <> v2.ROWID
          AND v1.fecha_inicio_vac <= v2.fecha_fin_vac
          AND v1.fecha_fin_vac >= v2.fecha_inicio_vac
         WHERE v1.matricula_medico = v_matriculas(i);

         IF v_solapadas > 0 THEN
            RAISE_APPLICATION_ERROR(-20006, 'Las fechas de vacaciones se superponen con otro periodo del mismo medico.');
         END IF;
      END LOOP;
   END AFTER STATEMENT;
END trg_vacacion_no_solapa;
/

-- 4. Validar COMENTARIO: que el paciente ocupe en la fecha del recorrido una
--    habitacion perteneciente a la ronda del recorrido, y que el medico no sea
--    el propio paciente (Secciones 2.1, 4.1 y 4.4)
CREATE OR REPLACE TRIGGER trg_validar_comentario
BEFORE INSERT OR UPDATE ON comentario
FOR EACH ROW
DECLARE
   v_fecha_rec    recorrido.fecha_recorrido%TYPE;
   v_id_ronda     recorrido.id_ronda%TYPE;
   v_mat_medico   recorrido.matricula_medico%TYPE;
   v_dni_medico   medico.dni%TYPE;
   v_dni_paciente internacion.dni%TYPE;
   v_ini_int      internacion.fecha_inicio_internacion%TYPE;
   v_fin_int      internacion.fecha_terminacion_internacion%TYPE;
   v_hab_valida   NUMBER;
BEGIN
   SELECT r.fecha_recorrido, r.id_ronda, r.matricula_medico, m.dni
   INTO v_fecha_rec, v_id_ronda, v_mat_medico, v_dni_medico
   FROM recorrido r
   JOIN medico m ON m.matricula_medico = r.matricula_medico
   WHERE r.id_recorrido = :NEW.id_recorrido;

   SELECT dni, fecha_inicio_internacion, fecha_terminacion_internacion
   INTO v_dni_paciente, v_ini_int, v_fin_int
   FROM internacion
   WHERE id_internacion = :NEW.id_internacion;

   IF v_dni_medico = v_dni_paciente THEN
      RAISE_APPLICATION_ERROR(-20007, 'Un medico internado no puede redactar comentarios sobre su propia internacion.');
   END IF;

   IF v_fecha_rec < v_ini_int OR (v_fin_int IS NOT NULL AND v_fecha_rec > v_fin_int) THEN
      RAISE_APPLICATION_ERROR(-20008, 'La fecha del recorrido del comentario cae fuera del periodo de la internacion.');
   END IF;

   SELECT COUNT(*) INTO v_hab_valida
   FROM ocupa o
   JOIN es_visitada ev ON ev.nro_habitacion = o.nro_habitacion
   WHERE o.id_internacion = :NEW.id_internacion
     AND ev.id_ronda = v_id_ronda
     AND v_fecha_rec >= o.fecha_asignacion_cama
     AND (o.fecha_terminacion_cama IS NULL OR v_fecha_rec <= o.fecha_terminacion_cama);

   IF v_hab_valida = 0 THEN
      RAISE_APPLICATION_ERROR(-20009, 'En la fecha del recorrido el paciente no ocupaba una habitacion incluida en la ronda.');
   END IF;
END;
/




-- 5. Validar OCUPA: fechas dentro de la internacion y no solapamiento de camas (Seccion 4.1 y 4.4)
CREATE OR REPLACE TRIGGER trg_validar_ocupa
FOR INSERT OR UPDATE ON ocupa
COMPOUND TRIGGER
   BEFORE EACH ROW IS
      v_ini_int internacion.fecha_inicio_internacion%TYPE;
      v_fin_int internacion.fecha_terminacion_internacion%TYPE;
   BEGIN
      SELECT fecha_inicio_internacion, fecha_terminacion_internacion
      INTO v_ini_int, v_fin_int
      FROM internacion
      WHERE id_internacion = :NEW.id_internacion;

      IF :NEW.fecha_asignacion_cama < v_ini_int OR
         (v_fin_int IS NOT NULL AND NVL(:NEW.fecha_terminacion_cama, :NEW.fecha_asignacion_cama) > v_fin_int) THEN
         RAISE_APPLICATION_ERROR(-20010, 'Las fechas de ocupacion de cama deben estar dentro del rango de la internacion.');
      END IF;
   END BEFORE EACH ROW;

   AFTER STATEMENT IS
      v_cama_solapada     NUMBER;
      v_paciente_solapado NUMBER;
   BEGIN
      -- Verificar que una misma cama no este asignada a dos pacientes en simultaneo
      SELECT COUNT(*) INTO v_cama_solapada
      FROM ocupa o1
      JOIN ocupa o2
        ON o1.nro_habitacion = o2.nro_habitacion
       AND o1.nro_cama = o2.nro_cama
       AND o1.ROWID <> o2.ROWID
       AND o1.fecha_asignacion_cama < NVL(o2.fecha_terminacion_cama, TIMESTAMP '9999-12-31 23:59:59')
       AND NVL(o1.fecha_terminacion_cama, TIMESTAMP '9999-12-31 23:59:59') > o2.fecha_asignacion_cama;

      IF v_cama_solapada > 0 THEN
         RAISE_APPLICATION_ERROR(-20011, 'La cama ya se encuentra ocupada en ese intervalo de tiempo.');
      END IF;

      -- Verificar que un mismo internado no tenga dos camas activas superpuestas
      SELECT COUNT(*) INTO v_paciente_solapado
      FROM ocupa o1
      JOIN ocupa o2
        ON o1.id_internacion = o2.id_internacion
       AND o1.ROWID <> o2.ROWID
       AND o1.fecha_asignacion_cama < NVL(o2.fecha_terminacion_cama, TIMESTAMP '9999-12-31 23:59:59')
       AND NVL(o1.fecha_terminacion_cama, TIMESTAMP '9999-12-31 23:59:59') > o2.fecha_asignacion_cama;

      IF v_paciente_solapado > 0 THEN
         RAISE_APPLICATION_ERROR(-20012, 'El paciente no puede ocupar mas de una cama simultaneamente.');
      END IF;
   END AFTER STATEMENT;
END trg_validar_ocupa;
/




-- 6. Validacion de RECORRIDO: el medico no puede hacer recorridos durante sus vacaciones (Seccion 4.4)
CREATE OR REPLACE TRIGGER trg_recorrido_no_vacaciones
BEFORE INSERT OR UPDATE ON recorrido
FOR EACH ROW
DECLARE
   v_en_vacaciones NUMBER;
BEGIN
   SELECT COUNT(*) INTO v_en_vacaciones
   FROM vacacion
   WHERE matricula_medico = :NEW.matricula_medico
     AND :NEW.fecha_recorrido BETWEEN fecha_inicio_vac AND fecha_fin_vac;

   IF v_en_vacaciones > 0 THEN
      RAISE_APPLICATION_ERROR(-20013, 'El medico no puede realizar un recorrido durante su periodo de vacaciones.');
   END IF;
END;
/

-- 7 
CREATE OR REPLACE TRIGGER trg_validar_cambio_guardia
FOR UPDATE OF fecha_inicio_guardia, fecha_fin_guardia ON guardia
COMPOUND TRIGGER

   TYPE t_guardias IS TABLE OF guardia.id_guardia%TYPE INDEX BY PLS_INTEGER;
   v_guardias t_guardias;
   v_idx      PLS_INTEGER := 0;

   AFTER EACH ROW IS
   BEGIN
      v_idx := v_idx + 1;
      v_guardias(v_idx) := :NEW.id_guardia;
   END AFTER EACH ROW;

   AFTER STATEMENT IS
      v_ini_guardia   guardia.fecha_inicio_guardia%TYPE;
      v_fin_guardia   guardia.fecha_fin_guardia%TYPE;
      v_en_vacaciones NUMBER;
      v_internado     NUMBER;
      v_cant_mes      NUMBER;
   BEGIN
      FOR i IN 1 .. v_idx LOOP
         SELECT fecha_inicio_guardia, fecha_fin_guardia
         INTO v_ini_guardia, v_fin_guardia
         FROM guardia
         WHERE id_guardia = v_guardias(i);

         -- Recorremos todos los medicos que ya tienen asignada esta guardia
         FOR r_med IN (
            SELECT DISTINCT d.matricula_medico, m.dni, m.cantidad_guardias
            FROM desempena d
            JOIN medico m ON m.matricula_medico = d.matricula_medico
            WHERE d.id_guardia = v_guardias(i)
         ) LOOP
            -- 1. Verificar vacaciones del medico
            SELECT COUNT(*) INTO v_en_vacaciones
            FROM vacacion
            WHERE matricula_medico = r_med.matricula_medico
              AND v_ini_guardia <= fecha_fin_vac
              AND v_fin_guardia >= fecha_inicio_vac;

            IF v_en_vacaciones > 0 THEN
               RAISE_APPLICATION_ERROR(-20003, 'El cambio de fecha de la guardia se superpone con vacaciones del medico ' || r_med.matricula_medico || '.');
            END IF;

            -- 2. Verificar internacion del medico como paciente
            SELECT COUNT(*) INTO v_internado
            FROM internacion
            WHERE dni = r_med.dni
              AND v_ini_guardia <= NVL(fecha_terminacion_internacion, TIMESTAMP '9999-12-31 23:59:59')
              AND v_fin_guardia >= fecha_inicio_internacion;

            IF v_internado > 0 THEN
               RAISE_APPLICATION_ERROR(-20004, 'El cambio de fecha de la guardia coincide con una internacion del medico ' || r_med.matricula_medico || '.');
            END IF;

            -- 3. Verificar tope mensual de guardias en el mes de la nueva fecha
            SELECT COUNT(*) INTO v_cant_mes
            FROM desempena d
            JOIN guardia g ON g.id_guardia = d.id_guardia
            WHERE d.matricula_medico = r_med.matricula_medico
              AND EXTRACT(YEAR FROM g.fecha_inicio_guardia) = EXTRACT(YEAR FROM v_ini_guardia)
              AND EXTRACT(MONTH FROM g.fecha_inicio_guardia) = EXTRACT(MONTH FROM v_ini_guardia);

            IF v_cant_mes > r_med.cantidad_guardias THEN
               RAISE_APPLICATION_ERROR(-20005, 'El cambio de mes hace que el medico ' || r_med.matricula_medico || ' supere su tope mensual de guardias.');
            END IF;
         END LOOP;
      END LOOP;
   END AFTER STATEMENT;

END trg_validar_cambio_guardia;
/
