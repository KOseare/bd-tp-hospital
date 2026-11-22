-- =========================================================================
-- 04_triggers_restricciones.sql: Reglas de negocio de la Seccion 4
-- =========================================================================

-- 1. Un medico no puede ser su propio medico principal al internarse (Seccion 4.3)
create or replace trigger trg_internacion_medico_paciente before
   insert or update on internacion
   for each row
declare
   v_dni_medico medico.dni%type;
begin
   select dni
     into v_dni_medico
     from medico
    where matricula_medico = :new.matricula_medico;

   if v_dni_medico = :new.dni then
      raise_application_error(
         -20001,
         'Un medico no puede ser su propio medico principal durante su internacion.'
      );
   end if;
end;
/

-- 2. Validaciones integrales al asignar una guardia en DESEMPENA (Seccion 4.2):
--    a) Que en POSEE tenga hace_guardia = 'S'
--    b) Que la guardia no se solape con vacaciones del medico
--    c) Que el medico no este internado como paciente durante la guardia
--    d) Que no supere cantidad_guardias en ese mes calendario
create or replace trigger trg_validar_asignacion_guardia for
   insert or update on desempena
compound trigger
   type t_asignacion is record (
         matricula_medico desempena.matricula_medico%type,
         id_guardia       desempena.id_guardia%type
   );
   type t_asignaciones is
      table of t_asignacion index by pls_integer;
   v_asig t_asignaciones;
   v_idx  pls_integer := 0;

   -- 1. A nivel fila: validamos contra las OTRAS tablas (posee, medico, guardia, vacacion, internacion)
   before each row is
      v_hace_guardia  posee.hace_guardia%type;
      v_dni_medico    medico.dni%type;
      v_ini_guardia   guardia.fecha_inicio_guardia%type;
      v_fin_guardia   guardia.fecha_fin_guardia%type;
      v_en_vacaciones number;
      v_internado     number;
   begin
      select hace_guardia
        into v_hace_guardia
        from posee
       where matricula_medico = :new.matricula_medico
         and nombre_especialidad = :new.nombre_especialidad;

      if v_hace_guardia <> 'S' then
         raise_application_error(
            -20002,
            'El medico no esta dispuesto a hacer guardias en esa especialidad (hace_guardia <> S).'
         );
      end if;
      select dni
        into v_dni_medico
        from medico
       where matricula_medico = :new.matricula_medico;

      select fecha_inicio_guardia,
             fecha_fin_guardia
        into
         v_ini_guardia,
         v_fin_guardia
        from guardia
       where id_guardia = :new.id_guardia;

      select count(*)
        into v_en_vacaciones
        from vacacion
       where matricula_medico = :new.matricula_medico
         and v_ini_guardia <= fecha_fin_vac
         and v_fin_guardia >= fecha_inicio_vac;

      if v_en_vacaciones > 0 then
         raise_application_error(
            -20003,
            'El medico se encuentra de vacaciones durante el horario de la guardia.'
         );
      end if;
      select count(*)
        into v_internado
        from internacion
       where dni = v_dni_medico
         and v_ini_guardia <= nvl(
         fecha_terminacion_internacion,
         timestamp '9999-12-31 23:59:59'
      )
         and v_fin_guardia >= fecha_inicio_internacion;

      if v_internado > 0 then
         raise_application_error(
            -20004,
            'El medico figura internado como paciente durante el periodo de la guardia.'
         );
      end if;
      v_idx := v_idx + 1;
      v_asig(v_idx).matricula_medico := :new.matricula_medico;
      v_asig(v_idx).id_guardia := :new.id_guardia;
   end before each row;

   -- 2. Al terminar la sentencia: consultamos DESEMPENA sin riesgo de tabla mutante
   after statement is
      v_max_guardias medico.cantidad_guardias%type;
      v_ini_guardia  guardia.fecha_inicio_guardia%type;
      v_cant_mes     number;
   begin
      for i in 1..v_idx loop
         select cantidad_guardias
           into v_max_guardias
           from medico
          where matricula_medico = v_asig(i).matricula_medico;

         select fecha_inicio_guardia
           into v_ini_guardia
           from guardia
          where id_guardia = v_asig(i).id_guardia;

         select count(*)
           into v_cant_mes
           from desempena d
           join guardia g
         on g.id_guardia = d.id_guardia
          where d.matricula_medico = v_asig(i).matricula_medico
            and extract(year from g.fecha_inicio_guardia) = extract(year from v_ini_guardia)
            and extract(month from g.fecha_inicio_guardia) = extract(month from v_ini_guardia);

         if v_cant_mes > v_max_guardias then
            raise_application_error(
               -20005,
               'El medico supera el maximo de guardias mensuales que acepta realizar.'
            );
         end if;
      end loop;
   end after statement;
end trg_validar_asignacion_guardia;
/


-- 3. Evitar solapamiento de vacaciones de un mismo medico (Seccion 4.1)
--    Se usa COMPOUND TRIGGER para evitar ORA-04091 (tabla mutante) ante UPDATE o INSERT multiple
create or replace trigger trg_vacacion_no_solapa for
   insert or update on vacacion
