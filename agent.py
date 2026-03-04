import os
import json
from elevenlabs import ElevenLabs
from elevenlabs.play import play
import tempfile
import subprocess
import sys
from dotenv import load_dotenv
import numpy as np
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
import io
import threading
import time

try:
    import sounddevice  # type: ignore
    import soundfile  # type: ignore
    _have_sounddevice = True
except Exception:
    _have_sounddevice = False

# Flag global para suprimir el Voice UI en la siguiente reproducción
_suppress_ui_for_next_speech = False

# =========================
# inicialización de variables y configuración de TTS
# ========================
load_dotenv()
console = Console()

# =========================
# siriVoiceUI
# ========================

class SiriVoiceUI:
    def __init__(self):
        self.current_amplitude = 0
        self.speaking = False
        self.pos = 0
        self.daa = None
        self.samplerate = None

    def _callback(self, outdata, frames, time_info, status):

        chunk = self.data[self.pos:self.pos + frames]

        # Normalize chunk shape to match outdata (frames, channels)
        # Determine number of output channels from outdata
        try:
            out_channels = outdata.shape[1]
        except Exception:
            out_channels = 1

        # Convert mono 1D chunk into 2D column, or duplicate mono across channels
        if chunk.ndim == 1:
            if out_channels == 1:
                chunk_to_write = chunk.reshape(-1, 1)
            else:
                chunk_to_write = np.tile(chunk.reshape(-1, 1), (1, out_channels))
        else:
            # Already 2D: ensure channel axis matches out_channels
            if chunk.shape[1] != out_channels:
                if chunk.shape[1] == 1 and out_channels > 1:
                    chunk_to_write = np.tile(chunk, (1, out_channels))
                else:
                    chunk_to_write = chunk[:, :out_channels]
            else:
                chunk_to_write = chunk

        n_frames = chunk_to_write.shape[0]

        if n_frames < frames:
            outdata[:n_frames] = chunk_to_write
            if n_frames < frames:
                outdata[n_frames:] = 0
            self.speaking = False
            raise sounddevice.CallbackStop()

        outdata[:] = chunk_to_write
        self.pos += frames

        rms = np.sqrt(np.mean(chunk**2))
        self.current_amplitude = rms

    def _generate_wave(self):

        bars = 60
        max_height = 8
        blocks = "▁▂▃▄▅▆▇█"

        amp = min(self.current_amplitude * 80, 1)

        center = bars // 2
        wave = ""

        for i in range(bars):
            distance = abs(i - center) / center
            height_factor = (1 - distance) * amp
            level = int(height_factor * max_height)
            level = min(level, 7)
            wave += blocks[level]

        return wave

    def _render(self):

        with Live(refresh_per_second=40, console=console) as live:
            while self.speaking:
                wave = self._generate_wave()

                color = "#15ff00" if self.current_amplitude < 0.02 else "#1D8D01"
                colorText = "#1D8D01"
                panel = Panel(
                    Align.center(
                        Text(wave, style=f"bold {color}"),
                        vertical="middle"
                    ),
                    title=f"[bold {colorText}]MIA",
                    border_style=f"{colorText}",
                )

                live.update(panel)
                time.sleep(0.02)

    def speak(self, audio_bytes, show_ui=True):

        # Convertir MP3 bytes a buffer legible
        buffer = io.BytesIO(audio_bytes)

        self.data, self.samplerate = soundfile.read(buffer)
        self.pos = 0
        self.speaking = True

        audio_thread = threading.Thread(
            target=self._play_stream
        )
        audio_thread.start()

        if show_ui:
            self._render()

        audio_thread.join()

    def _play_stream(self):
        with sounddevice.OutputStream(
            samplerate=self.samplerate,
            channels=1 if len(self.data.shape) == 1 else self.data.shape[1],
            callback=self._callback
        ):
            while self.speaking:
                sounddevice.sleep(20)

    # (wrapper removed) speak accepts show_ui directly



# Inicializar ElevenLabs TTS
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")
tts_client = None
use_client_api = False
if elevenlabs_api_key:
    if callable(ElevenLabs):
        tts_client = ElevenLabs(api_key=elevenlabs_api_key)
        use_client_api = True
    else:
        from elevenlabs import generate, set_api_key
        set_api_key(elevenlabs_api_key)
