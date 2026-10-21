"""Panel web local de dos etapas: autenticación manual y extracción."""
from pathlib import Path
from threading import Thread, Lock, Event
import time
from flask import Flask, jsonify, render_template, request, send_from_directory
from playwright.sync_api import sync_playwright
from instagram_lab.config import RESULTS_DIR
from instagram_lab.auth import LOGIN, restore_session, persist_session, verify_on_home
from instagram_lab.service import normalize_profile, run_scrape
from instagram_lab.big_five import analyze_file

app = Flask(__name__)
app.json.ensure_ascii = False
app.config['MAX_CONTENT_LENGTH'] = 4096
lock = Lock()
confirmation = Event()
auth = {'status': 'idle', 'events': [], 'error': None}
job = {'status': 'idle', 'events': [], 'file': None, 'error': None, 'analysis': None, 'analysis_error': None}


def auth_worker():
    """Playwright se crea y utiliza íntegramente en este hilo."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1280, 'height': 800}, locale='es-ES')
            # Cookies existentes pueden facilitar un nuevo acceso, pero no se sobreescriben.
            restore_session(context)
            page = context.new_page()
            try:
                page.goto(LOGIN, wait_until='domcontentloaded', timeout=30000)
                with lock:
                    auth['events'].append('Chromium abierto. Inicia sesión o completa las verificaciones manualmente.')
                # El usuario confirma desde la web. No asumimos que un login tuvo éxito.
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    if confirmation.wait(timeout=1):
                        confirmation.clear()
                        with lock:
                            auth['events'].append('Comprobando la sesión de Instagram…')
                        if verify_on_home(page, context):
                            persist_session(context)
                            with lock:
                                auth.update(status='ready', error=None)
                                auth['events'].append('Cookies guardadas. Ya puedes iniciar el scraping.')
                            return
                        with lock:
                            auth['events'].append('Todavía no se confirmó el inicio de sesión. Completa el acceso en Chromium y vuelve a verificar.')
                    # El navegador puede ser cerrado manualmente.
                    if not browser.is_connected():
                        raise RuntimeError('Se cerró Chromium antes de guardar las cookies.')
                raise RuntimeError('El tiempo de inicio de sesión terminó. Pulsa «Cargar cookies» para volver a intentarlo.')
            finally:
                browser.close()
    except Exception as exc:
        with lock:
            auth.update(status='error', error=str(exc))


def scrape_worker(target, count):
    def progress(message):
        with lock:
            job['events'].append(message)
    try:
        output = run_scrape(target, count, progress)
        with lock:
            job['events'].append('JSON extraído. Preparando análisis textual Big Five…')
        analysis_name = None
        analysis_error = None
        try:
            analysis_path = analyze_file(output)
            analysis_name = analysis_path.name
        except Exception as exc:
            # El scraping no se considera fallido si la API está sin clave o da error.
            analysis_error = str(exc)
        with lock:
            job.update(status='complete', file=output.name,
                       analysis=analysis_name, analysis_error=analysis_error)
            if analysis_name:
                job['events'].append('Análisis exploratorio generado.')
    except Exception as exc:
        with lock:
            job.update(status='error', error=str(exc))
            # Si ha caducado, obligamos a validar nuevamente desde la etapa 1.
            if 'cookie' in str(exc).lower() or 'sesión' in str(exc).lower():
                auth['status'] = 'idle'


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/api/auth')
def auth_status():
    with lock:
        return jsonify(auth.copy())


@app.post('/api/auth/start')
def start_auth():
    with lock:
        if auth['status'] == 'running' or job['status'] == 'running':
            return jsonify(error='Hay un proceso en ejecución.'), 409
        confirmation.clear()
        auth.update(status='running', events=['Abriendo navegador para autenticación manual…'], error=None)
    Thread(target=auth_worker, daemon=True).start()
    return jsonify(status='running'), 202


@app.post('/api/auth/confirm')
def confirm_auth():
    with lock:
        if auth['status'] != 'running':
            return jsonify(error='Primero pulsa «Cargar cookies».'), 409
    confirmation.set()
    return jsonify(status='checking'), 202


@app.post('/api/jobs')
def start_job():
    body = request.get_json(silent=True) or {}
    try:
        target = normalize_profile(str(body.get('profile', '')))
        count = int(body.get('posts', 2))
        if not 1 <= count <= 100:
            raise ValueError('Selecciona entre 1 y 100 publicaciones')
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    with lock:
        if auth['status'] != 'ready':
            return jsonify(error='Primero debes cargar y validar las cookies.'), 409
        if job['status'] == 'running':
            return jsonify(error='Ya existe una extracción en curso.'), 409
        job.update(status='running', events=[], file=None, error=None, analysis=None, analysis_error=None)
    Thread(target=scrape_worker, args=(target, count), daemon=True).start()
    return jsonify(status='running'), 202


@app.get('/api/jobs')
def job_status():
    with lock:
        return jsonify(job.copy())


@app.get('/downloads/<path:filename>')
def download(filename):
    if Path(filename).name != filename or not filename.endswith('.json'):
        return jsonify(error='Archivo no permitido'), 404
    return send_from_directory(RESULTS_DIR, filename, as_attachment=True)




@app.get('/api/analysis/<path:filename>')
def get_analysis(filename):
    if Path(filename).name != filename or not filename.endswith('_bigfive.json'):
        return jsonify(error='Archivo no permitido'), 404
    with lock:
        if job.get('analysis') != filename:
            return jsonify(error='Análisis no disponible'), 404
    path = RESULTS_DIR / filename
    if not path.is_file():
        return jsonify(error='Archivo no encontrado'), 404
    return jsonify(__import__('json').loads(path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
