from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura_aqui' # ¡CAMBIA ESTO EN PRODUCCIÓN!
DATABASE = 'gestor_tareas.db' # Renombrado para mayor claridad
UPLOAD_FOLDER = 'static/uploads/archivos_tareas'
AVATAR_FOLDER = 'static/uploads/avatars' # Nuevo folder para avatares

# Asegurar que los directorios de carga existan
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Max upload size: 16 MB

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Tabla usuarios
    cur.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nombre TEXT NOT NULL,
      nombre_usuario TEXT UNIQUE NOT NULL,
      curso TEXT DEFAULT 'N/A', -- Curso por defecto para usuarios que no son estudiantes
      documento TEXT UNIQUE NOT NULL,
      correo TEXT UNIQUE NOT NULL,
      contrasena TEXT NOT NULL,
      rol TEXT DEFAULT 'rol_usuario',
      fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
      activo INTEGER DEFAULT 1,
      tema TEXT DEFAULT 'claro',
      idioma TEXT DEFAULT 'es',
      notificaciones INTEGER DEFAULT 1,
      avatar_url TEXT DEFAULT NULL -- Columna para la URL del avatar
    );''')

    # Añadir columna avatar_url si no existe (para bases de datos existentes)
    try:
        cur.execute("ALTER TABLE usuarios ADD COLUMN avatar_url TEXT DEFAULT NULL")
        print("Columna 'avatar_url' añadida a la tabla 'usuarios'.")
    except sqlite3.OperationalError as e:
        if "duplicate column name: avatar_url" in str(e):
            print("La columna 'avatar_url' ya existe en la tabla 'usuarios'.")
        else:
            raise e

    # Tabla tareas
    cur.execute('''
    CREATE TABLE IF NOT EXISTS tareas (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      titulo TEXT NOT NULL,
      descripcion TEXT,
      fecha_vencimiento DATE,
      prioridad TEXT,
      estado TEXT DEFAULT 'pendiente',
      id_proyecto INTEGER,
      profesor_id INTEGER, -- FK al id de usuario del profesor que creó la tarea
      ruta_archivo TEXT,
      curso_destino TEXT NOT NULL, -- Curso al que se asigna la tarea
      FOREIGN KEY(profesor_id) REFERENCES usuarios(id) ON DELETE SET NULL
    );''')

    # Tabla proyectos
    cur.execute('''
    CREATE TABLE IF NOT EXISTS proyectos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nombre TEXT NOT NULL,
      descripcion TEXT,
      fecha_inicio DATE,
      fecha_fin DATE,
      estado TEXT DEFAULT 'activo',
      id_usuario_creador INTEGER,
      FOREIGN KEY(id_usuario_creador) REFERENCES usuarios(id) ON DELETE SET NULL
    );''')

    # Tabla notificaciones
    cur.execute('''
    CREATE TABLE IF NOT EXISTS notificaciones (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mensaje TEXT NOT NULL,
      leido INTEGER DEFAULT 0,
      fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
      id_usuario INTEGER,
      FOREIGN KEY(id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
    );''')

    # Tabla profesores
    cur.execute('''
    CREATE TABLE IF NOT EXISTS profesores (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      usuario_id INTEGER UNIQUE NOT NULL, -- FK al id de usuario
      experiencia TEXT,
      materia TEXT,
      lider TEXT,
      telefono TEXT,
      direccion TEXT,
      FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );''')

    # Tabla cursos
    cur.execute('''
    CREATE TABLE IF NOT EXISTS cursos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      curso TEXT UNIQUE NOT NULL
    );''')

    # Insertar cursos por defecto si no existen
    default_cursos = ['6A', '6B', '6C', '7A', '7B', '7C', '8A', '8B', '8C', '9A', '9B', '9C', '10A', '10B', '10C', '11A', '11B', '11C']
    for c_name in default_cursos:
        cur.execute('SELECT COUNT(*) FROM cursos WHERE curso=?', (c_name,))
        if not cur.fetchone()[0]:
            cur.execute('INSERT INTO cursos (curso) VALUES (?)', (c_name,))
            print(f"Curso '{c_name}' añadido.")


    # Crear usuarios por defecto (admin y profesor1) si no existen
    cur.execute('SELECT COUNT(*) FROM usuarios WHERE nombre_usuario="admin"')
    if not cur.fetchone()[0]:
        cur.execute('''
        INSERT INTO usuarios (nombre, nombre_usuario, curso, documento, correo, contrasena, rol)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
          'Administrador','admin','N/A','00000000',
          'admin@example.com', generate_password_hash('admin123'),
          'rol_administrador'
        ))
        print("Usuario 'admin' creado.")

    cur.execute('SELECT COUNT(*) FROM usuarios WHERE nombre_usuario="profesor1"')
    if not cur.fetchone()[0]:
        cur.execute('''
        INSERT INTO usuarios (nombre, nombre_usuario, curso, documento, correo, contrasena, rol)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
          'Profesor Juan','profesor1','Matemáticas','12345678',
          'profesor1@example.com', generate_password_hash('profesor123'),
          'rol_profesor'
        ))
        print("Usuario 'profesor1' creado.")

    conn.commit()
    conn.close()

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class Usuario(UserMixin):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        # Asegurarse de que avatar_url siempre esté presente, incluso si es None
        if 'avatar_url' not in self.__dict__:
            self.avatar_url = None

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM usuarios WHERE id=?', (user_id,)).fetchone()
    conn.close()
    return Usuario(**dict(row)) if row else None

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u = request.form['nombre_usuario']
        p = request.form['contrasena']
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM usuarios WHERE nombre_usuario=?', (u,)).fetchone()
        conn.close()
        if row and check_password_hash(row['contrasena'], p) and row['activo']:
            user = Usuario(**dict(row))
            login_user(user)
            flash(f'¡Bienvenido, {user.nombre}!', 'success')
            return redirect(url_for(user.rol.replace('rol_',''))) # Redirige a admin, profesor, o usuario
        flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/crear_usuario', methods=['GET','POST'])
def crear_usuario():
    if request.method=='POST':
        d = {k: request.form[k] for k in ['nombre','nombre_usuario','curso','documento','correo']}
        d['contrasena'] = generate_password_hash(request.form['contrasena'])
        d['rol'] = request.form.get('rol','rol_usuario') # Permite seleccionar rol en el formulario, si no, por defecto 'rol_usuario'
        conn = get_db_connection()
        try:
            conn.execute('''
            INSERT INTO usuarios (nombre,nombre_usuario,curso,documento,correo,contrasena,rol)
            VALUES (:nombre,:nombre_usuario,:curso,:documento,:correo,:contrasena,:rol)
            ''', d)
            conn.commit()
            flash('Usuario creado exitosamente. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('El nombre de usuario, documento o correo ya existe', 'danger')
        finally:
            conn.close()
    
    conn = get_db_connection()
    cursos_db = conn.execute('SELECT curso FROM cursos ORDER BY curso').fetchall()
    conn.close()
    return render_template('crear_usuario.html', cursos=cursos_db)

@app.route('/administrador')
@login_required
def administrador():
    if current_user.rol!='rol_administrador':
        flash('Acceso denegado. Solo administradores pueden acceder a este panel.', 'danger')
        return redirect(url_for('index'))
    conn = get_db_connection()
    usuarios_activos = conn.execute('SELECT COUNT(*) FROM usuarios WHERE rol="rol_usuario" AND activo=1').fetchone()[0]
    profesores_activos = conn.execute('SELECT COUNT(*) FROM usuarios WHERE rol="rol_profesor" AND activo=1').fetchone()[0]
    total_tareas = conn.execute('SELECT COUNT(*) FROM tareas').fetchone()[0]
    proyectos_activos = conn.execute('SELECT COUNT(*) FROM proyectos WHERE estado = "activo"').fetchone()[0]
    
    # Obtener algunos datos para listar en el admin.html, si es necesario
    usuarios_lista = conn.execute('SELECT id, nombre, nombre_usuario, rol, activo FROM usuarios ORDER BY rol, nombre').fetchall()

    conn.close()
    return render_template('admin.html', 
                           usuarios_activos=usuarios_activos, 
                           profesores_activos=profesores_activos,
                           total_tareas=total_tareas, 
                           proyectos_activos=proyectos_activos,
                           usuarios_lista=usuarios_lista # Para listar usuarios si el admin lo necesita
                           )

@app.route('/profesor')
@login_required
def profesor(): # Cambiado el nombre de la función para ser consistente con el render_template
    if current_user.rol != 'rol_profesor':
        flash('Acceso denegado. Solo profesores pueden acceder a este panel.', 'danger')
        return redirect(url_for('index'))

    estado_filtro = request.args.get('estado')
    curso_filtro = request.args.get('curso')

    conn = get_db_connection()
    query = 'SELECT * FROM tareas WHERE profesor_id = ?'
    params = [current_user.id]

    if estado_filtro:
        query += ' AND estado = ?'
        params.append(estado_filtro)
    if curso_filtro:
        query += ' AND curso_destino = ?'
        params.append(curso_filtro)

    # Ordenar tareas para una mejor visualización
    query += ' ORDER BY fecha_vencimiento ASC, prioridad DESC'

    print(f"DEBUG: Inside profesor() function") # Actualizado el nombre de la función en el debug
    print(f"DEBUG: Filters - estado: {estado_filtro}, curso: {curso_filtro}")

    try:
        tareas = conn.execute(query, params).fetchall()
        print(f"DEBUG: Number of tasks found: {len(tareas)}")

        # Obtener todos los cursos disponibles de la tabla 'cursos' para el selector del modal
        all_cursos_db = conn.execute('SELECT curso FROM cursos ORDER BY curso').fetchall()
        # Convertir a una lista de diccionarios para el template
        all_cursos_db_dicts = [dict(c) for c in all_cursos_db]

        # Obtener cursos distintos que tienen tareas asignadas por el profesor actual (para el filtro)
        cursos_para_filtro_db = conn.execute("""
            SELECT DISTINCT curso_destino FROM tareas
            WHERE profesor_id = ?
            ORDER BY curso_destino
        """, (current_user.id,)).fetchall()
        cursos_para_filtro_dicts = [dict(c) for c in cursos_para_filtro_db]

        print(f"DEBUG: Cursos disponibles (para modal): {all_cursos_db_dicts}")
        print(f"DEBUG: Cursos disponibles (para filtro): {cursos_para_filtro_dicts}")

    except Exception as e:
        print(f"DEBUG: Error fetching tasks or courses: {e}")
        flash(f"Error al cargar las tareas o cursos: {e}", "danger")
        tareas = []
        all_cursos_db_dicts = []
        cursos_para_filtro_dicts = []
    finally:
        conn.close()
        print("DEBUG: Database connection closed.")

    return render_template('profesor.html',
                           tareas=tareas,
                           cursos=all_cursos_db_dicts, # Pasar todos los cursos para el dropdown del modal de crear/editar
                           cursos_filtro_opciones=cursos_para_filtro_dicts, # Pasar cursos para el filtro de la tabla
                           estado=estado_filtro,
                           curso_filtro=curso_filtro,
                           current_user=current_user)

@app.route('/rol_usuario')
@login_required
def rol_usuario():
    if current_user.rol != 'rol_usuario':
        flash('Acceso denegado. Solo usuarios regulares pueden acceder a este panel.', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    # Lógica para mostrar tareas relevantes al usuario.
    # Por ejemplo, tareas asignadas a su curso, o a él directamente.
    # Asumiendo que `usuarios.curso` es el curso del estudiante
    
    # Obtener el curso del usuario actual
    usuario_curso = current_user.curso

    tareas_del_curso = []
    if usuario_curso and usuario_curso != 'N/A':
        tareas_del_curso = conn.execute(
            'SELECT * FROM tareas WHERE curso_destino = ? ORDER BY fecha_vencimiento ASC',
            (usuario_curso,)
        ).fetchall()
    
    # También podrías obtener tareas asignadas directamente al usuario si tuvieras una columna `id_usuario_asignado`
    # o una tabla de asignaciones muchos a muchos. Por ahora, nos basamos en `curso_destino`.
    
    conn.close()
    flash(f'¡Bienvenido, {current_user.nombre}! Estas son las tareas para tu curso: {usuario_curso}.', 'info')
    return render_template('persona.html', tareas=tareas_del_curso, current_user=current_user)


@app.route('/crear_tarea', methods=['POST'])
@login_required
def crear_tarea():
    if current_user.rol != 'rol_profesor':
        flash('Permiso denegado para crear tareas.', 'danger')
        return redirect(url_for('profesor'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        curso_destino = request.form['curso_destino']
        fecha_vencimiento = request.form['fecha_vencimiento']
        prioridad = request.form['prioridad']
        estado = request.form['estado']
        profesor_id = current_user.id

        ruta_archivo = None
        if 'archivo' in request.files:
            archivo = request.files['archivo']
            if archivo and allowed_file(archivo.filename):
                filename = secure_filename(archivo.filename)
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{base}_{timestamp}{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                archivo.save(filepath)
                ruta_archivo = unique_filename # Almacenar solo el nombre único del archivo

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO tareas (titulo, descripcion, fecha_vencimiento, prioridad, estado, profesor_id, ruta_archivo, curso_destino)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (titulo, descripcion, fecha_vencimiento, prioridad, estado, profesor_id, ruta_archivo, curso_destino))
            conn.commit()
            flash('Tarea creada exitosamente!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error al crear la tarea: {e}', 'danger')
            print(f"Error al crear la tarea: {e}")
        finally:
            conn.close()

    return redirect(url_for('profesor'))


@app.route('/editar_tarea/<int:id>', methods=['POST'])
@login_required
def editar_tarea(id):
    if current_user.rol != 'rol_profesor':
        flash('Permiso denegado para editar tareas.', 'danger')
        return redirect(url_for('profesor'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        curso_destino = request.form['curso_destino']
        fecha_vencimiento = request.form['fecha_vencimiento']
        prioridad = request.form['prioridad']
        estado = request.form['estado']

        conn = get_db_connection()
        current_task = conn.execute('SELECT ruta_archivo FROM tareas WHERE id = ? AND profesor_id = ?', (id, current_user.id)).fetchone()
        
        if not current_task:
            conn.close()
            flash('Tarea no encontrada o no tienes permiso para editarla.', 'danger')
            return redirect(url_for('profesor'))

        ruta_archivo = current_task['ruta_archivo'] # Preservar el path del archivo existente

        if 'archivo' in request.files:
            archivo = request.files['archivo']
            if archivo and allowed_file(archivo.filename):
                # Eliminar el archivo antiguo si existe y se sube uno nuevo
                if ruta_archivo:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], ruta_archivo)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                        print(f"Archivo antiguo eliminado: {old_filepath}")
                
                filename = secure_filename(archivo.filename)
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{base}_{timestamp}{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                archivo.save(filepath)
                ruta_archivo = unique_filename # Actualizar con el nombre del nuevo archivo
            elif archivo and archivo.filename == '': # Si el input de archivo está vacío (no se seleccionó un nuevo archivo)
                pass # Mantener la ruta_archivo existente
            # else: El usuario subió un archivo no permitido, mantener la ruta_archivo actual y no actualizar.

        try:
            conn.execute('''
                UPDATE tareas SET
                    titulo = ?,
                    descripcion = ?,
                    fecha_vencimiento = ?,
                    prioridad = ?,
                    estado = ?,
                    ruta_archivo = ?,
                    curso_destino = ?
                WHERE id = ? AND profesor_id = ?
            ''', (titulo, descripcion, fecha_vencimiento, prioridad, estado, ruta_archivo, curso_destino, id, current_user.id))
            conn.commit()
            flash('Tarea actualizada exitosamente!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error al actualizar la tarea: {e}', 'danger')
            print(f"Error al actualizar la tarea: {e}")
        finally:
            conn.close()

    return redirect(url_for('profesor'))


@app.route('/eliminar_tarea/<int:id>', methods=['POST'])
@login_required
def eliminar_tarea(id):
    if current_user.rol != 'rol_profesor':
        flash('Permiso denegado para eliminar tareas.', 'danger')
        return redirect(url_for('profesor'))

    conn = get_db_connection()
    try:
        # Obtener la ruta del archivo antes de eliminar el registro de la tarea
        task = conn.execute('SELECT ruta_archivo FROM tareas WHERE id = ? AND profesor_id = ?', (id, current_user.id)).fetchone()
        if task:
            ruta_archivo = task['ruta_archivo']
            conn.execute('DELETE FROM tareas WHERE id = ? AND profesor_id = ?', (id, current_user.id))
            conn.commit()
            
            # Eliminar el archivo asociado del servidor
            if ruta_archivo:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], ruta_archivo)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"Archivo de tarea eliminado: {filepath}")

            flash('Tarea eliminada exitosamente!', 'success')
        else:
            flash('Tarea no encontrada o no tienes permiso para eliminarla.', 'danger')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar la tarea: {e}', 'danger')
        print(f"Error al eliminar la tarea: {e}")
    finally:
        conn.close()
    return redirect(url_for('profesor'))

@app.route('/descargar_archivo/<filename>')
@login_required
def descargar_archivo(filename):
    # Verificar si el archivo pertenece a una tarea del profesor o si es un administrador
    conn = get_db_connection()
    task_owner = conn.execute('SELECT profesor_id FROM tareas WHERE ruta_archivo = ?', (filename,)).fetchone()
    conn.close()

    is_allowed = False
    if task_owner and task_owner['profesor_id'] == current_user.id:
        is_allowed = True
    elif current_user.rol == 'rol_administrador':
        is_allowed = True
    # Permitir a los usuarios regulares descargar archivos si están asociados a su curso
    elif current_user.rol == 'rol_usuario':
        conn = get_db_connection()
        user_course = current_user.curso
        task_in_course = conn.execute('SELECT 1 FROM tareas WHERE ruta_archivo = ? AND curso_destino = ?', (filename, user_course)).fetchone()
        conn.close()
        if task_in_course:
            is_allowed = True

    if is_allowed:
        try:
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        except FileNotFoundError:
            flash('El archivo no fue encontrado.', 'danger')
            if current_user.rol == 'rol_profesor':
                return redirect(url_for('profesor'))
            elif current_user.rol == 'rol_usuario':
                return redirect(url_for('rol_usuario'))
            return redirect(url_for('index'))
    else:
        flash('No tienes permiso para descargar este archivo.', 'danger')
        if current_user.rol == 'rol_profesor':
            return redirect(url_for('profesor'))
        elif current_user.rol == 'rol_usuario':
            return redirect(url_for('rol_usuario'))
        return redirect(url_for('index'))


# API para obtener una tarea por ID (para edición)
@app.route('/api/tarea/<int:task_id>', methods=['GET'])
@login_required
def api_get_tarea(task_id):
    conn = get_db_connection()
    # Asegurarse de que el profesor solo pueda ver sus propias tareas
    task = conn.execute('SELECT * FROM tareas WHERE id = ? AND profesor_id = ?', (task_id, current_user.id)).fetchone()
    conn.close()
    if task:
        return jsonify(dict(task))
    return jsonify(error="Tarea no encontrada o no tienes permiso."), 404

# API para obtener todos los cursos disponibles (para dropdowns de creación/edición)
@app.route('/api/cursos', methods=['GET'])
def api_get_cursos():
    conn = get_db_connection()
    cursos = conn.execute('SELECT curso FROM cursos ORDER BY curso').fetchall()
    conn.close()
    # Retorna una lista de diccionarios con la clave 'curso'
    return jsonify([dict(c) for c in cursos])

# API para obtener el perfil del profesor logueado
@app.route('/api/profesor/perfil', methods=['GET'])
@login_required
def api_profesor_perfil():
    if current_user.rol != 'rol_profesor':
        return jsonify(error="Acceso denegado."), 403

    conn = get_db_connection()
    try:
        user_data = conn.execute('SELECT id, nombre, nombre_usuario, correo, avatar_url FROM usuarios WHERE id = ?', (current_user.id,)).fetchone()
        profesor_data = conn.execute('SELECT experiencia, materia, lider, telefono, direccion FROM profesores WHERE usuario_id = ?', (current_user.id,)).fetchone()

        if user_data:
            user_dict = dict(user_data)
            # Construir la URL completa del avatar si existe
            if user_dict['avatar_url']:
                user_dict['avatar_url'] = url_for('serve_avatars', filename=user_dict['avatar_url'], _external=True)
            else:
                user_dict['avatar_url'] = None

            if profesor_data:
                user_dict.update(dict(profesor_data))
            
            return jsonify(user_dict), 200
        return jsonify(error="Perfil de profesor no encontrado."), 404
    except Exception as e:
        print(f"Error fetching professor profile: {e}")
        return jsonify(error=f"Error interno del servidor: {e}"), 500
    finally:
        conn.close()

@app.route('/actualizar_perfil_profesor', methods=['POST'])
@login_required
def actualizar_perfil_profesor():
    if current_user.rol != 'rol_profesor':
        flash('Permiso denegado para actualizar el perfil.', 'danger')
        return redirect(url_for('profesor'))

    conn = get_db_connection()
    try:
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        nueva_contrasena = request.form.get('nueva_contrasena')
        confirmar_contrasena = request.form.get('confirmar_contrasena')

        # --- DEBUGGING PRINTS ---
        print("\n--- DEBUG: Actualizar Perfil Profesor ---")
        print(f"Request Form Data: {request.form}")
        print(f"Nombre: {nombre}, Email: {email}")
        print(f"Nueva Contraseña (recibida): '{nueva_contrasena}'")
        print(f"Confirmar Contraseña (recibida): '{confirmar_contrasena}'")
        print(f"Current User ID: {current_user.id}")
        # --- END DEBUGGING PRINTS ---

        # Validación de contraseñas: Asegúrate de que no solo sea None o una cadena vacía/solo espacios
        if nueva_contrasena and nueva_contrasena.strip(): # CLAVE: añadimos .strip() aquí
            if nueva_contrasena != confirmar_contrasena:
                flash('Las nuevas contraseñas no coinciden.', 'danger')
                print("DEBUG: Contraseñas no coinciden.")
                return redirect(url_for('profesor'))
            
            hashed_password = generate_password_hash(nueva_contrasena)
            print(f"DEBUG: Contraseña Hashed: {hashed_password}")
        else:
            hashed_password = None # Asegurarse de que no se intente hashear una cadena vacía
            print("DEBUG: No se proporcionó nueva contraseña o estaba vacía. No se actualizará la contraseña.")

        avatar_filename = current_user.avatar_url # Mantener el avatar actual por defecto
        print(f"DEBUG: Avatar actual (antes de procesar archivo): {avatar_filename}")

        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file and allowed_file(avatar_file.filename):
                # Eliminar el avatar antiguo si existe y se sube uno nuevo
                if current_user.avatar_url:
                    old_avatar_path = os.path.join(app.config['AVATAR_FOLDER'], current_user.avatar_url)
                    if os.path.exists(old_avatar_path):
                        os.remove(old_avatar_path)
                        print(f"DEBUG: Avatar antiguo eliminado: {old_avatar_path}")

                filename = secure_filename(avatar_file.filename)
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_avatar_filename = f"avatar_{current_user.id}_{timestamp}{ext}"
                
                filepath = os.path.join(app.config['AVATAR_FOLDER'], unique_avatar_filename)
                avatar_file.save(filepath)
                avatar_filename = unique_avatar_filename # Actualizar con el nuevo nombre de archivo
                print(f"DEBUG: Nuevo avatar guardado: {avatar_filename}")
            else:
                print("DEBUG: Archivo de avatar no permitido o vacío.")
        else:
            print("DEBUG: No se encontró 'avatar' en request.files. Se mantiene el avatar actual.")
        
        # Iniciar la construcción de la consulta de actualización para la tabla usuarios
        update_user_query = 'UPDATE usuarios SET nombre = ?, correo = ?'
        user_params = [nombre, email]

        if hashed_password: # Solo añadir la contraseña si se generó un hash (es decir, si se proporcionó una nueva)
            update_user_query += ', contrasena = ?'
            user_params.append(hashed_password)
        
        # Añadir el avatar_url a la actualización (siempre se incluye para actualizar o mantener NULL/viejo)
        update_user_query += ', avatar_url = ?'
        user_params.append(avatar_filename)
        
        user_params.append(current_user.id) # Para la cláusula WHERE

        final_query = update_user_query + ' WHERE id = ?'
        print(f"DEBUG: Final SQL Query: {final_query}")
        print(f"DEBUG: Final Query Params: {user_params}")

        conn.execute(final_query, user_params)
        conn.commit()
        print("DEBUG: Conn.commit() ejecutado.")

        flash('Perfil actualizado exitosamente!', 'success')
        # Re-cargar el usuario actual en Flask-Login para reflejar los cambios
        # Esto es importante para que current_user tenga los datos más recientes (nombre, email, avatar, etc.)
        # y que el hasheo de la contraseña se aplique para futuras autenticaciones.
        login_user(load_user(current_user.id))
        print("DEBUG: Usuario recargado en sesión.")

    except sqlite3.IntegrityError as e:
        conn.rollback()
        flash('El correo electrónico ya está en uso.', 'danger')
        print(f"ERROR: IntegrityError: {e}")
    except Exception as e:
        conn.rollback()
        flash(f'Error al actualizar el perfil: {e}', 'danger')
        print(f"ERROR: Error general actualizando perfil: {e}")
    finally:
        conn.close()
        print("DEBUG: Conexión a DB cerrada.")
    
    print("--- DEBUG: Fin de Actualizar Perfil Profesor ---\n")
    return redirect(url_for('profesor'))

@app.route('/logout')
@login_required
def logout():
    logout_user() # Esto cierra la sesión del usuario
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('login')) # Redirige al login

# Rutas para servir archivos estáticos cargados
@app.route('/static/uploads/archivos_tareas/<filename>')
def serve_task_files(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/static/uploads/avatars/<filename>')
def serve_avatars(filename):
    return send_from_directory(app.config['AVATAR_FOLDER'], filename)


if __name__=='__main__':
    # Si quieres reiniciar la base de datos para pruebas, descomenta las líneas de abajo.
    # ¡CUIDADO! Esto borrará todos tus datos.
    # if os.path.exists(DATABASE):
    #     os.remove(DATABASE)
    #     print(f"Database '{DATABASE}' removed for fresh start.")

    init_db()
    app.run(debug=True, port=5000)