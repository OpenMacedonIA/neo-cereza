import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file, Response
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24) # Random key for client session

# Initialize CSRF Protection
csrf = CSRFProtect(app)

# Configuration
# Default to localhost if not set, but Configurator should set this.
NEO_API_URL = os.environ.get('NEO_API_URL', 'http://localhost:5000')

# Ensure URL has schema
if not NEO_API_URL.startswith(('http://', 'https://')):
    NEO_API_URL = f"http://{NEO_API_URL}"

# Remove trailing slash to avoid double slashes in paths
NEO_API_URL = NEO_API_URL.rstrip('/')

def get_headers():
    """Headers for API requests (simulate login or pass API Key)."""
    # For now, we rely on the Server being open or sharing a session cookie concept if complex.
    # But NeoCore uses session['logged_in']. 
    # HEADLESS AUTH STRATEGY:
    # 1. Login on Client -> Client calls Server /login API?
    # 2. Or Client stores a Token?
    # Current NeoCore uses session cookie. We need to proxy that.
    
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
        
        # Proxy Login to Server
        try:
            # We hit the login form endpoint of server? No, server expects session.
            # We actually need an API /login which returns a cookie or token.
            # NeoCore currently uses a standard form login.
            # Let's try to POST to /login on server and capture the cookie.
            # Disable warnings for self-signed certs
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            resp = requests.post(f"{NEO_API_URL}/login", data={'username': username, 'password': password}, allow_redirects=False, verify=False)
            
            if resp.status_code == 302 and 'dashboard' in resp.headers['Location']:
                # Success
                session['logged_in'] = True
                session['neo_session'] = resp.cookies.get('session') # Store server session cookie
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

# --- Proxy Views ---
# These views render local templates but fetch data from Server API

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
    # Fetch content from API
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

@app.route('/training')
def training():
    # Training usually needs config too for TTS/STT options logic
    try:
        headers, cookies = get_headers()
        resp = requests.get(f"{NEO_API_URL}/api/config/get", cookies=cookies, verify=False)
        data = resp.json()
        return render_template('training.html', page='training', config=data.get('config', {}))
    except:
        return render_template('training.html', page='training', config={})    

@app.route('/face')
def face():
    return render_template('face.html')

# --- API PROXY ---
# Forward all /api/* requests to NeoCore
@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_proxy(path):
    headers, cookies = get_headers()
    url = f"{NEO_API_URL}/api/{path}"
    
    try:
        if request.method == 'GET':
            resp = requests.get(url, params=request.args, cookies=cookies, verify=False)
        elif request.method == 'POST':
            # Forward JSON or Form data
            if request.is_json:
                resp = requests.post(url, json=request.json, cookies=cookies, verify=False)
            else:
                resp = requests.post(url, data=request.form, files=request.files, cookies=cookies, verify=False)
        
        # Check if response is json
        try:
            return jsonify(resp.json()), resp.status_code
        except:
            return Response(resp.content, status=resp.status_code, content_type=resp.headers['content-type'])
            
    except Exception as e:
        return jsonify({'success': False, 'message': f"Proxy Error: {e}"}), 500

if __name__ == "__main__":
    print(f"🚀 Neo Headless Client starting...")
    print(f"🔗 Connected to NeoCore at: {NEO_API_URL}")
    print(f"🌍 Web Interface at: http://0.0.0.0:8092")
    app.run(host='0.0.0.0', port=8092, debug=True)