compound trigger
   type t_matriculas is
      table of vacacion.matricula_medico%type index by pls_integer;
   v_matriculas t_matriculas;
   v_idx        pls_integer := 0;
   after each row is begin
      v_idx := v_idx + 1;
      v_matriculas(v_idx) := :new.matricula_medico;
   end after each row;
   after statement is
      v_solapadas number;
   begin
      for i in 1..v_idx loop
         select count(*)
           into v_solapadas
           from vacacion v1
           join vacacion v2
         on v1.matricula_medico = v2.matricula_medico
            and v1.rowid <> v2.rowid
            and v1.fecha_inicio_vac <= v2.fecha_fin_vac
            and v1.fecha_fin_vac >= v2.fecha_inicio_vac
          where v1.matricula_medico = v_matriculas(i);

         if v_solapadas > 0 then
            raise_application_error(
               -20006,
               'Las fechas de vacaciones se superponen con otro periodo del mismo medico.'
            );
         end if;
      end loop;
   end after statement;
end trg_vacacion_no_solapa;
/

-- 4. Validar COMENTARIO: que el paciente ocupe en la fecha del recorrido una
--    habitacion perteneciente a la ronda del recorrido, y que el medico no sea
--    el propio paciente (Secciones 2.1, 4.1 y 4.4)
create or replace trigger trg_validar_comentario before
   insert or update on comentario
   for each row
declare
   v_fecha_rec    recorrido.fecha_recorrido%type;
   v_id_ronda     recorrido.id_ronda%type;
   v_mat_medico   recorrido.matricula_medico%type;
   v_dni_medico   medico.dni%type;
   v_dni_paciente internacion.dni%type;
   v_ini_int      internacion.fecha_inicio_internacion%type;
   v_fin_int      internacion.fecha_terminacion_internacion%type;
   v_hab_valida   number;
begin
   select r.fecha_recorrido,
          r.id_ronda,
          r.matricula_medico,
          m.dni
     into
      v_fecha_rec,
      v_id_ronda,
      v_mat_medico,
      v_dni_medico
     from recorrido r
     join medico m
   on m.matricula_medico = r.matricula_medico
    where r.id_recorrido = :new.id_recorrido;

   select dni,
          fecha_inicio_internacion,
          fecha_terminacion_internacion
     into
      v_dni_paciente,
      v_ini_int,
      v_fin_int
     from internacion
    where id_internacion = :new.id_internacion;

   if v_dni_medico = v_dni_paciente then
      raise_application_error(
         -20007,
         'Un medico internado no puede redactar comentarios sobre su propia internacion.'
      );
   end if;
   if v_fecha_rec < v_ini_int
   or (
      v_fin_int is not null
      and v_fecha_rec > v_fin_int
   ) then
      raise_application_error(
         -20008,
         'La fecha del recorrido del comentario cae fuera del periodo de la internacion.'
      );
   end if;

   select count(*)
     into v_hab_valida
     from ocupa o
     join es_visitada ev
   on ev.nro_habitacion = o.nro_habitacion
    where o.id_internacion = :new.id_internacion
      and ev.id_ronda = v_id_ronda
      and v_fecha_rec >= o.fecha_asignacion_cama
      and ( o.fecha_terminacion_cama is null
       or v_fecha_rec <= o.fecha_terminacion_cama );

   if v_hab_valida = 0 then
      raise_application_error(
         -20009,
         'En la fecha del recorrido el paciente no ocupaba una habitacion incluida en la ronda.'
      );
   end if;
end;
/




-- 5. Validar OCUPA: fechas dentro de la internacion y no solapamiento de camas (Seccion 4.1 y 4.4)
create or replace trigger trg_validar_ocupa for
   insert or update on ocupa
