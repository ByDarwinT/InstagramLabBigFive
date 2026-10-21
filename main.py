"""Punto de entrada único de InstagramLab.

Ejecuta el panel web local con `python main.py`.
Para usar la consola: `python main.py --cli usuario --posts 3`.
"""
import argparse
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="InstagramLab: panel web y extractor de Instagram")
    parser.add_argument("--cli", metavar="PERFIL", help="Ejecuta extracción desde consola, sin interfaz")
    parser.add_argument("--posts", type=int, default=2, help="Número de publicaciones (modo --cli)")
    parser.add_argument("--no-browser", action="store_true", help="No abrir automáticamente el navegador")
    args = parser.parse_args()

    if args.cli:
        from instagram_lab.service import run_scrape
        print("Resultado:", run_scrape(args.cli, args.posts))
        return

    # Importar Flask solo después de interpretar argumentos mantiene este módulo simple.
    from web import app
    url = "http://127.0.0.1:5000"
    print(f"InstagramLab disponible en {url}")
    print("Para detenerlo, presiona Ctrl+C en esta terminal.")
    if not args.no_browser:
        # La apertura del navegador es opcional; el servidor corre en el hilo principal.
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
