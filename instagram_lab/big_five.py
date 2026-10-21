"""Análisis *exploratorio del lenguaje publicado*, no diagnóstico de personalidad.

Envía solamente captions/textos al proveedor configurado mediante variables de entorno.
No transmite cookies, contraseñas, imágenes ni lista de seguidores.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import RESULTS_DIR

TRAITS = (
    ('apertura', 'Apertura a experiencias'),
    ('responsabilidad', 'Responsabilidad'),
    ('extraversion', 'Extraversión'),
    ('amabilidad', 'Amabilidad'),
    ('neuroticismo', 'Neuroticismo / emocionalidad negativa'),
)

SYSTEM_PROMPT = '''Eres un analista de CONTENIDO TEXTUAL para un proyecto universitario.
No tienes acceso a la personalidad real del autor. NO infieras ni afirmes rasgos psicológicos de una persona a partir de redes sociales.
Tu tarea es identificar, únicamente en el texto proporcionado, indicios narrativos y temas relacionados de modo orientativo con las cinco dimensiones Big Five: apertura, responsabilidad, extraversión, amabilidad y neuroticismo.
Devuelve 5 valores de 0 a 100 como grado de PRESENCIA DE SEÑALES TEXTUALES por dimensión, NUNCA puntuaciones de personalidad, percentiles o diagnóstico. 0 indica sin señales textuales; no implica rasgo bajo.
Usa como evidencia exclusiva los fragmentos de publicaciones con su número de referencia. No inventes citas ni uses información personal adicional. Un texto promocional, breve o de terceros puede no representar al autor: declara esa limitación.
Si faltan textos útiles, responde evidencia_insuficiente=true y asigna null a los cinco valores.
Respuesta SOLO JSON válido con el esquema:
{"evidencia_insuficiente":false,"resumen":"...","dimensiones":{"apertura":{"valor":40,"razon":"...","referencias":[1]},"responsabilidad":{"valor":20,"razon":"...","referencias":[2]},"extraversion":{"valor":30,"razon":"...","referencias":[1]},"amabilidad":{"valor":10,"razon":"...","referencias":[2]},"neuroticismo":{"valor":0,"razon":"No aparecen señales textuales suficientes","referencias":[]}},"limitaciones":"..."}
Sé prudente con la valoración, no supongas estados emocionales o diagnósticos. Razones cortas en español.'''


def _api_url() -> str:
    base = os.getenv('BIGFIVE_API_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions').strip()
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('BIGFIVE_API_URL debe ser una URL https válida.')
    return base


def build_evidence(scrape_json: dict) -> list[dict]:
    """Limita el volumen enviado y excluye datos de sesión e información privada."""
    posts = scrape_json.get('publicaciones', [])
    evidence = []
    for idx, post in enumerate(posts, 1):
        if not isinstance(post, dict):
            continue
        text = re.sub(r'\s+', ' ', str(post.get('caption') or '')).strip()
        if not text or text.lower() in {'none', 'null'}:
            continue
        evidence.append({'numero': idx, 'texto': text[:1200]})
        if len(evidence) >= 25:
            break
    return evidence


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw).strip()
    return json.loads(raw)


def validate_analysis(result: dict, evidence: list[dict]) -> dict:
    if not isinstance(result, dict) or not isinstance(result.get('dimensiones'), dict):
        raise ValueError('La API devolvió un formato distinto al esperado.')
    insufficient = result.get('evidencia_insuficiente') is True
    valid_refs = {e['numero'] for e in evidence}
    clean = {}
    for key, label in TRAITS:
        item = result['dimensiones'].get(key)
        if not isinstance(item, dict):
            raise ValueError(f'Falta la dimensión {key}.')
        value = item.get('valor')
        if insufficient:
            value = None
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 100:
            raise ValueError(f'Valor inválido para {key}.')
        refs = item.get('referencias', [])
        if not isinstance(refs, list):
            refs = []
        clean[key] = {
            'etiqueta': label,
            'valor': round(value) if value is not None else None,
            'razon': str(item.get('razon') or '')[:500],
            'referencias': [r for r in refs if type(r) is int and r in valid_refs][:5],
        }
    return {
        'tipo': 'señales textuales exploratorias (no test de personalidad)',
        'evidencia_insuficiente': insufficient,
        'resumen': str(result.get('resumen') or '')[:800],
        'dimensiones': clean,
        'limitaciones': str(result.get('limitaciones') or '')[:900],
        'publicaciones_con_texto': len(evidence),
        'creado_en': datetime.now(timezone.utc).isoformat(),
    }


def analyze_file(source: Path) -> Path:
    key = os.getenv('BIGFIVE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Falta BIGFIVE_API_KEY. Define tu clave como variable de entorno antes de ejecutar el proyecto.')
    model = os.getenv('BIGFIVE_MODEL', 'gemini-3.5-flash-lite').strip()
    if not model:
        raise RuntimeError('BIGFIVE_MODEL no puede estar vacío.')
    scrape_json = json.loads(source.read_text(encoding='utf-8'))
    evidence = build_evidence(scrape_json)
    if not evidence:
        data = validate_analysis({
            'evidencia_insuficiente': True,
            'resumen': 'No se extrajeron descripciones de publicaciones para analizar.',
            'dimensiones': {key: {'valor': None, 'razon': 'Sin texto disponible.', 'referencias': []} for key, _ in TRAITS},
            'limitaciones': 'No es posible valorar señales textuales sin publicaciones con descripción.'
        }, evidence)
    else:
        payload = {
            'model': model,
            'temperature': 0.2,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': json.dumps({'publicaciones': evidence}, ensure_ascii=False)},
            ],
        }
        request = Request(
            _api_url(),
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=90) as response:
                answer = json.load(response)
        except HTTPError as exc:
            details = exc.read(600).decode('utf-8', errors='replace')
            raise RuntimeError(f'Error de API HTTP {exc.code}: {details}') from exc
        except URLError as exc:
            raise RuntimeError(f'No se pudo conectar a la API: {exc.reason}') from exc
        try:
            content = answer['choices'][0]['message']['content']
            data = validate_analysis(_extract_json(content), evidence)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f'La API no devolvió un análisis JSON válido: {exc}') from exc
    destination = RESULTS_DIR / f'{source.stem}_bigfive.json'
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return destination