compound trigger
   before each row is
      v_ini_int internacion.fecha_inicio_internacion%type;
      v_fin_int internacion.fecha_terminacion_internacion%type;
   begin
      select fecha_inicio_internacion,
             fecha_terminacion_internacion
        into
         v_ini_int,
         v_fin_int
        from internacion
       where id_internacion = :new.id_internacion;

      if :new.fecha_asignacion_cama < v_ini_int
      or (
         v_fin_int is not null
         and nvl(
            :new.fecha_terminacion_cama,
            :new.fecha_asignacion_cama
         ) > v_fin_int
      ) then
         raise_application_error(
            -20010,
            'Las fechas de ocupacion de cama deben estar dentro del rango de la internacion.'
         );
      end if;
   end before each row;
   after statement is
      v_cama_solapada     number;
      v_paciente_solapado number;
   begin
      -- Verificar que una misma cama no este asignada a dos pacientes en simultaneo
      select count(*)
        into v_cama_solapada
        from ocupa o1
        join ocupa o2
      on o1.nro_habitacion = o2.nro_habitacion
         and o1.nro_cama = o2.nro_cama
         and o1.rowid <> o2.rowid
         and o1.fecha_asignacion_cama < nvl(
         o2.fecha_terminacion_cama,
         timestamp '9999-12-31 23:59:59'
      )
         and nvl(
         o1.fecha_terminacion_cama,
         timestamp '9999-12-31 23:59:59'
      ) > o2.fecha_asignacion_cama;

      if v_cama_solapada > 0 then
         raise_application_error(
            -20011,
            'La cama ya se encuentra ocupada en ese intervalo de tiempo.'
         );
      end if;

      -- Verificar que un mismo internado no tenga dos camas activas superpuestas
      select count(*)
        into v_paciente_solapado
        from ocupa o1
        join ocupa o2
      on o1.id_internacion = o2.id_internacion
         and o1.rowid <> o2.rowid
         and o1.fecha_asignacion_cama < nvl(
         o2.fecha_terminacion_cama,
         timestamp '9999-12-31 23:59:59'
      )
         and nvl(
         o1.fecha_terminacion_cama,
         timestamp '9999-12-31 23:59:59'
      ) > o2.fecha_asignacion_cama;

      if v_paciente_solapado > 0 then
         raise_application_error(
            -20012,
            'El paciente no puede ocupar mas de una cama simultaneamente.'
         );
      end if;
   end after statement;
end trg_validar_ocupa;
/




-- 6. Validacion de RECORRIDO: el medico no puede hacer recorridos durante sus vacaciones (Seccion 4.4)
create or replace trigger trg_recorrido_no_vacaciones before
   insert or update on recorrido
   for each row
declare
   v_en_vacaciones number;
begin
   select count(*)
     into v_en_vacaciones
     from vacacion
    where matricula_medico = :new.matricula_medico
      and :new.fecha_recorrido between fecha_inicio_vac and fecha_fin_vac;

   if v_en_vacaciones > 0 then
      raise_application_error(
         -20013,
         'El medico no puede realizar un recorrido durante su periodo de vacaciones.'
      );
   end if;
end;
/

-- 7 
create or replace trigger trg_validar_cambio_guardia for
   update of fecha_inicio_guardia,fecha_fin_guardia on guardia
compound trigger
   type t_guardias is
      table of guardia.id_guardia%type index by pls_integer;
   v_guardias t_guardias;
   v_idx      pls_integer := 0;
   after each row is begin
      v_idx := v_idx + 1;
      v_guardias(v_idx) := :new.id_guardia;
   end after each row;
   after statement is
      v_ini_guardia   guardia.fecha_inicio_guardia%type;
      v_fin_guardia   guardia.fecha_fin_guardia%type;
      v_en_vacaciones number;
      v_internado     number;
      v_cant_mes      number;
   begin
      for i in 1..v_idx loop
         select fecha_inicio_guardia,
                fecha_fin_guardia
           into
            v_ini_guardia,
            v_fin_guardia
           from guardia
          where id_guardia = v_guardias(i);

         -- Recorremos todos los medicos que ya tienen asignada esta guardia
         for r_med in (
            select distinct d.matricula_medico,
                            m.dni,
                            m.cantidad_guardias
              from desempena d
              join medico m
            on m.matricula_medico = d.matricula_medico
             where d.id_guardia = v_guardias(i)
         ) loop
            -- 1. Verificar vacaciones del medico
            select count(*)
              into v_en_vacaciones
              from vacacion
             where matricula_medico = r_med.matricula_medico
               and v_ini_guardia <= fecha_fin_vac
               and v_fin_guardia >= fecha_inicio_vac;

            if v_en_vacaciones > 0 then
               raise_application_error(
                  -20003,
                  'El cambio de fecha de la guardia se superpone con vacaciones del medico '
                  || r_med.matricula_medico
                  || '.'
               );
            end if;

            -- 2. Verificar internacion del medico como paciente
            select count(*)
              into v_internado
              from internacion
             where dni = r_med.dni
               and v_ini_guardia <= nvl(
               fecha_terminacion_internacion,
               timestamp '9999-12-31 23:59:59'
            )
               and v_fin_guardia >= fecha_inicio_internacion;

            if v_internado > 0 then
               raise_application_error(
                  -20004,
                  'El cambio de fecha de la guardia coincide con una internacion del medico '
                  || r_med.matricula_medico
                  || '.'
               );
            end if;

            -- 3. Verificar tope mensual de guardias en el mes de la nueva fecha
            select count(*)
              into v_cant_mes
              from desempena d
              join guardia g
            on g.id_guardia = d.id_guardia
             where d.matricula_medico = r_med.matricula_medico
               and extract(year from g.fecha_inicio_guardia) = extract(year from v_ini_guardia)
               and extract(month from g.fecha_inicio_guardia) = extract(month from v_ini_guardia);

            if v_cant_mes > r_med.cantidad_guardias then
               raise_application_error(
                  -20005,
                  'El cambio de mes hace que el medico '
                  || r_med.matricula_medico
                  || ' supere su tope mensual de guardias.'
               );
            end if;
         end loop;
      end loop;
   end after statement;
end trg_validar_cambio_guardia;
/