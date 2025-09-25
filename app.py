from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import sqlite3
from scheduler import Scheduler

app = Flask(__name__)
DB_FILE = "asignaciones.db"

# "Caché" en memoria para el último programa generado. En una app real,
# esto podría usar un sistema de caché más robusto como Redis.
schedule_cache = {}

# --- Database Setup ---
def get_db_connection():
    """Crea y configura la conexión a la base de datos."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    if os.path.exists(DB_FILE):
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla de Personas
    cursor.execute('''
        CREATE TABLE personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')

    # Tabla de Roles
    cursor.execute('''
        CREATE TABLE roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_rol TEXT NOT NULL UNIQUE
        )
    ''')

    # Tabla de Asignaciones de Roles a Personas
    cursor.execute('''
        CREATE TABLE personas_roles (
            persona_id INTEGER,
            rol_id INTEGER,
            genero TEXT, -- 'hombre', 'mujer' (para Seamos Mejores Maestros)
            grupo_edad TEXT, -- 'adulto', 'joven' (para Acomodadores)
            FOREIGN KEY (persona_id) REFERENCES personas (id) ON DELETE CASCADE,
            FOREIGN KEY (rol_id) REFERENCES roles (id) ON DELETE CASCADE,
            PRIMARY KEY (persona_id, rol_id)
        )
    ''')

    # Tabla de Historial de Asignaciones
    cursor.execute('''
        CREATE TABLE historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semana INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            asignacion_nombre TEXT NOT NULL,
            persona_id INTEGER,
            rol_secundario TEXT, -- 'principal', 'ayudante', 'sala_a', 'sala_b', etc.
            FOREIGN KEY (persona_id) REFERENCES personas (id)
        )
    ''')

    # Insertar los roles fijos
    roles = [
        'Presidente', 'Oraciones', 'Tesoros', 'Perlas', 'Lectura de la biblia',
        'Seamos mejores maestros', 'Vida y ministerio', 'Estudio del libro',
        'Lector del libro', 'Acomodadores'
    ]
    for rol in roles:
        cursor.execute("INSERT INTO roles (nombre_rol) VALUES (?)", (rol,))

    conn.commit()
    conn.close()
    print("Base de datos inicializada.")

# Inicializar la DB al arrancar
init_db()

@app.route('/')
def index():
    """Página principal que muestra la interfaz."""
    return render_template('index.html')

# --- API Endpoints ---

@app.route('/api/roles', methods=['GET'])
def get_roles():
    """Obtiene todos los roles de la base de datos."""
    conn = get_db_connection()
    roles = conn.execute('SELECT * FROM roles ORDER BY id').fetchall()
    conn.close()
    return jsonify([dict(rol) for rol in roles])

@app.route('/api/roles/<int:rol_id>/personas', methods=['GET'])
def get_personas_by_rol(rol_id):
    """Obtiene todas las personas asignadas a un rol específico."""
    conn = get_db_connection()
    query = """
        SELECT p.id, p.nombre, pr.genero, pr.grupo_edad
        FROM personas p
        JOIN personas_roles pr ON p.id = pr.persona_id
        WHERE pr.rol_id = ?
        ORDER BY p.nombre
    """
    personas = conn.execute(query, (rol_id,)).fetchall()
    conn.close()
    return jsonify([dict(p) for p in personas])

@app.route('/api/personas', methods=['POST'])
def add_persona():
    """Añade una o más personas y las asigna a un rol."""
    data = request.json
    nombres = data.get('nombres', [])
    rol_id = data.get('rol_id')
    genero = data.get('genero')
    grupo_edad = data.get('grupo_edad')

    if not nombres or not rol_id:
        return jsonify({'success': False, 'errors': 'Faltan nombres o el ID del rol.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    errors = []

    for nombre in nombres:
        try:
            # 1. Encontrar o crear la persona
            cursor.execute("SELECT id FROM personas WHERE nombre = ?", (nombre,))
            persona = cursor.fetchone()
            if persona:
                persona_id = persona['id']
            else:
                cursor.execute("INSERT INTO personas (nombre) VALUES (?)", (nombre,))
                persona_id = cursor.lastrowid

            # 2. Asignar el rol a la persona
            cursor.execute(
                """
                INSERT INTO personas_roles (persona_id, rol_id, genero, grupo_edad)
                VALUES (?, ?, ?, ?)
                """,
                (persona_id, rol_id, genero, grupo_edad)
            )
        except sqlite3.IntegrityError:
            # Esto puede pasar si la persona ya existe o si la asignación de rol ya existe
            errors.append(f"'{nombre}' ya está en la base de datos o ya tiene este rol.")
            continue
        except Exception as e:
            errors.append(f"Error con '{nombre}': {str(e)}")
            continue

    if errors:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'errors': errors}), 500

    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/personas/<int:persona_id>/roles/<int:rol_id>', methods=['DELETE'])
def delete_persona_from_rol(persona_id, rol_id):
    """Elimina la asignación de un rol a una persona."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM personas_roles WHERE persona_id = ? AND rol_id = ?",
            (persona_id, rol_id)
        )
        # Opcional: si la persona no tiene más roles, eliminarla de la tabla personas
        cursor.execute("SELECT COUNT(*) as count FROM personas_roles WHERE persona_id = ?", (persona_id,))
        if cursor.fetchone()['count'] == 0:
            cursor.execute("DELETE FROM personas WHERE id = ?", (persona_id,))

        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/generate_schedule', methods=['POST'])
