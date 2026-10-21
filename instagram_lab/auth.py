"""Autenticación manual independiente del scraping.

Las cookies son secretas: solo se guardan localmente y jamás se devuelven a la web.
"""
import json
from .config import SESSION_FILE

HOME = 'https://www.instagram.com/'
LOGIN = HOME + 'accounts/login/'
# Indicadores positivos: un formulario ausente no prueba autenticación.
AUTH_UI = ('a[href*="/direct/inbox"], a[href*="/explore/"], '
           'a[href*="/accounts/edit"], svg[aria-label="Inicio"], '
           'svg[aria-label="Home"]')


def persist_session(context):
    """Guarda de forma atómica cookies de una sesión previamente verificada."""
    cookies = context.cookies()
    if not any(c.get('name') == 'sessionid' and c.get('value') for c in cookies):
        raise RuntimeError('Instagram no entregó una cookie de sesión válida.')
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SESSION_FILE.with_name('cookies.json.tmp')
    tmp.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(SESSION_FILE)


def restore_session(context):
    """Inyecta cookies desde el archivo sin gestionar el inicio de sesión."""
    if not SESSION_FILE.exists():
        return False
    try:
        cookies = json.loads(SESSION_FILE.read_text(encoding='utf-8'))
        if not isinstance(cookies, list) or not cookies:
            return False
        context.add_cookies(cookies)
        return True
    except (OSError, ValueError, TypeError) as exc:
        print(f'No se pudieron restaurar cookies: {exc}')
        return False


def verified_session(page, context):
    """Comprueba una sesión mediante cookie y señales de UI autenticada."""
    if any(x in page.url.lower() for x in ('/accounts/login', '/challenge', '/two_factor', '/checkpoint', '/suspended')):
        return False
    if not any(c.get('name') == 'sessionid' and c.get('value') for c in context.cookies()):
        return False
    try:
        return page.locator(AUTH_UI).first.is_visible(timeout=2000)
    except Exception:
        return False


def verify_on_home(page, context):
    """Comprueba de forma activa la sesión en la página principal."""
    try:
        page.goto(HOME, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(1800)
        return verified_session(page, context)
    except Exception:
        return False


def load_verified_cookies(page, context):
    """Verifica cookies del disco; nunca inicia sesión ni pide contraseñas."""
    if not restore_session(context):
        raise RuntimeError('No existe cookies.json válido. Usa primero «Cargar cookies» en el panel web.')
    if not verify_on_home(page, context):
        raise RuntimeError('Las cookies han caducado o Instagram pide verificación. Usa «Cargar cookies» otra vez.')