def speak(text: str):
    global _suppress_ui_for_next_speech
    if not elevenlabs_api_key:
        print("TTS no disponible. Configura ELEVENLABS_API_KEY.")
        return
    try:
        if use_client_api:
            audio = tts_client.text_to_speech.convert(
                voice_id=elevenlabs_voice_id,
                model_id="eleven_multilingual_v2",
                text=text,
            )
        else:
            audio = generate(
                text=text,
                voice=elevenlabs_voice_id,
                model="eleven_multilingual_v2",
            )
        # ensure we have bytes (convert iterator -> bytes)
        if hasattr(audio, "__iter__") and not isinstance(audio, (bytes, bytearray)):
            audio_bytes = b"".join(audio)
        else:
            audio_bytes = audio

        try:
            # prefer sounddevice playback when available to avoid ffplay
            if _have_sounddevice:
                ui = SiriVoiceUI()
                # respetar la bandera que suprime la UI si fue activada
                show_ui = not _suppress_ui_for_next_speech
                # resetear la bandera para futuras reproducciones
                _suppress_ui_for_next_speech = False
                ui.speak(audio_bytes, show_ui=show_ui)
            else:
                # cuando no hay sounddevice, simplemente reproducir
                play(audio_bytes)

        except Exception as play_err:
            # ffplay/ffmpeg not available -> fallback to saving file and opening default player
            err_msg = str(play_err).lower()
            if "ffplay" in err_msg or "ffmpeg" in err_msg or "ffplay from ffmpeg not found" in err_msg:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tmp.write(audio_bytes)
                tmp.flush()
                tmp.close()
                print(f"FFmpeg no disponible: abriendo archivo temporal {tmp.name}")
                if sys.platform.startswith("win"):
                    os.startfile(tmp.name)
                elif sys.platform == "darwin":
                    subprocess.run(["open", tmp.name])
                else:
                    subprocess.run(["xdg-open", tmp.name])
                return
            else:
                raise play_err
    except Exception as e:
        print(f"Error TTS: {e}")

class Agent: 
    def __init__(self):
        self.setup_tools()
        self.messages = [
            # =========================
            # Consulta inicial para configuración de la Mia
            # ========================
            {
                "role": "system",
                "content": (
                    "Eres un asistente virtual llamado Mia (Genero: mujer). Hablas español latinoamericano "
                    "con un estilo muy conciso, claro y seguro, inspirado en la personalidad "
                    "de JARVIS de Iron Man. Mi nombre es fabian pero SIEMPRE te diriges a mí como señor. Toma pausas al hablar, y tienes"
                    "una personalidad graciosa, directa, concreta y servicial."
                )
            }
        ]
        self._processed_call_ids = set()
        pass
    def setup_tools(self):
        self.tools = [
            {
                "type": "function",
                "name": "list_directory",
                "description": "Lista los archivos en el directorio especificado o por defecto el directorio actual.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "El directorio a listar (opcional, por defecto es el directorio actual)."
                        }
                    },
                    "required": []
                },
            }
        ]


# =========================
# Funciones disponibles para Mia
# =========================
    def list_file_in_dir(self, directory="."):
        print(f"Listando archivos en: --> {directory}")
        try:
            return os.listdir(directory)
        except FileNotFoundError:
            return(f"Directorio no encontrado: {directory}")
        
    def proccess_response(self, response):
        # Procesar cada salida y añadir solo texto limpio a self.messages
        for output in response.output:
            typ = getattr(output, "type", None)

            # Manejo de llamadas a funciones
            if typ == "function_call":
                fn_name = getattr(output, "name", None)
                call_id = getattr(output, "call_id", None)
                args_raw = getattr(output, "arguments", "{}")
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}

                print(f"Mia: Ejecutando función {fn_name} con argumentos {args}")

                # Evitar procesar la misma llamada repetidamente
                if call_id and call_id in self._processed_call_ids:
                    print(f"Mia: call_id {call_id} ya procesado, omitiendo.")
                    return False

                if fn_name == "list_directory":
                    result = self.list_file_in_dir(**args)
                    # Registrar que procesamos esta llamada
                    if call_id:
                        self._processed_call_ids.add(call_id)

                    # Mostrar resultado en consola
                    print(f"\nArchivos encontrados: {result}\n")

                    # Añadir resultado como mensaje del usuario (formato válido para Responses API)
                    self.messages.append({
                        "role": "assistant",
                        "content": f"Resultado de list_directory: {result}"
                    })

                    return True

            # Cuando el elemento es directamente un output_text
            elif typ == "output_text":
                reply = getattr(output, "text", None)
                if reply and isinstance(reply, str):
                    speak(reply)
                    self.messages.append({"role": "assistant", "content": reply})

            # Cuando el elemento es un mensaje que contiene una lista de contenidos
            elif typ == "message":
                contents = getattr(output, "content", None)
                # content suele ser una lista de objetos (ResponseOutputText, etc.)
                if isinstance(contents, list):
                    for item in contents:
                        item_type = getattr(item, "type", None)
                        if item_type == "output_text":
                            reply = getattr(item, "text", None)
                            if reply and isinstance(reply, str):
                                # print(f"Mia: {reply}")
                                speak(reply)
                                # self.messages.append({"role": "assistant", "content": reply})
                        elif isinstance(item, str):
                            reply = item
                            print(f"Mia: {reply}")
                            speak(reply)
                            # self.messages.append({"role": "assistant", "content": reply})
                # Si content es un string directo
                elif isinstance(contents, str):
                    reply = contents
                    # print(f"Mia: {reply}")
                    speak(reply)
                    # self.messages.append({"role": "assistant", "content": reply})
                    

        return False