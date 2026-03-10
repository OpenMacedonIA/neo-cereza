import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file, Response
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24) # Clave aleatoria para la sesión del cliente

@app.context_processor
def inject_socket_url():
    return dict(socket_url=NEO_API_URL)

# Inicializar Protección CSRF
csrf = CSRFProtect(app)

# Configuración
# Por defecto a localhost si no está configurado, pero el Configurator debería establecer esto.
NEO_API_URL = os.environ.get('NEO_API_URL', 'http://localhost:5000')

# Asegurar que la URL tenga el esquema
if not NEO_API_URL.startswith(('http://', 'https://')):
    NEO_API_URL = f"http://{NEO_API_URL}"

# Eliminar barra diagonal final para evitar barras dobles en rutas
NEO_API_URL = NEO_API_URL.rstrip('/')

def get_headers():
    """Cabeceras para peticiones API (simula inicio de sesión o pasa API Key)."""
    # Por ahora, dependemos de que el Servidor esté abierto o compartiremos un concepto de cookie de sesión si es complejo.
    # Pero NeoCore usa session['logged_in']. 
    # ESTRATEGIA DE AUTENTICACIÓN HEADLESS:
    # 1. Login en Cliente -> Cliente llama a Servidor /login API?
    # 2. ¿O el Cliente almacena un Token?
    # El NeoCore actual usa cookie de sesión. Necesitamos hacer proxy a eso.
    
    cookies = {}
    if 'neo_session' in session:
        cookies['session'] = session['neo_session']
    return {}, cookies

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Proxy Login al Servidor
        try:
            # ¿Afectamos al endpoint del formulario de inicio de sesión del servidor? No, el servidor espera la sesión.
            # En realidad necesitamos una API /login que devuelva una cookie o token.
            # NeoCore actualmente usa un inicio de sesión de formulario estándar.
            # Intentemos hacer POST a /login en el servidor y capturar la cookie.
            # Desactivar advertencias para certificados autofirmados
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            resp = requests.post(f"{NEO_API_URL}/login", data={'username': username, 'password': password}, allow_redirects=False, verify=False)
            
            if resp.status_code == 302 and 'dashboard' in resp.headers['Location']:
                # Éxito
                session['logged_in'] = True
                session['neo_session'] = resp.cookies.get('session') # Almacenar cookie de sesión del servidor
                return redirect(url_for('dashboard'))
            else:
                error = "Login fallido en servidor NeoCore."
        except Exception as e:
            error = f"No se pudo conectar con NeoCore ({NEO_API_URL}): {e}"
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Vistas Proxy ---
# Estas vistas renderizan plantillas locales pero obtienen datos de la API del Servidor

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', page='dashboard')

@app.route('/services')
def services():
    return render_template('services.html', page='services')

@app.route('/docker')
def docker_page():
    return render_template('docker.html', page='docker')

@app.route('/tasks')
def tasks_page():
    return render_template('tasks.html', page='tasks')

@app.route('/network')
def network():
    return render_template('network.html', page='network')

@app.route('/actions')
def actions():
    return render_template('actions.html', page='actions')

@app.route('/terminal')
def terminal():
    return render_template('terminal.html', page='terminal')

@app.route('/logs')
def logs():
    return render_template('logs.html', page='logs')

@app.route('/monitor')
def monitor():
    return render_template('monitor.html', page='monitor')

@app.route('/speech')
def speech():
    return render_template('speech.html', page='speech')

@app.route('/settings')
def settings():
    # Obtener contenido de la API
    try:
        headers, cookies = get_headers()
        resp = requests.get(f"{NEO_API_URL}/api/config/get", cookies=cookies, verify=False)
        data = resp.json()
        return render_template('settings.html', page='settings', config=data.get('config',{}), voices=data.get('voices',[]), models=data.get('models',[]))
    except Exception as e:
        return f"Error connecting to NeoCore: {e}"

@app.route('/ssh')
def ssh_page():
    return render_template('ssh.html', page='ssh')

@app.route('/explorer')
def explorer():
    return render_template('explorer.html', page='explorer')

@app.route('/knowledge')
def knowledge():
    return render_template('knowledge.html', page='knowledge')

@app.route('/skills')
def skills():
    try:
        headers, cookies = get_headers()
        resp = requests.get(f"{NEO_API_URL}/api/skills", cookies=cookies, verify=False)
        return render_template('skills.html', page='skills', config=resp.json())
    except:
        return render_template('skills.html', page='skills', config={})



