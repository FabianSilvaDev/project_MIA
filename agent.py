import os
import json
from elevenlabs import ElevenLabs
from elevenlabs.play import play
import tempfile
import subprocess
import sys
from dotenv import load_dotenv

try:
    import sounddevice  # type: ignore
    import soundfile  # type: ignore
    _have_sounddevice = True
except Exception:
    _have_sounddevice = False

# Cargar variables de entorno
load_dotenv()

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
            play(audio_bytes, use_ffmpeg=not _have_sounddevice)
            return
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
            # Mensajes iniciales
            # ========================
            {
                "role": "system",
                "content": (
                    "Eres un asistente virtual llamado Mia (Genero: mujer). Hablas español latinoamericano "
                    "con un estilo muy conciso, claro y seguro, inspirado en la personalidad "
                    "de JARVIS de Iron Man. Siempre te diriges a mí como señor, Toma pausas al hablar, y tienes"
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
# Funciones disponibles para el modelo
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

                    # Añadir resultado como mensaje de assistant (texto JSON)
                    self.messages.append({
                        "role": "assistant",
                        "content": json.dumps({"files": result})
                    })

                    return True

            # Cuando el elemento es directamente un output_text
            elif typ == "output_text":
                reply = getattr(output, "text", None)
                if reply and isinstance(reply, str):
                    print(f"Mia: {reply}")
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
                                print(f"Mia: {reply}")
                                speak(reply)
                                self.messages.append({"role": "assistant", "content": reply})
                        elif isinstance(item, str):
                            reply = item
                            print(f"Mia: {reply}")
                            speak(reply)
                            self.messages.append({"role": "assistant", "content": reply})
                # Si content es un string directo
                elif isinstance(contents, str):
                    reply = contents
                    print(f"Mia: {reply}")
                    speak(reply)
                    self.messages.append({"role": "assistant", "content": reply})

        return False