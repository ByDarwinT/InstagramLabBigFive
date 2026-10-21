"""Ubicaciones de sesión y resultados del proyecto (sin contraseñas)."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SESSION_FILE = BASE_DIR / "cookies.json"
RESULTS_DIR = BASE_DIR / "output"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
