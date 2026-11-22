alter session set container = xepdb1;

create user tp_hospital identified by potentia
   default tablespace users
   quota unlimited on users;

grant connect,resource,
   create view,
   create trigger,
   create sequence
to tp_hospital;