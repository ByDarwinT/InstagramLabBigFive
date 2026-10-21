import re
from datetime import datetime
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .config import RESULTS_DIR
from .utils import random_pause


def collect_post_urls(page, profile_url: str, max_posts: int) -> list[str]:
    """Recolecta las URLs de los posts de un perfil."""
    print(f"\n📂 Visitando perfil: {profile_url}")
    page.goto(profile_url, timeout=30000)
    random_pause(2, 4)

    post_urls = set()
    last_count = 0
    stall_rounds = 0

    print(f"🔍 Recolectando URLs de posts (objetivo: {max_posts})...")

    while len(post_urls) < max_posts:
        anchors = page.locator('a[href*="/p/"]').all()
        for a in anchors:
            href = a.get_attribute("href")
            if href and "/p/" in href:
                post_urls.add("https://www.instagram.com" + href.split("?")[0])

        print(f"  → {len(post_urls)} URLs encontradas", end="\r")

        if len(post_urls) >= max_posts:
            break

        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        random_pause(2, 4)

        if len(post_urls) == last_count:
            stall_rounds += 1
            if stall_rounds >= 3:
                print("\n⚠️  No se encontraron más posts.")
                break
        else:
            stall_rounds = 0

        last_count = len(post_urls)

    final = list(post_urls)[:max_posts]
    print(f"\n✅ {len(final)} URLs recolectadas.")
    return final


def extract_post_data(page, post_url: str, index: int) -> dict | None:
    """Extrae todos los datos de un post individual."""
    try:
        page.goto(post_url, wait_until="networkidle", timeout=30000)
        random_pause(2, 4)

        page.evaluate("window.scrollBy(0, 100)")
        random_pause(1, 2)

        data = {
            "url": post_url,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "caption": None,
            "likes": None,
            "date": None,
            "media_urls": [],
        }

        # ── 1. Fecha ──────────────────────────────────────────────────
        try:
            time_el = page.locator("time").first
            data["date"] = time_el.get_attribute("datetime", timeout=3000)
        except Exception:
            pass

        # ── 2 y 3. Caption, Likes y Comentarios vía meta tag ──────────
        try:
            meta_locator = page.locator('meta[property="og:description"], meta[name="description"]').first
            content = meta_locator.get_attribute("content", timeout=3000)

            if content:
                if ":" in content:
                    data["caption"] = content.split(":", 1)[1].strip().strip('"').strip('\u201c').strip('\u201d')
                else:
                    data["caption"] = content

                likes_match = re.search(r'([\d,.]+)\s*(likes|Me gusta)', content, re.IGNORECASE)
                if likes_match:
                    data["likes"] = likes_match.group(1).replace(',', '')

                comments_match = re.search(r'([\d,.]+)\s*(comments|comentarios)', content, re.IGNORECASE)
                if comments_match:
                    data["comments_count"] = comments_match.group(1).replace(',', '')

        except Exception as e:
            print(f"    [!] Aviso: No se pudo extraer la etiqueta meta en {post_url}: {e}")

        # ── 4. Imágenes y Videos ──────────────────────────────────────
        try:
            imgs = page.locator('img[style*="object-fit: cover"]').all()
            for img in imgs:
                src = img.get_attribute("src")
                if src and ("scontent" in src or "fbcdn" in src or "instagram" in src):
                    if src not in data["media_urls"]:
                        data["media_urls"].append(src)

            videos = page.locator("video").all()
            for vid in videos:
                src = vid.get_attribute("src")
                if src and src not in data["media_urls"]:
                    data["media_urls"].append(src)
        except Exception:
            pass

        print(f"  [{index}] ✅ Post extraído: {post_url}")
        return data

    except PlaywrightTimeoutError:
        print(f"  [{index}] ⏱️  Timeout cargando {post_url}")
        page.screenshot(path=RESULTS_DIR / f"timeout_post_{index}.png")
        return None
    except Exception as e:
        print(f"  [{index}] ❌ Error en {post_url}: {e}")
        return None

# ── Información pública del perfil ──────────────────────────────────────────

# Admite contadores como: 1234, 1.234, 1,234, 1,2 mil, 12.5K, 2M.
_COUNT_NUMBER = r"(\d+(?:[.,\u00a0\u202f ]\d+)*(?:\s*(?:mil|millones?|mill[oó]n|millions?|million|[kKmMbB]))?)"
_COUNT_LABELS = {
    "seguidores": r"seguidores|followers",
    "seguidos": r"seguidos|siguiendo|following",
    "total_publicaciones": r"publicaciones|publicaci[oó]n|posts?",
}


