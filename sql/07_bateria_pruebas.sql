-- =============================================================================
-- 07_bateria_pruebas.sql
-- Bateria de pruebas completa del TP Hospital (Procedures, Auditorias, Triggers
-- ORA-20001..ORA-20013 y Atomicidad Transaccional).
--
-- Precondicion: haber ejecutado 01_1tablas_ddl.sql, 01_2_auditorias.sql,
--               05_procedures.sql, 06_triggers.sql y 02_inserts.sql.
--
-- Caracteristica clave: CADA bloque usa SAVEPOINT + ROLLBACK al finalizar, por
-- lo que la base queda intacta y podes correr bloque por bloque (Ctrl+Enter) o
-- el script entero (F5) todas las veces que necesites durante la defensa.
-- =============================================================================

SET SERVEROUTPUT ON SIZE UNLIMITED;

-- =============================================================================
-- 1. PROCEDURE pr_camas_disponibles (Caso OK + Caso FALLA cama inexistente)
-- =============================================================================
DECLARE
   c_cant          SYS_REFCURSOR;
   c_det           SYS_REFCURSOR;
   v_sector        sector.nombre_sector%TYPE;
   v_cant          NUMBER;
   v_hab           habitacion.nro_habitacion%TYPE;
   v_piso          habitacion.piso%TYPE;
   v_ori           habitacion.orientacion%TYPE;
   v_cama          cama.nro_cama%TYPE;
   v_total_antes   NUMBER := 0;
   v_total_despues NUMBER := 0;
   v_pediatria_0   BOOLEAN := FALSE;
   v_hab_libre     habitacion.nro_habitacion%TYPE;
   v_cama_libre    cama.nro_cama%TYPE;
   v_id_int        internacion.id_internacion%TYPE;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 1. PROCEDURE pr_camas_disponibles ===');
   SAVEPOINT sp_test;

   -- Caso OK: listar disponibilidad, verificar sector con 0 camas y baja al ocupar 1 cama
   pr_camas_disponibles(c_cant, c_det);
   LOOP
      FETCH c_cant INTO v_sector, v_cant;
      EXIT WHEN c_cant%NOTFOUND;
      v_total_antes := v_total_antes + v_cant;
      IF v_sector = 'Pediatria' AND v_cant = 0 THEN
         v_pediatria_0 := TRUE;
      END IF;
   END LOOP;
   CLOSE c_cant;

   FETCH c_det INTO v_sector, v_hab_libre, v_piso, v_ori, v_cama_libre;
   CLOSE c_det;

   INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
   VALUES (SYSTIMESTAMP - INTERVAL '1' MINUTE, NULL, 1001, '30333333')
   RETURNING id_internacion INTO v_id_int;

   INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama, fecha_terminacion_cama)
   VALUES (v_id_int, SYSTIMESTAMP - INTERVAL '1' MINUTE, v_hab_libre, v_cama_libre, NULL);

   pr_camas_disponibles(c_cant, c_det);
   LOOP
      FETCH c_cant INTO v_sector, v_cant;
      EXIT WHEN c_cant%NOTFOUND;
      v_total_despues := v_total_despues + v_cant;
   END LOOP;
   CLOSE c_cant;
   CLOSE c_det;

   IF v_pediatria_0 AND v_total_despues = v_total_antes - 1 THEN
      DBMS_OUTPUT.PUT_LINE('[PASS] 1A (OK): Pediatria=0 camas; al ocupar Hab ' || v_hab_libre ||
                           '-Cama ' || v_cama_libre || ' el total bajo de ' || v_total_antes ||
                           ' a ' || v_total_despues || '.');
   ELSE
      DBMS_OUTPUT.PUT_LINE('[FAIL] 1A (OK): total antes=' || v_total_antes || ', despues=' || v_total_despues);
   END IF;

   ROLLBACK TO sp_test;

   -- Caso FALLA: intentar ocupar cama 102-3 (no existe: hab 102 tiene camas 1, 2 y 4)
   BEGIN
      INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
      VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1001, '30333333')
      RETURNING id_internacion INTO v_id_int;

      INSERT INTO ocupa (id_internacion, fecha_asignacion_cama, nro_habitacion, nro_cama, fecha_terminacion_cama)
      VALUES (v_id_int, TIMESTAMP '2028-01-10 09:00:00', 102, 3, NULL);

      DBMS_OUTPUT.PUT_LINE('[FAIL] 1B (FALLA esperada): permitio ocupar cama inexistente 102-3.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -2291 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 1B (FALLA esperada ORA-02291): rechazo cama inexistente 102-3.');
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 1B: error inesperado ' || SQLERRM);
         END IF;
   END;

   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 2. PROCEDURE pr_comentarios_internacion (DNI correcto vs DNI ajeno)