@app.route('/face')
def face():
    try:
        # Check config to serve legacy or new simple UI
        headers, cookies = get_headers()
        resp = requests.get(f"{NEO_API_URL}/api/config/get", cookies=cookies, verify=False, timeout=2)
        if resp.status_code == 200:
            config_data = resp.json().get('config', {})
            # Read a custom flag for legacy UI
            if config_data.get('tangerine', {}).get('use_legacy_face', False):
                return render_template('face_legacy.html')
    except Exception as e:
        print(f"Warning: Could not fetch config for face UI: {e}")
        
    # Serve new simple UI by default
    return render_template('face.html')

# --- API PROXY ---
# Reenviar todas las peticiones /api/* a NeoCore
@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_proxy(path):
    headers, cookies = get_headers()
    url = f"{NEO_API_URL}/api/{path}"
    
    try:
        if request.method == 'GET':
            resp = requests.get(url, params=request.args, cookies=cookies, verify=False)
        elif request.method == 'POST':
            # Reenviar datos JSON o Formulario
            if request.is_json:
                resp = requests.post(url, json=request.json, cookies=cookies, verify=False)
            else:
                resp = requests.post(url, data=request.form, files=request.files, cookies=cookies, verify=False)
        
        # Comprobar si la respuesta es json
        try:
            return jsonify(resp.json()), resp.status_code
        except:
            return Response(resp.content, status=resp.status_code, content_type=resp.headers['content-type'])
            
    except Exception as e:
        return jsonify({'success': False, 'message': f"Proxy Error: {e}"}), 500

if __name__ == "__main__":
    import glob

    # ── Detección automática de certificados SSL (mkcert) ──────────────
    # Busca en variables de entorno primero, luego en el directorio padre
    # del proyecto (donde mkcert genera los archivos por defecto).
    ssl_cert = os.environ.get('SSL_CERT')
    ssl_key  = os.environ.get('SSL_KEY')

    if not ssl_cert or not ssl_key:
        # mkcert genera los certs en el CWD donde se ejecuta.
        # Buscamos en el dir padre de TangerineUI (la raíz del proyecto)
        # y también en el CWD actual.
        # Buscar en todos los homes /home/*/WatermelonD (funciona con cualquier usuario de VM)
        extra_dirs = glob.glob('/home/*/WatermelonD') + glob.glob('/root/WatermelonD')
        search_dirs = [
            os.path.join(os.path.dirname(__file__), '..'),   # raíz ~/Música/WatermelonD
            os.path.dirname(__file__),                         # TangerineUI/
            os.path.expanduser('~/WatermelonD'),               # ~/WatermelonD del usuario actual
            os.path.expanduser('~'),                           # home dir
            os.getcwd(),                                       # directorio de trabajo actual
        ] + extra_dirs
        for d in search_dirs:
            # mkcert nombra la clave como *-key.pem
            keys = glob.glob(os.path.join(d, '*-key.pem'))
            if keys:
                ssl_key  = keys[0]
                # El cert tiene el mismo prefijo sin '-key'
                ssl_cert = ssl_key.replace('-key.pem', '.pem')
                if os.path.exists(ssl_cert):
                    break
                else:
                    ssl_cert = ssl_key = None  # par incompleto, seguir buscando

    # ── Arranque ───────────────────────────────────────────────────────
    if ssl_cert and ssl_key and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
        port = int(os.environ.get('PORT', 8443))
        print(f"[START] Neo Headless Client starting (HTTPS)...")
        print(f"[LINK]  Connected to NeoCore at: {NEO_API_URL}")
        print(f"[CERT]  Certificate : {ssl_cert}")
        print(f"[CERT]  Key          : {ssl_key}")
        print(f"[WEB]  Web Interface at: https://0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, ssl_context=(ssl_cert, ssl_key))
    else:
        port = int(os.environ.get('PORT', 8000))
        print(f"[START] Neo Headless Client starting (HTTP — no SSL certs found)...")
        print(f"[LINK]  Connected to NeoCore at: {NEO_API_URL}")
        print(f"[WARN]  getUserMedia() solo funcionará en localhost sin HTTPS.")
        print(f"[WEB]  Web Interface at: http://0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port)

