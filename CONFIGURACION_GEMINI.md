# Uso de Gemini gratuito en InstagramLab

El proyecto mantiene intacto el scraper de Instagram. Tras extraer los datos, puede enviar hasta 25 descripciones de publicaciones a Gemini para representar **señales textuales relacionadas con Big Five**. Esto no constituye una evaluación psicológica de la persona.

## Configuración (Windows PowerShell)

```powershell
$env:BIGFIVE_API_KEY = "TU_CLAVE_DE_GOOGLE_AI_STUDIO"
python main.py
```

El proyecto ya tiene estos valores por defecto:

- `BIGFIVE_MODEL`: `gemini-3.5-flash-lite`
- `BIGFIVE_API_URL`: `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`

Si necesitas cambiarlos, puedes definir también esas dos variables de entorno.

## Errores comunes

- **401 / 403**: clave incorrecta, restricciones o falta de permisos.
- **404**: el modelo indicado no está disponible para tu clave o tu proyecto. Comprueba los modelos de Google AI Studio.
- **429**: has alcanzado la cuota; espera a que se restablezca.
- **Respuesta no válida**: el proveedor devolvió un texto distinto del JSON esperado. Repite con menos publicaciones o revisa el resultado.

Nunca compartas ni subas tu clave API o `cookies.json` a GitHub. No uses textos de terceros sin contar con una base adecuada para enviarlos al proveedor de IA.

Documentación: https://ai.google.dev/gemini-api/docs/openai y https://ai.google.dev/gemini-api/docs/pricing