-- =============================================================================
DECLARE
   c_com      SYS_REFCURSOR;
   v_fecha    recorrido.fecha_recorrido%TYPE;
   v_turno    ronda.turno_ronda%TYPE;
   v_ape      persona.apellido%TYPE;
   v_nom      persona.nombre%TYPE;
   v_txt      comentario.texto_comentario%TYPE;
   v_cnt_ok   NUMBER := 0;
   v_cnt_fail NUMBER := 0;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 2. PROCEDURE pr_comentarios_internacion ===');

   -- Caso OK: internacion 1 pertenece a Ana Lopez (DNI 30111111) -> debe devolver 2 comentarios
   pr_comentarios_internacion(1, '30111111', c_com);
   LOOP
      FETCH c_com INTO v_fecha, v_turno, v_ape, v_nom, v_txt;
      EXIT WHEN c_com%NOTFOUND;
      v_cnt_ok := v_cnt_ok + 1;
   END LOOP;
   CLOSE c_com;

   IF v_cnt_ok >= 2 THEN
      DBMS_OUTPUT.PUT_LINE('[PASS] 2A (OK): internacion 1 + DNI 30111111 devolvio ' || v_cnt_ok || ' comentarios.');
   ELSE
      DBMS_OUTPUT.PUT_LINE('[FAIL] 2A (OK): esperaba >= 2 comentarios, devolvio ' || v_cnt_ok);
   END IF;

   -- Caso FALLA / seguridad: internacion 1 con DNI de otro paciente (30222222) -> 0 filas
   pr_comentarios_internacion(1, '30222222', c_com);
   LOOP
      FETCH c_com INTO v_fecha, v_turno, v_ape, v_nom, v_txt;
      EXIT WHEN c_com%NOTFOUND;
      v_cnt_fail := v_cnt_fail + 1;
   END LOOP;
   CLOSE c_com;

   IF v_cnt_fail = 0 THEN
      DBMS_OUTPUT.PUT_LINE('[PASS] 2B (DNI ajeno): internacion 1 + DNI 30222222 devolvio 0 filas.');
   ELSE
      DBMS_OUTPUT.PUT_LINE('[FAIL] 2B (DNI ajeno): devolvio ' || v_cnt_fail || ' filas y debia devolver 0.');
   END IF;
END;
/

