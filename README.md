# InstagramLab | Extracción de información de Instagram

## Descripción

Desarrollé InstagramLab como un proyecto académico de séptimo semestre para comprender cómo funciona la extracción automatizada de información en páginas dinámicas. Utilicé **Python, Playwright y Flask**. Playwright controla Chromium y permite consultar los elementos HTML que Instagram muestra en pantalla. Flask conecta ese proceso con una interfaz web sencilla.

El programa trabaja con un perfil por ejecución. Obtiene el nombre de usuario, nombre visible, biografía, fotografía, cantidad de seguidores, seguidos y publicaciones. También busca enlaces de publicaciones y recopila algunos datos disponibles, como fecha, descripción, reacciones y contenido multimedia. Los resultados se guardan en **JSON**, junto con la foto de perfil cuando se puede descargar.

## Cómo fui desarrollándolo

Al comienzo trabajaba desde la consola y el problema principal era encontrar los enlaces de las publicaciones. Después añadí la lectura del encabezado del perfil y organicé las funciones para que la extracción y la interfaz no dependieran una de otra. Para avanzar consulté documentación técnica, ejemplos y soluciones compartidas en GitHub, contrastándolas con las pruebas de mi proyecto.

Uno de los retos fue **la autenticación**. Intentar iniciar sesión mientras se ejecutaba el scraper producía errores cuando Instagram pedía un código, una comprobación de seguridad o un CAPTCHA. Lo resolví separando el proceso en dos pasos: primero abro Chromium desde el botón **Cargar cookies**, inicio sesión manualmente y confirmo el acceso; después se guarda `cookies.json` y se habilita el scraping. Si la sesión caduca, repito esa primera etapa. Ya no necesito guardar usuario ni contraseña en `.env`.

Otro problema fue que la **biografía aparecía como `null`**. Descubrí que no bastaba con tomar el primer elemento HTML: una misma sección podía contener varios textos. Mejoré los filtros para descartar botones, contadores y nombres, y elegir un bloque más representativo. También añadí la foto de perfil: primero localizo su URL y luego intento descargar el archivo.

Aprendí además a diferenciar las esperas necesarias para cargar páginas de las pausas entre acciones. Conservé los tiempos porque quitarlos puede provocar lecturas incompletas. Al instalar Playwright encontré un error de compatibilidad entre una dependencia antigua y Python 3.13; por eso actualicé los requisitos. Finalmente agregué el panel web para controlar la autenticación y la extracción por separado.

## Estructura y ejecución

- `main.py`: inicia el panel.
- `web.py`: recibe solicitudes y muestra el progreso.
- `instagram_lab/auth.py`: verifica y guarda cookies.
- `instagram_lab/service.py`: coordina la extracción y genera el JSON.
- `instagram_lab/scraper.py`: lee perfiles y publicaciones.
- `templates/` y `static/`: interfaz.

Requiere **Python 3.10 a 3.14**, con `python` y `pip` disponibles. En la carpeta del proyecto, ejecutar:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

Se abre `http://127.0.0.1:5000`. Primero pulso **Cargar cookies**, completo el acceso en Chromium y selecciono **Verificar y guardar cookies**. Luego ingreso el perfil, la cantidad de publicaciones y descargo el JSON. La instalación anterior no crea un entorno virtual.

## Lo aprendido y mejoras futuras

Este proyecto me ayudó a comprender los selectores CSS, el DOM, las cookies, la navegación automatizada, la limpieza de datos y la comunicación entre JavaScript y Flask. También entendí que un scraper depende de la estructura de la página: algunos campos pueden no estar disponibles y los selectores pueden dejar de funcionar si Instagram cambia su interfaz. Como siguiente mejora quisiera extraer y guardar las **listas de seguidores y seguidos**, no solamente sus cantidades, siempre que el acceso esté permitido.

**Precaución:** `cookies.json` contiene datos sensibles de sesión y no debe publicarse en GitHub. Las comprobaciones de seguridad de Instagram se resuelven manualmente.


## Análisis exploratorio Big Five (opcional)

Al finalizar el scraping, el panel puede representar señales textuales relacionadas con las cinco dimensiones Big Five. **No mide la personalidad ni sustituye un cuestionario validado**. Solo analiza las descripciones de publicaciones obtenidas y explica sus conclusiones con referencias a las publicaciones. Si no hay descripciones, la gráfica indica que no hay evidencia suficiente.

Se utiliza la API gratuita de **Google Gemini**, mediante su endpoint compatible con OpenAI Chat Completions. Antes de ejecutar `python main.py`, configura en PowerShell (solo para esa ventana):

```powershell
$env:BIGFIVE_API_KEY = "TU_CLAVE"
$env:BIGFIVE_MODEL = "gemini-3.5-flash-lite"
$env:BIGFIVE_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
python main.py
```

El prompt completo se encuentra en `instagram_lab/big_five.py` como `SYSTEM_PROMPT` y en `PROMPT_BIGFIVE.md`. El análisis se guarda como `output/usuario_fecha_bigfive.json`. El modelo por defecto es `gemini-3.5-flash-lite` y la URL predeterminada apunta a Google Gemini; por tanto, basta con configurar `BIGFIVE_API_KEY` si ese modelo está disponible para tu clave. La cuota gratuita depende de Google. Si la API falla o falta la clave, el JSON original del scraping se conserva. **No incluyas claves API en GitHub.** Antes de transmitir publicaciones a un proveedor externo, asegúrate de contar con autorización y respetar las políticas aplicables.