def _parse_count(value: str) -> int | None:
    """Convierte un contador visible a entero; los valores abreviados son aproximados."""
    if not value:
        return None
    value = value.strip().lower().replace("\u00a0", " ").replace("\u202f", " ")
    match = re.fullmatch(
        r"([\d., ]+?)\s*(mil|millones?|mill[oó]n|millions?|million|[kmb])?", value
    )
    if not match:
        return None

    numeric = match.group(1).strip().replace(" ", "")
    unit = match.group(2)
    factor = (1_000 if unit in ("k", "mil")
              else 1_000_000 if unit in ("m", "millon", "millón", "millones", "million", "millions")
              else 1_000_000_000 if unit == "b" else 1)

    if factor != 1:
        # Con un sufijo K/M/mil, el último separador suele ser decimal.
        separator = max(numeric.rfind(","), numeric.rfind("."))
        if separator != -1:
            integer_part = re.sub(r"[.,]", "", numeric[:separator]) or "0"
            numeric = integer_part + "." + numeric[separator + 1:]
    elif "," in numeric or "." in numeric:
        # Sin sufijo: «1.234» y «1,234» son separadores de miles.
        pieces = re.split(r"[.,]", numeric)
        if len(pieces) > 1 and all(len(piece) == 3 for piece in pieces[1:]):
            numeric = "".join(pieces)
        elif "," in numeric and "." in numeric:
            # Ej.: 1.234,56 y 1,234.56 (casos atípicos para contadores).
            separator = max(numeric.rfind(","), numeric.rfind("."))
            numeric = re.sub(r"[.,]", "", numeric[:separator]) + "." + numeric[separator + 1:]
        else:
            numeric = numeric.replace(",", ".")

    try:
        return int(round(float(numeric) * factor))
    except ValueError:
        return None


def _extract_labeled_count(text: str, label: str) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    pattern = rf"{_COUNT_NUMBER}\s*(?:{_COUNT_LABELS[label]})\b"
    found = re.search(pattern, text, flags=re.IGNORECASE)
    if not found:
        return None, None
    raw = found.group(1).strip()
    return _parse_count(raw), raw


def _get_meta(page, selector: str) -> str | None:
    try:
        return page.locator(selector).first.get_attribute("content", timeout=1500)
    except Exception:
        return None


def _profile_display_name(page, header, username: str) -> str | None:
    # El título/OG contiene a menudo «Nombre (@usuario) • Instagram».
    titles = [_get_meta(page, 'meta[property="og:title"]')]
    try:
        titles.append(page.title())
    except Exception:
        pass

    for title in titles:
        if not title:
            continue
        pattern = rf"^(.+?)\s*\(@?{re.escape(username)}\)"
        found = re.search(pattern, title, flags=re.IGNORECASE)
        if found:
            return found.group(1).strip()

    # Alternativa accesible cuando el título no incluye el nombre.
    try:
        for heading in header.locator("h1, h2").all_inner_texts():
            heading = heading.strip()
            if heading and heading.casefold().lstrip("@") != username.casefold():
                if len(heading) <= 120 and not re.search(r"seguidores|followers|following|seguidos", heading, re.I):
                    return heading
    except Exception:
        pass
    return None


def _profile_bio(header, username: str, display_name: str | None) -> str | None:
    # Instagram suele marcar líneas de biografía con dir="auto".
    try:
        candidates = header.locator('[dir="auto"]').all_inner_texts()
    except Exception:
        return None

    exclude = {username.casefold(), f"@{username}".casefold(),
               (display_name or "").casefold(), "seguir", "siguiendo",
               "follow", "following", "mensaje", "message", "contactar",
               "contact", "ver traducción", "see translation", "threads"}
    valid = []
    for candidate in candidates:
        candidate = candidate.strip()
        if (not candidate or len(candidate) > 500 or candidate.casefold() in exclude
                or re.search(r"^(?:https?://|www\.)", candidate, re.I)
                or any(_extract_labeled_count(candidate, label)[0] is not None for label in _COUNT_LABELS)):
            continue
        if candidate not in valid:
            valid.append(candidate)

    # Antes se devolvía None si había más de un candidato, algo común
    # porque Instagram usa dir="auto" en varios elementos del perfil.
    # Conservamos los textos completos que engloban fragmentos pequeños
    # y elegimos el más descriptivo; no afecta al resto del scraper.
    if not valid:
        print("    ⚠️ No aparecieron candidatos a biografía en [dir='auto'].")
        try:
            print("    🔎 Cabecera visible (diagnóstico):", repr(header.inner_text()[:1200]))
        except Exception:
            pass
        return None

    # Evita seleccionar un fragmento cuando también está disponible el
    # bloque completo de la biografía (por ejemplo, varias líneas).
    completos = [
        texto for texto in valid
        if not any(texto != otro and texto in otro for otro in valid)
    ]
    # En caso de empate gana el candidato que aparece más tarde.
    return max(enumerate(completos), key=lambda item: (len(item[1]), item[0]))[1]