-- =============================================================================
-- 3. AUDITORIA DE GUARDIAS (5 triggers OK + Atomicidad ROLLBACK ante falla)
-- =============================================================================
DECLARE
   v_aud_antes   NUMBER;
   v_aud_despues NUMBER;
   v_g_antes     NUMBER;
   v_g_despues   NUMBER;
   v_id_g        guardia.id_guardia%TYPE;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 3. AUDITORIA DE GUARDIAS (01_2_auditorias.sql) ===');
   SAVEPOINT sp_test;

   SELECT COUNT(*) INTO v_aud_antes FROM auditoria_guardias;

   -- Caso OK: 1 cambio en cada una de las 5 tablas auditadas
   UPDATE medico SET cantidad_guardias = cantidad_guardias + 1 WHERE matricula_medico = 1002;
   UPDATE posee SET hace_guardia = 'S' WHERE matricula_medico = 1001 AND nombre_especialidad = 'Cardiologia';
   INSERT INTO vacacion VALUES (1003, TIMESTAMP '2028-03-01 00:00:00', TIMESTAMP '2028-03-10 23:59:59');
   INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
   VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
   RETURNING id_guardia INTO v_id_g;
   INSERT INTO desempena VALUES (1002, 'Cardiologia', v_id_g);

   SELECT COUNT(*) INTO v_aud_despues FROM auditoria_guardias;

   IF v_aud_despues = v_aud_antes + 5 THEN
      DBMS_OUTPUT.PUT_LINE('[PASS] 3A (OK): se registraron 5 eventos en auditoria_guardias (MEDICO, POSEE, VACACION, GUARDIA, DESEMPENA).');
   ELSE
      DBMS_OUTPUT.PUT_LINE('[FAIL] 3A (OK): esperaba +5 filas, se registraron +' || (v_aud_despues - v_aud_antes));
   END IF;

   ROLLBACK TO sp_test;

   -- Caso FALLA + ROLLBACK: falla DESEMPENA (ORA-20003) -> se revierte GUARDIA y su auditoria
   SELECT COUNT(*) INTO v_aud_antes FROM auditoria_guardias;
   SELECT COUNT(*) INTO v_g_antes FROM guardia;

   SAVEPOINT sp_tx;
   BEGIN
      INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
      VALUES (TIMESTAMP '2026-11-25 06:00:00', TIMESTAMP '2026-11-25 14:00:00')
      RETURNING id_guardia INTO v_id_g;

      -- 1001 esta de vacaciones el 2026-11-25 -> falla ORA-20003
      INSERT INTO desempena VALUES (1001, 'Clinica Medica', v_id_g);
      DBMS_OUTPUT.PUT_LINE('[FAIL] 3B: no disparo ORA-20003.');
   EXCEPTION
      WHEN OTHERS THEN
         ROLLBACK TO sp_tx;
         SELECT COUNT(*) INTO v_aud_despues FROM auditoria_guardias;
         SELECT COUNT(*) INTO v_g_despues FROM guardia;
         IF SQLCODE = -20003 AND v_aud_despues = v_aud_antes AND v_g_despues = v_g_antes THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 3B (FALLA + ROLLBACK ORA-20003): revirtio GUARDIA y auditoria sin dejar huerfanos.');
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 3B: code=' || SQLCODE || ', aud=' || v_aud_antes || '->' || v_aud_despues);
         END IF;
   END;

   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 4. TRIGGER trg_internacion_medico_paciente (ORA-20001)
-- =============================================================================
DECLARE
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 4. TRIGGER trg_internacion_medico_paciente ===');
   SAVEPOINT sp_test;

   -- Caso OK: Dr. Diaz (DNI 24444444) internado con OTRO medico principal (1001)
   INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
   VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1001, '24444444');
   DBMS_OUTPUT.PUT_LINE('[PASS] 4A (OK): medico internado atendido por otro medico (1001).');
   ROLLBACK TO sp_test;

   -- Caso FALLA: Dr. Diaz (DNI 24444444) como su propio medico principal (1004)
   BEGIN
      INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
      VALUES (TIMESTAMP '2028-01-10 08:00:00', NULL, 1004, '24444444');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 4B: permitio que un medico sea su propio medico principal.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20001 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 4B (FALLA esperada ORA-20001): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 4B: error inesperado ' || SQLERRM);
         END IF;
   END;

   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 5. TRIGGER trg_validar_asignacion_guardia (ORA-20002, -20003, -20004, -20005)
