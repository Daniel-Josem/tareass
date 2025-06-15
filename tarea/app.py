# app.py

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'
DATABASE = 'usuarios.db'
UPLOAD_FOLDER = 'archivos_tareas'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # usuarios
    cur.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nombre TEXT NOT NULL,
      nombre_usuario TEXT UNIQUE NOT NULL,
      curso TEXT NOT NULL,
      documento TEXT UNIQUE NOT NULL,
      correo TEXT UNIQUE NOT NULL,
      contrasena TEXT NOT NULL,
      rol TEXT DEFAULT 'rol_usuario',
      fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
      activo INTEGER DEFAULT 1,
      tema TEXT DEFAULT 'claro',
      idioma TEXT DEFAULT 'es',
      notificaciones INTEGER DEFAULT 1
    );''')

    # tareas, proyectos, notificaciones...
    cur.execute('''
    CREATE TABLE IF NOT EXISTS tareas (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      titulo TEXT NOT NULL,
      descripcion TEXT,
      fecha_vencimiento DATE,
      prioridad TEXT,
      estado TEXT DEFAULT 'pendiente',
      id_proyecto INTEGER,
      id_usuario_asignado INTEGER,
      ruta_archivo TEXT,
      curso_destino TEXT,
      FOREIGN KEY(id_usuario_asignado) REFERENCES usuarios(id) ON DELETE SET NULL
    );''')

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

    cur.execute('''
    CREATE TABLE IF NOT EXISTS notificaciones (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mensaje TEXT NOT NULL,
      leido INTEGER DEFAULT 0,
      fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
      id_usuario INTEGER,
      FOREIGN KEY(id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
    );''')

    # profesores
    cur.execute('''
    CREATE TABLE IF NOT EXISTS profesores (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      usuario_id INTEGER UNIQUE NOT NULL,
      experiencia TEXT,
      materia TEXT,
      lider TEXT,
      telefono TEXT,
      direccion TEXT,
      FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );''')

    # admin + prueba
    cur.execute('SELECT COUNT(*) FROM usuarios WHERE nombre_usuario="admin"')
    if not cur.fetchone()[0]:
        cur.execute('''
        INSERT INTO usuarios (nombre,nombre_usuario,curso,documento,correo,contrasena,rol)
        VALUES (?,?,?,?,?,?,?)
        ''', (
          'Administrador','admin','N/A','00000000',
          'admin@example.com', generate_password_hash('admin123'),
          'rol_administrador'
        ))
    cur.execute('SELECT COUNT(*) FROM usuarios WHERE nombre_usuario="profesor1"')
    if not cur.fetchone()[0]:
        cur.execute('''
        INSERT INTO usuarios (nombre,nombre_usuario,curso,documento,correo,contrasena,rol)
        VALUES (?,?,?,?,?,?,?)
        ''', (
          'Profesor Juan','profesor1','Matemáticas','12345678',
          'profesor1@example.com', generate_password_hash('profesor123'),
          'rol_profesor'
        ))
    conn.commit(); conn.close()

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class Usuario(UserMixin):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

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
            login_user(Usuario(**dict(row)))
            return redirect(url_for(row['rol'].replace('rol_','')))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/crear_usuario', methods=['GET','POST'])
def crear_usuario():
    if request.method=='POST':
        d = {k: request.form[k] for k in ['nombre','nombre_usuario','curso','documento','correo']}
        d['contrasena'] = generate_password_hash(request.form['contrasena'])
        d['rol'] = request.form.get('rol','rol_usuario')
        conn = get_db_connection()
        try:
            conn.execute('''
            INSERT INTO usuarios (nombre,nombre_usuario,curso,documento,correo,contrasena,rol)
            VALUES (:nombre,:nombre_usuario,:curso,:documento,:correo,:contrasena,:rol)
            ''', d)
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('El nombre de usuario, documento o correo ya existe')
        finally:
            conn.close()
    return render_template('crear_usuario.html')

@app.route('/administrador')
@login_required
def administrador():
    if current_user.rol!='rol_administrador':
        return redirect(url_for('index'))
    conn = get_db_connection()
    usuarios = conn.execute('SELECT COUNT(*) FROM usuarios WHERE rol="rol_usuario" AND activo=1').fetchone()[0]
    tareas   = conn.execute('SELECT COUNT(*) FROM tareas').fetchone()[0]
    proyectos= conn.execute('SELECT COUNT(*) FROM proyectos').fetchone()[0]
    conn.close()
    return render_template('admin.html', usuarios=usuarios, tareas=tareas, proyectos=proyectos)

# ... rutas de profesor y tareas sin cambios ...

@app.route('/api/profesores/count')
@login_required
def api_profesores_count():
    conn = get_db_connection()
    cnt = conn.execute('SELECT COUNT(*) FROM usuarios WHERE rol="rol_profesor" AND activo=1').fetchone()[0]
    conn.close()
    return jsonify(count=cnt)


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/profesores', methods=['GET', 'POST'])
@login_required
def api_profesores():
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data = request.get_json()
            nombre_completo = f"{data['nombre']} {data['apellido']}"
            pwd_hash = generate_password_hash(data.get('contrasena', 'profesor123'))
            cur = conn.cursor()

            # 1) Intentamos insertar en usuarios
            try:
                cur.execute('''
                  INSERT INTO usuarios
                    (nombre, nombre_usuario, curso, documento, correo, contrasena, rol)
                  VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                  nombre_completo,
                  data['nombre_usuario'],
                  data.get('curso', ''),      # si no lo pasas, cadena vacía
                  data['documento'],
                  data['correo'],
                  pwd_hash,
                  'rol_profesor'
                ))
            except sqlite3.IntegrityError:
                conn.rollback()
                return jsonify(error="El nombre de usuario, documento o correo ya existe"), 400

            usuario_id = cur.lastrowid

            # 2) Insertamos en profesores
            cur.execute('''
              INSERT INTO profesores
                (usuario_id, experiencia, materia, lider, telefono, direccion)
              VALUES (?, ?, ?, ?, ?, ?)
            ''', (
              usuario_id,
              data['experiencia'],
              data['materia'],
              data['lider'],
              data['telefono'],
              data['direccion']
            ))

            conn.commit()
            return jsonify(success=True), 201

        else:
            # LISTAR solo activos
            rows = conn.execute('''
              SELECT
                u.id,
                u.nombre_usuario,
                u.documento,
                substr(u.nombre,1,instr(u.nombre,' ')-1)   AS nombre,
                trim(substr(u.nombre,instr(u.nombre,' ')+1)) AS apellido,
                p.experiencia,
                p.materia,
                p.lider,
                u.correo,
                p.telefono,
                p.direccion,
                CASE u.activo WHEN 1 THEN 'Activo' ELSE 'Inactivo' END AS estado,
                u.fecha_registro AS fecha_de_registro
              FROM usuarios u
              JOIN profesores p ON p.usuario_id = u.id
              WHERE u.rol = "rol_profesor"
                AND u.activo = 1;
            ''').fetchall()
            return jsonify([dict(r) for r in rows]), 200
    finally:
        conn.close()


@app.route('/api/profesores/<int:id>', methods=['PUT'])
@login_required
def update_profesor(id):
    data = request.get_json()
    conn = get_db_connection()
    # Si cambiamos estado
    if 'estado' in data:
        activo = 1 if data['estado']=='Activo' else 0
        conn.execute('UPDATE usuarios SET activo=? WHERE id=?',(activo,id))
    else:
        # Actualizar datos usuario
        nombre_comp = f"{data['nombre']} {data['apellido']}"
        conn.execute('''
          UPDATE usuarios
          SET nombre=?, nombre_usuario=?, correo=?
          WHERE id=?
        ''',(nombre_comp, data['nombre_usuario'], data['correo'], id))
        # Actualizar detalles de profesor
        conn.execute('''
          UPDATE profesores
          SET experiencia=?, materia=?, lider=?, telefono=?, direccion=?
          WHERE usuario_id=?
        ''',(
          data['experiencia'], data['materia'], data['lider'],
          data['telefono'], data['direccion'], id
        ))
    conn.commit()
    conn.close()
    return jsonify(success=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))



if __name__=='__main__':
    init_db()
    app.run(debug=True)
