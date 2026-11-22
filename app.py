"""App del hospital (tkinter + Oracle).

Antes de correr:
    pip install oracledb
    set HOSPITAL_USER=...  HOSPITAL_PASSWORD=...  HOSPITAL_DSN=localhost:1521/XEPDB1
    (en Linux/Mac: export en lugar de set)
"""
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

import oracledb

import db
import pruebas


# ---------------------------------------------------------------------------
# Helpers de UI
# ---------------------------------------------------------------------------
def ejecutar(accion, mensaje_ok=None, despues=None):
    """Corre accion() mostrando los errores; si sale bien avisa y refresca."""
    try:
        resultado = accion()
    except db.ErrorTrigger as e:
        messagebox.showwarning(f"Regla de negocio (ORA-{e.codigo})", str(e))
        return None
    except db.ReglaError as e:
        messagebox.showwarning("No se pudo completar", str(e))
        return None
    except ValueError as e:
        messagebox.showwarning("Dato inválido", str(e))
        return None
    except oracledb.Error as e:
        messagebox.showerror("Error de base de datos", str(e))
        return None
    if mensaje_ok:
        messagebox.showinfo("Listo", mensaje_ok)
    if despues:
        despues()
    return resultado if resultado is not None else True


def parsear_fecha(texto, nombre):
    try:
        return datetime.strptime(texto.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{nombre}: usá el formato AAAA-MM-DD (ej. 2026-11-21).")


def parsear_entero(texto, nombre):
    try:
        return int(texto.strip())
    except ValueError:
        raise ValueError(f"{nombre}: tiene que ser un número entero.")


def campo(parent, fila, texto, ancho=30):
    ttk.Label(parent, text=texto).grid(row=fila, column=0, sticky="e", padx=6, pady=3)
    entrada = ttk.Entry(parent, width=ancho)
    entrada.grid(row=fila, column=1, sticky="w", pady=3)
    return entrada


def combo(parent, fila, texto, ancho=45, solo_lectura=True):
    ttk.Label(parent, text=texto).grid(row=fila, column=0, sticky="e", padx=6, pady=3)
    cb = ttk.Combobox(parent, width=ancho, state="readonly" if solo_lectura else "normal")
    cb.grid(row=fila, column=1, sticky="w", pady=3)
    cb.mapa = {}
    return cb


def cargar_combo(cb, items):
    """items: lista de (texto_visible, valor)."""
    cb.mapa = dict(items)
    cb["values"] = [texto for texto, _ in items]
    if cb.get() not in cb.mapa:
        cb.set("")


def valor_combo(cb, nombre):
    if cb.get() not in cb.mapa:
        raise db.ReglaError(f"Elegí una opción en: {nombre}.")
    return cb.mapa[cb.get()]


def crear_tabla(parent, columnas, ancho=140, **pack):
    tabla = ttk.Treeview(parent, columns=columnas, show="headings", height=8)
    for c in columnas:
        tabla.heading(c, text=c)
        tabla.column(c, width=ancho)
    pack.setdefault("expand", True)
    pack.setdefault("fill", "both")
    tabla.pack(**pack)
    return tabla


def _texto(v):
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    return v


def llenar(tabla, filas):
    tabla.delete(*tabla.get_children())
    for fila in filas:
        tabla.insert("", "end", values=tuple(_texto(v) for v in fila))


def fila_seleccionada(tabla, mensaje):
    sel = tabla.selection()
    if not sel:
        raise db.ReglaError(mensaje)
    return tabla.item(sel[0])["values"]


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        root.title("Hospital - Gestión")
        root.geometry("1150x700")
        self.nb = ttk.Notebook(root)
        self.nb.pack(expand=True, fill="both")

        self._tab_camas()
        self._tab_comentarios()
        self._tab_pacientes()
        self._tab_medicos()
        self._tab_internaciones()
        self._tab_guardias()
        self._tab_auditoria()
        self._tab_pruebas()
        self.refrescar_todo()

    # ----- Camas disponibles -------------------------------------------------
    def _tab_camas(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Camas disponibles")
        ttk.Button(tab, text="Refrescar", command=lambda: ejecutar(self.refrescar_camas)).pack(pady=5)
        sub = ttk.Notebook(tab)
        sub.pack(expand=True, fill="both")
        f1, f2 = ttk.Frame(sub), ttk.Frame(sub)
        sub.add(f1, text="Resumen por sector")
        sub.add(f2, text="Detalle")
        self.t_resumen = crear_tabla(f1, ("sector", "camas_disponibles"), 250)
        self.t_detalle = crear_tabla(
            f2, ("sector", "habitacion", "piso", "orientacion", "cama"), 150)

    def refrescar_camas(self):
        resumen, detalle = db.camas_disponibles()
        llenar(self.t_resumen, resumen)
        llenar(self.t_detalle, detalle)

    # ----- Comentarios por internación --------------------------------------
    def _tab_comentarios(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Comentarios")
        form = ttk.Frame(tab)
        form.pack(pady=8)
        self.e_com_int = campo(form, 0, "ID de internación:", 12)
        self.e_com_dni = campo(form, 1, "DNI del paciente:", 12)
        ttk.Button(form, text="Buscar comentarios", command=self.buscar_comentarios
                   ).grid(row=2, column=0, columnspan=2, pady=6)
        self.t_coment = crear_tabla(
            tab, ("fecha_recorrido", "turno", "apellido", "nombre", "comentario"), 200)

    def buscar_comentarios(self):
        def accion():
            id_int = parsear_entero(self.e_com_int.get(), "ID de internación")
            dni = self.e_com_dni.get().strip()
            filas = db.comentarios_internacion(id_int, dni)
            llenar(self.t_coment, filas)
            if not filas:
                messagebox.showinfo("Sin resultados",
                                    "No hay comentarios (o la internación no es de ese paciente).")
        ejecutar(accion)

    # ----- Pacientes ----------------------------------------------------------
    def _tab_pacientes(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Pacientes")
        form = ttk.LabelFrame(tab, text="Alta de paciente")
        form.pack(fill="x", padx=10, pady=8)
        self.p_dni = campo(form, 0, "DNI:", 15)
        self.p_nombre = campo(form, 1, "Nombre:")
        self.p_apellido = campo(form, 2, "Apellido:")
        self.p_nac = campo(form, 3, "Fecha nacimiento (AAAA-MM-DD):", 15)
        self.p_sexo = combo(form, 4, "Sexo:", 5)
        cargar_combo(self.p_sexo, [("F", "F"), ("M", "M"), ("X", "X")])
        ttk.Button(form, text="Guardar paciente", command=self.guardar_paciente
                   ).grid(row=5, column=0, columnspan=2, pady=8)
        self.t_pacientes = crear_tabla(tab, ("dni", "apellido", "nombre", "fecha_nac", "sexo"), 180)

    def guardar_paciente(self):
        def accion():
            db.alta_paciente(
                self.p_dni.get().strip(), self.p_nombre.get(), self.p_apellido.get(),
                parsear_fecha(self.p_nac.get(), "Fecha de nacimiento"),
                valor_combo(self.p_sexo, "Sexo"))
        if ejecutar(accion, "Paciente guardado.", self.refrescar_todo):
            for e in (self.p_dni, self.p_nombre, self.p_apellido, self.p_nac):
                e.delete(0, "end")

    # ----- Médicos ------------------------------------------------------------
    def _tab_medicos(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Médicos")
        self.esp_pendientes = {}  # especialidad -> hace_guardia (bool)

        form = ttk.LabelFrame(tab, text="Alta de médico")
        form.pack(fill="x", padx=10, pady=8)
        self.m_mat = campo(form, 0, "Matrícula:", 15)
        self.m_dni = campo(form, 1, "DNI:", 15)
        self.m_nombre = campo(form, 2, "Nombre:")
        self.m_apellido = campo(form, 3, "Apellido:")
        self.m_cuil = campo(form, 4, "CUIL/CUIT (11 dígitos):", 15)
        self.m_ingreso = campo(form, 5, "Fecha de ingreso (AAAA-MM-DD):", 15)
        self.m_ingreso.insert(0, date.today().isoformat())
        self.m_maxg = campo(form, 6, "Máx. guardias por mes:", 6)
        self.m_maxg.insert(0, "0")
        self.m_foto = campo(form, 7, "Foto (opcional):", 40)
        ttk.Button(form, text="Elegir...", command=self.elegir_foto).grid(row=7, column=2, padx=4)

        esp = ttk.LabelFrame(form, text="Especialidades")
        esp.grid(row=0, column=3, rowspan=8, padx=20, sticky="n")
        self.cb_esp = ttk.Combobox(esp, width=25)  # editable: permite una especialidad nueva
        self.cb_esp.grid(row=0, column=0, padx=4, pady=3)
        self.var_hace_guardia = tk.BooleanVar(value=True)
        ttk.Checkbutton(esp, text="Hace guardia", variable=self.var_hace_guardia
                        ).grid(row=0, column=1, padx=4)
        ttk.Button(esp, text="Agregar", command=self.agregar_especialidad).grid(row=0, column=2, padx=4)
        self.t_esp = ttk.Treeview(esp, columns=("especialidad", "guardia"), show="headings", height=4)
        for c in ("especialidad", "guardia"):
            self.t_esp.heading(c, text=c)
            self.t_esp.column(c, width=130)
        self.t_esp.grid(row=1, column=0, columnspan=3, padx=4, pady=4)
        ttk.Button(esp, text="Quitar seleccionada", command=self.quitar_especialidad
                   ).grid(row=2, column=0, columnspan=3, pady=2)

        ttk.Button(form, text="Guardar médico", command=self.guardar_medico
                   ).grid(row=8, column=0, columnspan=2, pady=8)
        self.t_medicos = crear_tabla(
            tab, ("matricula", "dni", "apellido", "nombre", "cuil_cuit", "max_guardias"), 150)

    def elegir_foto(self):
        ruta = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Todos", "*.*")])
        if ruta:
            self.m_foto.delete(0, "end")
            self.m_foto.insert(0, ruta)

    def agregar_especialidad(self):
        nombre = self.cb_esp.get().strip()
        if not nombre:
            return
        self.esp_pendientes[nombre] = self.var_hace_guardia.get()
        self._mostrar_esp_pendientes()

    def quitar_especialidad(self):
        sel = self.t_esp.selection()
        if sel:
            self.esp_pendientes.pop(self.t_esp.item(sel[0])["values"][0], None)
            self._mostrar_esp_pendientes()

    def _mostrar_esp_pendientes(self):
        llenar(self.t_esp, [(n, "S" if hg else "N") for n, hg in self.esp_pendientes.items()])

    def guardar_medico(self):
        def accion():
            foto = None
            ruta = self.m_foto.get().strip()
            if ruta:
                try:
                    with open(ruta, "rb") as f:
                        foto = f.read()
                except OSError as e:
                    raise ValueError(f"No se pudo leer la foto: {e}")
            ing = parsear_fecha(self.m_ingreso.get(), "Fecha de ingreso")
            db.alta_medico(
                parsear_entero(self.m_mat.get(), "Matrícula"),
                self.m_dni.get().strip(), self.m_nombre.get(), self.m_apellido.get(),
                self.m_cuil.get().strip(), datetime.combine(ing, datetime.min.time()),
                parsear_entero(self.m_maxg.get(), "Máx. guardias"), foto,
                list(self.esp_pendientes.items()))
        if ejecutar(accion, "Médico guardado.", self.refrescar_todo):
            for e in (self.m_mat, self.m_dni, self.m_nombre, self.m_apellido,
                      self.m_cuil, self.m_foto):
                e.delete(0, "end")
            self.esp_pendientes.clear()
            self._mostrar_esp_pendientes()

    # ----- Internaciones (camas) ---------------------------------------------
    def _tab_internaciones(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Internaciones")
        form = ttk.LabelFrame(tab, text="Nueva internación / cambio de cama")
        form.pack(fill="x", padx=10, pady=8)
        self.cb_paciente = combo(form, 0, "Paciente:")
        self.cb_medico_ppal = combo(form, 1, "Médico principal:")
        self.cb_cama = combo(form, 2, "Cama libre:")
        botones = ttk.Frame(form)
        botones.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(botones, text="Internar paciente", command=self.internar).pack(side="left", padx=6)
        ttk.Button(botones, text="Cambiar cama de la internación seleccionada",
                   command=self.cambiar_cama).pack(side="left", padx=6)
        ttk.Button(botones, text="Dar de alta la seleccionada",
                   command=self.dar_alta).pack(side="left", padx=6)

        ttk.Label(tab, text="Internaciones en curso:").pack(anchor="w", padx=10)
        self.t_int = crear_tabla(
            tab, ("id_internacion", "dni", "paciente", "matricula", "habitacion", "cama", "desde"), 140)

    def internar(self):
        def accion():
            id_int = db.internar(
                valor_combo(self.cb_paciente, "Paciente"),
                valor_combo(self.cb_medico_ppal, "Médico principal"),
                *valor_combo(self.cb_cama, "Cama libre"))
            messagebox.showinfo("Listo", f"Internación #{id_int} creada.")
        ejecutar(accion, despues=self.refrescar_todo)

    def cambiar_cama(self):
        def accion():
            fila = fila_seleccionada(self.t_int, "Seleccioná una internación de la lista.")
            db.cambiar_cama(int(fila[0]), *valor_combo(self.cb_cama, "Cama libre"))
        ejecutar(accion, "Cama cambiada.", self.refrescar_todo)

    def dar_alta(self):
        def accion():
            fila = fila_seleccionada(self.t_int, "Seleccioná una internación de la lista.")
            if not messagebox.askyesno("Confirmar", f"¿Dar de alta la internación #{fila[0]}?"):
                return False
            db.dar_alta(int(fila[0]))
            return True
        if ejecutar(accion):
            self.refrescar_todo()

    # ----- Guardias -----------------------------------------------------------
    def _tab_guardias(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Guardias")
        form = ttk.LabelFrame(tab, text="Asignar guardia")
        form.pack(fill="x", padx=10, pady=8)
        self.cb_medico_g = combo(form, 0, "Médico:")
        self.cb_medico_g.bind("<<ComboboxSelected>>", lambda _e: self.cargar_esp_guardia())
        self.cb_esp_g = combo(form, 1, "Especialidad (hace guardia):")
        self.g_fecha = campo(form, 2, "Día (AAAA-MM-DD):", 15)
        ttk.Label(form, text="Turnos:").grid(row=3, column=0, sticky="e", padx=6)
        marcos = ttk.Frame(form)
        marcos.grid(row=3, column=1, sticky="w")
        self.var_turnos = {}
        for t, (nombre, hora) in db.TURNOS.items():
            self.var_turnos[t] = tk.BooleanVar()
            ttk.Checkbutton(marcos, text=f"{nombre} ({hora:02d}:00)",
                            variable=self.var_turnos[t]).pack(side="left", padx=6)
        ttk.Button(form, text="Asignar guardia", command=self.asignar_guardia
                   ).grid(row=4, column=0, columnspan=2, pady=8)
        self.t_guardias = crear_tabla(
            tab, ("id_guardia", "matricula", "especialidad", "inicio", "fin"), 190)

    def cargar_esp_guardia(self):
        def accion():
            mat = valor_combo(self.cb_medico_g, "Médico")
            cargar_combo(self.cb_esp_g, [(e, e) for e in db.especialidades_de_guardia(mat)])
        ejecutar(accion)

    def asignar_guardia(self):
        def accion():
            db.alta_guardia(
                valor_combo(self.cb_medico_g, "Médico"),
                valor_combo(self.cb_esp_g, "Especialidad"),
                parsear_fecha(self.g_fecha.get(), "Día"),
                [t for t, v in self.var_turnos.items() if v.get()])
        ejecutar(accion, "Guardia asignada.", self.refrescar_todo)

    # ----- Auditoría ----------------------------------------------------------
    def _tab_auditoria(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Auditoría de guardias")
        ttk.Button(tab, text="Refrescar auditoría",
                   command=lambda: ejecutar(self.refrescar_auditoria)).pack(pady=5)
        self.t_audit = crear_tabla(
            tab, ("id", "fecha_hora", "usuario", "tabla", "operacion", "clave", "detalle"), 150)

    def refrescar_auditoria(self):
        llenar(self.t_audit, db.listar_auditoria())

    # ----- Batería de pruebas -------------------------------------------------
    def _tab_pruebas(self):
        panel = pruebas.PanelPruebas(self.nb)
        self.nb.add(panel, text="Batería de pruebas")

    # ----- Refresco general ---------------------------------------------------
    def refrescar_todo(self):
        try:
            self.refrescar_camas()
            pacientes = db.listar_pacientes()
            medicos = db.listar_medicos()
            llenar(self.t_pacientes, pacientes)
            llenar(self.t_medicos, medicos)
            cargar_combo(self.cb_paciente, [(f"{d} - {a}, {n}", d) for d, a, n, _, _ in pacientes])
            medicos_items = [(f"{m} - {a}, {n}", m) for m, _, a, n, _, _ in medicos]
            cargar_combo(self.cb_medico_ppal, medicos_items)
            cargar_combo(self.cb_medico_g, medicos_items)
            cargar_combo(self.cb_cama, [
                (f"Hab {h} / Cama {c} - {s}", (int(h), int(c))) for h, c, s in db.camas_libres()])
            self.cb_esp["values"] = db.listar_especialidades()
            llenar(self.t_int, db.internaciones_abiertas())
            llenar(self.t_guardias, db.listar_guardias())
            self.refrescar_auditoria()
        except oracledb.Error as e:
            messagebox.showerror("Error de conexión", f"No se pudo leer la base:\n{e}")


if __name__ == "__main__":
    ventana = tk.Tk()
    App(ventana)
    ventana.mainloop()