-- =============================================================================
DECLARE
   v_id_g guardia.id_guardia%TYPE;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 5. TRIGGER trg_validar_asignacion_guardia ===');
   SAVEPOINT sp_test;

   -- 5A. Caso OK: medico 1002 en Cardiologia ('S'), fecha libre en 2028
   INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
   VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
   RETURNING id_guardia INTO v_id_g;
   INSERT INTO desempena VALUES (1002, 'Cardiologia', v_id_g);
   DBMS_OUTPUT.PUT_LINE('[PASS] 5A (OK): guardia asignada correctamente a medico 1002.');
   ROLLBACK TO sp_test;

   -- 5B. FALLA ORA-20002: hace_guardia = 'N' (1001 tiene Cardiologia con 'N')
   BEGIN
      INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
      VALUES (TIMESTAMP '2028-05-10 06:00:00', TIMESTAMP '2028-05-10 14:00:00')
      RETURNING id_guardia INTO v_id_g;
      INSERT INTO desempena VALUES (1001, 'Cardiologia', v_id_g);
      DBMS_OUTPUT.PUT_LINE('[FAIL] 5B: permitio asignar guardia con hace_guardia = N.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20002 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 5B (FALLA esperada ORA-20002): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 5B: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 5C. FALLA ORA-20003: medico 1001 de vacaciones (2026-11-20..2026-12-04)
   BEGIN
      INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
      VALUES (TIMESTAMP '2026-11-25 06:00:00', TIMESTAMP '2026-11-25 14:00:00')
      RETURNING id_guardia INTO v_id_g;
      INSERT INTO desempena VALUES (1001, 'Clinica Medica', v_id_g);
      DBMS_OUTPUT.PUT_LINE('[FAIL] 5C: permitio asignar guardia durante vacaciones.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20003 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 5C (FALLA esperada ORA-20003): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 5C: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 5D. FALLA ORA-20004: medico 1004 internado como paciente (I5: 2026-10-10..2026-10-20)
   BEGIN
      INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
      VALUES (TIMESTAMP '2026-10-15 06:00:00', TIMESTAMP '2026-10-15 14:00:00')
      RETURNING id_guardia INTO v_id_g;
      INSERT INTO desempena VALUES (1004, 'Clinica Medica', v_id_g);
      DBMS_OUTPUT.PUT_LINE('[FAIL] 5D: permitio asignar guardia a medico internado.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20004 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 5D (FALLA esperada ORA-20004): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 5D: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 5E. FALLA ORA-20005: medico 1004 supera tope mensual (max=2, ya tiene 2 en nov 2026)
   BEGIN
      INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
      VALUES (TIMESTAMP '2026-11-15 06:00:00', TIMESTAMP '2026-11-15 14:00:00')
      RETURNING id_guardia INTO v_id_g;
      INSERT INTO desempena VALUES (1004, 'Clinica Medica', v_id_g);
      DBMS_OUTPUT.PUT_LINE('[FAIL] 5E: permitio superar tope mensual de guardias.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20005 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 5E (FALLA esperada ORA-20005): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 5E: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 6. TRIGGER trg_vacacion_no_solapa (ORA-20006)
-- =============================================================================
DECLARE
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 6. TRIGGER trg_vacacion_no_solapa ===');
   SAVEPOINT sp_test;

   -- Caso OK: periodo libre para medico 1003
   INSERT INTO vacacion VALUES (1003, TIMESTAMP '2028-03-01 00:00:00', TIMESTAMP '2028-03-15 23:59:59');
   DBMS_OUTPUT.PUT_LINE('[PASS] 6A (OK): periodo de vacaciones sin superposicion aceptado.');
   ROLLBACK TO sp_test;

   -- Caso FALLA: se superpone con 2026-11-20..2026-12-04 de 1001
   BEGIN
      INSERT INTO vacacion VALUES (1001, TIMESTAMP '2026-11-25 00:00:00', TIMESTAMP '2026-12-10 23:59:59');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 6B: permitio vacaciones superpuestas.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20006 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 6B (FALLA esperada ORA-20006): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 6B: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 7. TRIGGER trg_validar_comentario (ORA-20007, -20008, -20009)
-- =============================================================================
DECLARE
   v_rec recorrido.id_recorrido%TYPE;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 7. TRIGGER trg_validar_comentario ===');
   SAVEPOINT sp_test;

   -- 7A. Caso OK: I1 (hab 101-1 el 2026-10-20 16:00) + recorrido 2 (ronda 1 visita 101, med 1001)
   INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
   VALUES (1, 2, 'Comentario valido de prueba.');
   DBMS_OUTPUT.PUT_LINE('[PASS] 7A (OK): comentario valido registrado correctamente.');
   ROLLBACK TO sp_test;

   -- 7B. FALLA ORA-20007: medico 1004 comenta sobre su propia internacion (I5, DNI 24444444)
   BEGIN
      INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido)
      VALUES (2, 1004, TIMESTAMP '2026-10-15 10:00:00')
      RETURNING id_recorrido INTO v_rec;

      INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
      VALUES (5, v_rec, 'Auto-comentario prohibido.');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 7B: permitio auto-comentario de medico internado.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20007 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 7B (FALLA esperada ORA-20007): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 7B: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 7C. FALLA ORA-20008: fecha del recorrido (2026-10-20) fuera de I3 (2026-10-01..2026-10-08)
   BEGIN
      INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
      VALUES (3, 2, 'Comentario fuera del periodo de internacion.');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 7C: permitio comentario fuera del periodo de internacion.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20008 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 7C (FALLA esperada ORA-20008): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 7C: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 7D. FALLA ORA-20009: el 2026-10-21 I1 estaba en hab 101, pero recorrido 3 (ronda 2) visita 301/302
   BEGIN
      INSERT INTO comentario (id_internacion, id_recorrido, texto_comentario)
      VALUES (1, 3, 'Habitacion fuera de la ronda del recorrido.');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 7D: permitio comentario en habitacion fuera de la ronda.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20009 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 7D (FALLA esperada ORA-20009): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 7D: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 8. TRIGGER trg_validar_ocupa (ORA-20010, -20011, -20012)
-- =============================================================================
DECLARE
   v_int internacion.id_internacion%TYPE;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 8. TRIGGER trg_validar_ocupa ===');
   SAVEPOINT sp_test;

   -- 8A. Caso OK: cambio de cama y repeticion de cama dentro del rango de la internacion
   INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
   VALUES (TIMESTAMP '2028-02-01 08:00:00', TIMESTAMP '2028-02-10 12:00:00', 1001, '30333333')
   RETURNING id_internacion INTO v_int;

   INSERT INTO ocupa VALUES (v_int, TIMESTAMP '2028-02-01 08:00:00', 101, 1, TIMESTAMP '2028-02-04 10:00:00');
   INSERT INTO ocupa VALUES (v_int, TIMESTAMP '2028-02-04 10:00:00', 101, 2, TIMESTAMP '2028-02-07 10:00:00');
   INSERT INTO ocupa VALUES (v_int, TIMESTAMP '2028-02-07 10:00:00', 101, 1, TIMESTAMP '2028-02-10 12:00:00');
   DBMS_OUTPUT.PUT_LINE('[PASS] 8A (OK): asignacion, cambio y repeticion de cama dentro de la internacion.');
   ROLLBACK TO sp_test;

   -- 8B. FALLA ORA-20010: ocupacion anterior al inicio de I4 (inicio I4: 2026-09-10 09:00)
   BEGIN
      INSERT INTO ocupa VALUES (4, TIMESTAMP '2026-09-09 08:00:00', 201, 2, TIMESTAMP '2026-09-10 08:00:00');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 8B: permitio ocupacion fuera del rango de la internacion.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20010 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 8B (FALLA esperada ORA-20010): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 8B: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 8C. FALLA ORA-20011: cama 302-1 ya ocupada por I5 (2026-10-10 09:00..2026-10-20 12:00)
   BEGIN
      INSERT INTO internacion (fecha_inicio_internacion, fecha_terminacion_internacion, matricula_medico, dni)
      VALUES (TIMESTAMP '2026-10-12 08:00:00', TIMESTAMP '2026-10-15 12:00:00', 1002, '30444444')
      RETURNING id_internacion INTO v_int;

      INSERT INTO ocupa VALUES (v_int, TIMESTAMP '2026-10-12 09:00:00', 302, 1, TIMESTAMP '2026-10-15 12:00:00');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 8C: permitio superponer dos pacientes en la misma cama.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20011 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 8C (FALLA esperada ORA-20011): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 8C: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 8D. FALLA ORA-20012: I4 ya ocupa 201-1 (09-10..09-15), intento asignarle tambien 201-2 en 09-11..09-12
   BEGIN
      INSERT INTO ocupa VALUES (4, TIMESTAMP '2026-09-11 09:00:00', 201, 2, TIMESTAMP '2026-09-12 09:00:00');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 8D: permitio dos camas simultaneas para la misma internacion.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20012 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 8D (FALLA esperada ORA-20012): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 8D: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 9. TRIGGER trg_recorrido_no_vacaciones (ORA-20013)
-- =============================================================================
DECLARE
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 9. TRIGGER trg_recorrido_no_vacaciones ===');
   SAVEPOINT sp_test;

   -- Caso OK: medico 1001 fuera de vacaciones (2026-11-10)
   INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido)
   VALUES (1, 1001, TIMESTAMP '2026-11-10 10:00:00');
   DBMS_OUTPUT.PUT_LINE('[PASS] 9A (OK): recorrido fuera de vacaciones aceptado.');
   ROLLBACK TO sp_test;

   -- Caso FALLA: medico 1001 durante vacaciones (2026-11-25)
   BEGIN
      INSERT INTO recorrido (id_ronda, matricula_medico, fecha_recorrido)
      VALUES (1, 1001, TIMESTAMP '2026-11-25 10:00:00');
      DBMS_OUTPUT.PUT_LINE('[FAIL] 9B: permitio recorrido durante vacaciones.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20013 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 9B (FALLA esperada ORA-20013): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 9B: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;
END;
/

-- =============================================================================
-- 10. TRIGGER trg_validar_cambio_guardia (UPDATE guardia -> ORA-20003/04/05)
-- =============================================================================
DECLARE
   v_id_g guardia.id_guardia%TYPE;
BEGIN
   DBMS_OUTPUT.PUT_LINE('=== 10. TRIGGER trg_validar_cambio_guardia ===');
   SAVEPOINT sp_test;

   -- 10A. Caso OK: mover guardia 1 (medico 1001) a otra fecha libre del mismo mes (2026-11-12)
   UPDATE guardia
      SET fecha_inicio_guardia = TIMESTAMP '2026-11-12 06:00:00',
          fecha_fin_guardia    = TIMESTAMP '2026-11-12 14:00:00'
    WHERE id_guardia = 1;
   DBMS_OUTPUT.PUT_LINE('[PASS] 10A (OK): reprogramacion de guardia a fecha valida aceptada.');
   ROLLBACK TO sp_test;

   -- 10B. FALLA ORA-20003: mover guardia 1 (medico 1001) a vacaciones (2026-11-25)
   BEGIN
      UPDATE guardia
         SET fecha_inicio_guardia = TIMESTAMP '2026-11-25 06:00:00',
             fecha_fin_guardia    = TIMESTAMP '2026-11-25 14:00:00'
       WHERE id_guardia = 1;
      DBMS_OUTPUT.PUT_LINE('[FAIL] 10B: permitio mover guardia a vacaciones.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20003 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 10B (FALLA esperada ORA-20003): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 10B: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 10C. FALLA ORA-20004: mover guardia 2 (asignada a 1004) a fecha de internacion de 1004 (2026-10-15)
   BEGIN
      UPDATE guardia
         SET fecha_inicio_guardia = TIMESTAMP '2026-10-15 14:00:00',
             fecha_fin_guardia    = TIMESTAMP '2026-10-15 22:00:00'
       WHERE id_guardia = 2;
      DBMS_OUTPUT.PUT_LINE('[FAIL] 10C: permitio mover guardia a fecha de internacion.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20004 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 10C (FALLA esperada ORA-20004): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 10C: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;

   -- 10D. FALLA ORA-20005: crear guardia en 2028-06 para 1004 y moverla a nov 2026 (supera tope=2)
   BEGIN
      INSERT INTO guardia (fecha_inicio_guardia, fecha_fin_guardia)
      VALUES (TIMESTAMP '2028-06-05 06:00:00', TIMESTAMP '2028-06-05 14:00:00')
      RETURNING id_guardia INTO v_id_g;
      INSERT INTO desempena VALUES (1004, 'Clinica Medica', v_id_g);

      UPDATE guardia
         SET fecha_inicio_guardia = TIMESTAMP '2026-11-15 06:00:00',
             fecha_fin_guardia    = TIMESTAMP '2026-11-15 14:00:00'
       WHERE id_guardia = v_id_g;
      DBMS_OUTPUT.PUT_LINE('[FAIL] 10D: permitio mover guardia a un mes donde supera tope.');
   EXCEPTION
      WHEN OTHERS THEN
         IF SQLCODE = -20005 THEN
            DBMS_OUTPUT.PUT_LINE('[PASS] 10D (FALLA esperada ORA-20005): ' || SUBSTR(SQLERRM, 1, 120));
         ELSE
            DBMS_OUTPUT.PUT_LINE('[FAIL] 10D: error inesperado ' || SQLERRM);
         END IF;
   END;
   ROLLBACK TO sp_test;
END;
/