def generate_schedule_endpoint():
    config = request.json

    conn = get_db_connection()

    # Obtener todos los participantes con sus roles y atributos
    participants_raw = conn.execute("""
        SELECT p.id as persona_id, p.nombre, r.nombre_rol, pr.genero, pr.grupo_edad
        FROM personas p
        JOIN personas_roles pr ON p.id = pr.persona_id
        JOIN roles r ON pr.rol_id = r.id
    """).fetchall()

    # Obtener todo el historial
    history_raw = conn.execute("SELECT * FROM historial").fetchall()

    conn.close()

    # Convertir a diccionarios
    participants_data = [dict(p) for p in participants_raw]
    history_data = [dict(h) for h in history_raw]

    # Crear y ejecutar el planificador
    scheduler = Scheduler(config, participants_data, history_data)
    schedule_result = scheduler.generate_schedule()

    # Guardar en caché el resultado y la instancia del planificador para futuras consultas
    schedule_cache['last_schedule'] = schedule_result
    schedule_cache['last_scheduler_instance'] = scheduler

    return jsonify(schedule_result)


@app.route('/api/candidates', methods=['GET'])
def get_candidates():
    slot_key = request.args.get('slot_key')
    week_index = int(request.args.get('week_index'))

    last_schedule = schedule_cache.get('last_schedule')
    scheduler = schedule_cache.get('last_scheduler_instance')

    if not last_schedule or not scheduler:
        return jsonify({"error": "No schedule generated yet"}), 404

    # Encontrar las personas ya asignadas en esa semana
    assigned_this_week = set()
    for assignment in last_schedule['weeks'][week_index]['assignments']:
        for slot in assignment['slots']:
            if slot.get('persona_id'):
                assigned_this_week.add(slot['persona_id'])

    # Determinar el rol/subrol a partir de la clave del slot
    # Esta es una lógica inversa simple, podría necesitar ser más robusta
    # Ejemplo: 'SMM_1_principal' -> role_key='smm_hombre/mujer', role_name='Seamos mejores maestros', sub_role='principal'
    # Esta parte es compleja y depende de la estructura de slot_key. Asumiremos una estructura predecible.

    # Lógica de ejemplo para encontrar el rol original (necesita ser robusta)
    # Por simplicidad, en este prototipo, vamos a recargar todos los participantes de un rol genérico.
    # Una implementación real mapearía slot_key de vuelta a la configuración de `find_candidate`.
    # Esto es una simplificación para avanzar.

    # Fake logic para encontrar el rol correcto (¡Simplificación!)
    role_key = None
    role_name = None
    sub_role = None

    # Esta es una aproximación. Una solución real necesitaría un mapeo inverso robusto.
    if "Presidente" in slot_key: role_key, role_name = "Presidente", "Presidente"
    elif "Oracion" in slot_key: role_key, role_name = "Oraciones", "Oracion"
    elif "Tesoros" in slot_key: role_key, role_name = "Tesoros", "Tesoros"
    elif "Perlas" in slot_key: role_key, role_name = "Perlas", "Perlas"
    elif "Lectura" in slot_key: role_key, role_name = "Lectura de la biblia", "Lectura de la biblia"
    elif "SMM" in slot_key:
        role_name = "Seamos mejores maestros"
        # Necesitaríamos saber el género de la configuración original. ¡Esto es complicado!
        # Por ahora, simplemente no filtraremos por género en la búsqueda de candidatos.
        role_key = "Seamos mejores maestros"
    elif "Acomodadores" in slot_key: role_key, role_name = "Acomodadores", "Acomodadores"
    else: role_key, role_name = "Vida y ministerio", "Vida y ministerio"


    if not role_key:
        return jsonify([])

    # Reutilizamos la lógica de find_candidate pero solo para obtener una lista
    all_participants_for_role = scheduler.participants_by_role.get(role_key, [])

    candidates = []
    for p in all_participants_for_role:
        if p['persona_id'] not in assigned_this_week:
            candidates.append({'persona_id': p['persona_id'], 'nombre': p['nombre']})

    return jsonify(candidates)


@app.route('/api/save_schedule', methods=['POST'])
def save_schedule():
    data = request.json
    year = data.get('year')
    month = data.get('month')
    weeks_data = data.get('weeks', [])

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for week in weeks_data:
            week_index = week.get('week_index')
            for assignment in week.get('assignments', []):
                for slot in assignment.get('slots', []):
                    # Solo guardar si hay una persona asignada
                    if slot.get('person_id'):
                        cursor.execute("""
                            INSERT INTO historial (semana, mes, anio, asignacion_nombre, persona_id, rol_secundario)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            week_index + 1, # Guardar semana como 1, 2, 3, 4
                            month,
                            year,
                            assignment.get('title'),
                            slot.get('person_id'),
                            slot.get('slot_key') # Usar slot_key como identificador del rol secundario
                        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"success": True})


@app.route('/api/history', methods=['GET'])
def get_history():
    conn = get_db_connection()
    history_data = conn.execute("""
        SELECT h.anio, h.mes, h.semana, h.asignacion_nombre, p.nombre
        FROM historial h
        JOIN personas p ON h.persona_id = p.id
        ORDER BY h.anio DESC, h.mes DESC, h.semana DESC, h.id
    """).fetchall()
    conn.close()
    return jsonify([dict(row) for row in history_data])


if __name__ == '__main__':
    # Asegurarse de que la DB se inicializa antes de correr la app
    with app.app_context():
        init_db()
    app.run(debug=True, port=5001)