def _profile_photo(page, header, username: str):
    """Busca la imagen del avatar en la cabecera; evita elegir imágenes de publicaciones."""
    from urllib.parse import urlparse
    candidates = header.locator('img')
    for i in range(min(candidates.count(), 20)):
        img = candidates.nth(i)
        alt = (img.get_attribute("alt") or "").lower()
        if ("profile picture" in alt or "foto del perfil" in alt or
            "foto de perfil" in alt or "imagen del perfil" in alt or
            username.lower() in alt or "profile_pic" in (img.get_attribute("src") or "")):
            url = img.get_attribute("src")
            if url and urlparse(url).scheme in ("https", "http"):
                return url
    # Fallback a la metadata, si está disponible.
    url = _get_meta(page, 'meta[property="og:image"]')
    if url and urlparse(url).scheme in ("https", "http"):
        return url
    return None


def _save_profile_photo(page, url: str, username: str):
    """Descarga el avatar con la sesión del navegador, si Instagram lo permite."""
    from urllib.parse import urlparse
    from pathlib import Path
    try:
        response = page.context.request.get(url, timeout=15000)
        if not response.ok:
            print(f"  ⚠️ Foto no descargada (HTTP {response.status}).")
            return None
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type)
        if ext is None:
            print("  ⚠️ La respuesta no es una imagen compatible.")
            return None
        body = response.body()
        if len(body) > 10 * 1024 * 1024:
            print("  ⚠️ Imagen demasiado grande; no se guardó.")
            return None
        folder = RESULTS_DIR / "fotos_perfil"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{username}{ext}"
        path.write_bytes(body)
        return str(path)
    except Exception as exc:
        print(f"  ⚠️ No se pudo descargar la foto: {exc}")
        return None


def extract_profile_data(page, profile_url: str) -> dict:
    """Extrae datos visibles del perfil, sin APIs privadas ni llamadas adicionales.

    Si un dato no está disponible se guarda como None, en lugar de atribuirle 0.
    """
    from urllib.parse import urlparse
    from datetime import timezone

    parsed = urlparse(profile_url)
    username = parsed.path.strip("/").split("/")[0]
    if parsed.hostname not in ("instagram.com", "www.instagram.com") or not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
        raise ValueError("Introduce la URL de un perfil de Instagram válido.")
    profile_url = f"https://www.instagram.com/{username}/"

    data = {
        "username": username,
        "nombre": None,
        "biografia": None,
        "foto_perfil_url": None,
        "foto_perfil_archivo": None,
        "seguidores": None,
        "seguidos": None,
        "total_publicaciones": None,
        "contadores_originales": {},
        "url": profile_url,
        "scraped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    print(f"\n👤 Extrayendo información de @{username}...")

    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        header = page.locator("header").first
        header.wait_for(state="visible", timeout=15000)
        random_pause(1, 2)

        header_text = header.inner_text(timeout=5000)
        metadata = "\n".join(filter(None, [
            _get_meta(page, 'meta[name="description"]'),
            _get_meta(page, 'meta[property="og:description"]'),
        ]))

        for field in _COUNT_LABELS:
            # Se prefieren contadores exactos del atributo title, si existen.
            if field in ("seguidores", "seguidos"):
                subpath = "followers" if field == "seguidores" else "following"
                try:
                    link = header.locator(f'a[href*="/{subpath}/"]').first
                    tooltip = link.locator("[title]").first.get_attribute("title", timeout=1000)
                    count = _parse_count(tooltip or "")
                    if count is not None:
                        data[field] = count
                        data["contadores_originales"][field] = tooltip
                        continue
                except Exception:
                    pass

            for text in (header_text, metadata):
                count, raw = _extract_labeled_count(text, field)
                if count is not None:
                    data[field] = count
                    data["contadores_originales"][field] = raw
                    break

        data["nombre"] = _profile_display_name(page, header, username)
        data["biografia"] = _profile_bio(header, username, data["nombre"])
        data["foto_perfil_url"] = _profile_photo(page, header, username)
        if data["foto_perfil_url"]:
            data["foto_perfil_archivo"] = _save_profile_photo(page, data["foto_perfil_url"], username)
        missing = [key for key in ("nombre", "biografia", "seguidores", "seguidos", "total_publicaciones")
                   if data[key] is None]
        if missing:
            print(f"  ⚠️ Campos no confirmados: {', '.join(missing)}")
        else:
            print("  ✅ Datos principales del perfil extraídos.")

    except PlaywrightTimeoutError:
        print("  ⚠️ No se pudo confirmar la cabecera del perfil (timeout).")
    except Exception as exc:
        print(f"  ⚠️ No se pudo completar la extracción del perfil: {exc}")

    return data
