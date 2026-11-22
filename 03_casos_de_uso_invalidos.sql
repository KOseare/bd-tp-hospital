-- -------------------------------------------------------------------------
-- CASO 1: Medico como su propio medico principal (Dispara ORA-20001)
-- Trigger: trg_internacion_medico_paciente (Restriccion 4.3)
-- Contexto: El Dr. Sergio Diaz tiene matricula 1004 y DNI '24444444'.
-- -------------------------------------------------------------------------
insert into internacion (
   id_internacion,
   fecha_inicio_internacion,
   fecha_terminacion_internacion,
   matricula_medico,
   dni
) values
   ( 90,
     timestamp '2026-11-05 08:00:00',
     null,
     1004,        -- Matricula del propio Dr. Diaz
     '24444444'   -- DNI del Dr. Diaz como paciente
      );