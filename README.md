# Dictado

Dictado por voz para **cualquier cuadro de texto de Windows** (Word, el navegador, WhatsApp, Outlook, el Bloc de notas…)
usando solo la tecla **Ctrl**. Se instala **sin permisos de administrador**.

El reconocimiento usa **Whisper large-v3-turbo**, uno de los mejores modelos de voz que existen, y se ejecuta
**en tu propio PC**: es gratis, privado y funciona sin internet (solo necesita internet la primera vez para
descargar el modelo, unos 1,6 GB). También puede usar opcionalmente un servicio en la nube (OpenAI o Groq).

## Cómo se usa

1. Haz clic en cualquier cuadro de texto, como harías para escribir.
2. **Mantén pulsada la tecla Ctrl** (sola). A los 0,3 segundos suena un pitido agudo: ya te está escuchando.
3. Habla con normalidad, con frases completas. La puntuación y las mayúsculas se ponen solas.
4. **Suelta Ctrl**. Suena un pitido más grave y en un momento aparece el texto donde estaba el cursor.

Los atajos de siempre siguen funcionando: si con Ctrl pulsas otra tecla o usas el ratón (Ctrl+C, Ctrl+V,
Ctrl+clic, Ctrl+rueda…), Dictado no hace nada. AltGr (para escribir @, #, €…) tampoco lo activa.

El icono del micrófono que aparece junto al reloj indica el estado:

| Color | Significado |
|---|---|
| 🔵 Azul | Listo para dictar |
| 🔴 Rojo | Escuchando |
| 🟠 Naranja | Transcribiendo |
| ⚪ Gris | Cargando el modelo (o en pausa) |

Con clic derecho en el icono puedes **pausar** el dictado, activar **Iniciar con Windows**, abrir la
**configuración** o **salir**.

> Si el icono no se ve, puede estar escondido en la flecha `^` junto al reloj. Puedes arrastrarlo a la barra.

## Instalación (sin administrador)

1. Descarga **`Dictado-Setup.exe`**:
   - de la página **Releases** del repositorio, o
   - de la pestaña **Actions** → la última ejecución correcta de *Compilar Dictado para Windows* →
     apartado *Artifacts* → `Dictado-Setup` (viene dentro de un .zip).
2. Ábrelo. Como el programa no está firmado digitalmente, Windows puede mostrar
   *"Windows protegió su PC"*: pulsa **Más información → Ejecutar de todas formas**.
3. El instalador **no pide administrador**: se instala en `%LOCALAPPDATA%\Programs\Dictado`, solo para tu usuario.
   Marca *"Iniciar Dictado automáticamente al entrar en Windows"* si quieres tenerlo siempre disponible.
4. La primera vez descargará el modelo de voz (verás un aviso). Cuando el icono se ponga azul, ya puedes dictar.

¿Prefieres no instalar nada? Descarga `Dictado-portable`, descomprímelo donde quieras (por ejemplo en
Documentos) y ejecuta `Dictado.exe`.

**Desinstalar:** Configuración de Windows → Aplicaciones → Dictado → Desinstalar. Los modelos descargados
quedan en `%LOCALAPPDATA%\Dictado\modelos` (puedes borrar la carpeta para liberar espacio).

## Configuración

Clic derecho en el icono → **Abrir configuración**. Se abre `%APPDATA%\Dictado\config.json` en el Bloc de notas;
cada opción está explicada dentro del propio archivo (sección `_ayuda`). Tras guardar, **Salir** y volver a
abrir Dictado.

Opciones más útiles:

| Opción | Por defecto | Para qué sirve |
|---|---|---|
| `modo` | `"mantener"` | `"alternar"`: toca Ctrl una vez para empezar y otra para terminar (manos libres; Esc cancela). |
| `tiempo_pulsacion` | `0.3` | Segundos que hay que mantener Ctrl para empezar a grabar. |
| `idioma` | `"es"` | `"en"`, `"ca"`, `"eu"`, `"gl"`, `"fr"`… o `""` para detectarlo automáticamente. |
| `motor` | `"local"` | `"groq"` u `"openai"` para reconocimiento en la nube casi instantáneo (ver abajo). |
| `modelo_local` | `"large-v3-turbo"` | `"large-v3"` (aún más preciso, más lento) o `"small"` (rápido para PCs modestos). |
| `texto_contexto` | `""` | Nombres propios o palabras técnicas que uses a menudo, separados por comas, para que las escriba bien. |
| `metodo_insercion` | `"pegar"` | `"escribir"` si alguna aplicación no acepta Ctrl+V. |
| `microfono` | `null` | Parte del nombre del micrófono a usar, p. ej. `"USB"`. |
| `sonidos` | `true` | Pitidos al empezar y terminar. |

### Velocidad

Dictado va transcribiendo **mientras hablas**: cada vez que haces una pausa procesa lo ya dicho, así que al soltar
Ctrl solo queda el último trozo. Aun así, en un PC sin tarjeta gráfica el motor local tarda alrededor de 1–3 segundos
en ese último trozo. Si tienes una tarjeta **NVIDIA** con CUDA 12 y cuDNN 9 instalados, Dictado la usa
automáticamente y es casi instantáneo.

### Casi instantáneo: motor Groq (recomendado si quieres velocidad)

[Groq](https://console.groq.com) ejecuta el mismo modelo Whisper en la nube en unas décimas de segundo, y tiene un
plan gratuito con un límite diario holgado para dictar.

1. Crea una cuenta en https://console.groq.com y en **API Keys** pulsa **Create API Key**. Copia la clave (`gsk_...`).
2. Clic derecho en el icono de Dictado → **Abrir configuración** y cambia estas dos líneas:
   ```json
   "motor": "groq",
   "api_clave": "gsk_tu_clave_aqui",
   ```
3. Guarda, y en el icono → **Salir**. Vuelve a abrir Dictado.

También puedes usar `"motor": "openai"` con una clave de OpenAI (modelo `gpt-4o-transcribe`). Con estos motores el
audio de cada dictado se envía a ese servicio por internet.

## Limitaciones

- No funciona dentro de ventanas abiertas **como administrador** (p. ej. el Administrador de tareas o una
  consola de administrador): Windows impide que un programa normal escriba en ellas.
- Al pegar se usa el portapapeles un instante y luego se restaura su texto anterior. Si en el portapapeles había
  una imagen o archivos, se pierden.
- Algunos juegos a pantalla completa o escritorios remotos pueden no recibir el texto.

## Para desarrolladores

Ejecutar desde el código (Python 3.10+ instalado "solo para mi usuario", que tampoco necesita administrador):

```bash
pip install -r requirements.txt
```

```bash
pythonw dictado_main.py
```

Compilar el `.exe` y el instalador en Windows (el instalador requiere Inno Setup 6):

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

Pruebas:

```bash
python -m unittest discover -s tests -t .
```

Estructura:

| Archivo | Función |
|---|---|
| `dictado/gesture.py` | Decide cuándo Ctrl significa "dictar" (y cuándo es un atajo normal). |
| `dictado/keyhook.py` | Ganchos globales de teclado y ratón (sin administrador, solo observan). |
| `dictado/audio.py` | Grabación del micrófono a 16 kHz. |
| `dictado/transcriber.py` | Whisper local (faster-whisper) o API compatible con OpenAI. |
| `dictado/output.py` | Escribe el texto en la ventana activa (portapapeles + Ctrl+V, o tecleo simulado). |
| `dictado/app.py` | Icono de bandeja y coordinación de todo lo anterior. |

El workflow `.github/workflows/build.yml` compila en Windows, ejecuta las pruebas y una autoprueba del `.exe`
(carga un modelo Whisper real), y publica `Dictado-Setup.exe` y `Dictado-portable.zip` como artefactos. Al
subir una etiqueta `v*` (p. ej. `v0.1.0`) crea además una *Release* con ambos archivos.
