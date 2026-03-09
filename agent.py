import os
import sys
import tempfile
import subprocess
import io
import threading
import time
import base64
import requests
import numpy as np
import asyncio
import websockets
import json
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.play import play
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.text import Text


# =========================
# Cargar entorno
# =========================
load_dotenv()
console = Console()

# =========================
# Audio opcional avanzado
# =========================
try:
    import sounddevice  # type: ignore
    _have_sounddevice = True
except Exception:
    _have_sounddevice = False   

# =========================
# WebSocket Server
# =========================

clients = set()
WS_CLIENTS_COUNT = 0
WS_LOOP = None
WS_SERVER_STARTED = False
WS_SERVER_LOCK = threading.Lock()
WS_STATUS_EVENT = threading.Event()
WS_SERVER_HOST = "127.0.0.1"
WS_SERVER_PORT = 3312
CURRENT_EMOTION = "happy"  # Track current emotion for the avatar
WS_DEBUG_LOGS = False
LIPSYNC_OFFSET_MS = int(os.getenv("BMO_LIPSYNC_OFFSET_MS", "0"))

async def register(websocket):
    global WS_CLIENTS_COUNT
    clients.add(websocket)
    WS_CLIENTS_COUNT = len(clients)
    if WS_DEBUG_LOGS:
        print(f"[BMO] Cliente WebSocket conectado (clientes: {WS_CLIENTS_COUNT})")

async def unregister(websocket):
    global WS_CLIENTS_COUNT
    clients.discard(websocket)
    WS_CLIENTS_COUNT = len(clients)
    if WS_DEBUG_LOGS:
        print(f"[BMO] Cliente WebSocket desconectado (clientes: {WS_CLIENTS_COUNT})")

async def broadcast(data):
    if clients:
        await asyncio.gather(
            *[client.send(json.dumps(data)) for client in clients],
            return_exceptions=True
        )

async def handler(websocket):
    await register(websocket)
    try:
        async for message in websocket:
            pass
    finally:
        await unregister(websocket)


def start_websocket_server():
    global WS_LOOP, WS_SERVER_STARTED

    def _is_port_in_use_error(error: OSError) -> bool:
        return (
            getattr(error, "winerror", None) == 10048
            or getattr(error, "errno", None) == 10048
            or "10048" in str(error)
            or "address already in use" in str(error).lower()
        )

    async def _run_server():
        async with websockets.serve(handler, WS_SERVER_HOST, WS_SERVER_PORT):
            WS_STATUS_EVENT.set()
            await asyncio.Future()

    with WS_SERVER_LOCK:
        if WS_SERVER_STARTED:
            WS_STATUS_EVENT.set()
            return
        WS_SERVER_STARTED = True

    loop = asyncio.new_event_loop()
    WS_LOOP = loop
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_server())
    except OSError as e:
        if _is_port_in_use_error(e):
            with WS_SERVER_LOCK:
                WS_SERVER_STARTED = False
            WS_LOOP = None
            WS_STATUS_EVENT.set()
            return
        with WS_SERVER_LOCK:
            WS_SERVER_STARTED = False
        WS_LOOP = None
        WS_STATUS_EVENT.set()
        return
    except Exception:
        with WS_SERVER_LOCK:
            WS_SERVER_STARTED = False
        WS_LOOP = None
        WS_STATUS_EVENT.set()
        return


def send_ws_state(data):
    if WS_LOOP is None:
        return

    try:
        asyncio.run_coroutine_threadsafe(broadcast(data), WS_LOOP)
    except Exception:
        pass


def wait_for_ws_client(timeout_seconds: float = 2.0, poll_interval: float = 0.05) -> bool:
    deadline = time.time() + max(0.0, timeout_seconds)
    while time.time() < deadline:
        if WS_CLIENTS_COUNT > 0:
            return True
        time.sleep(max(0.01, poll_interval))
    return WS_CLIENTS_COUNT > 0


def get_websocket_status() -> dict:
    return {
        "ready": WS_LOOP is not None,
        "started": WS_SERVER_STARTED,
        "host": WS_SERVER_HOST,
        "port": WS_SERVER_PORT,
        "clients": WS_CLIENTS_COUNT,
    }


def detect_emotion_from_text(text: str) -> str:
    """Detecta emoción basada en palabras clave en el texto."""
    text_lower = text.lower()
    
    # Palabras clave para cada emoción
    happy_keywords = ["jaja", "ja ja", "jeje", "bueno", "excelente", "genial", "fantástico", "gracias", ":)", "😊"]
    curious_keywords = ["interesante", "quiero saber", "cuéntame", "cómo", "qué", "interesa", "pregunto", "explora"]
    surprised_keywords = ["wow", "vaya", "sorprendente", "increíble", "nunca", "!"]
    thinking_keywords = ["creo", "parece", "cuestión", "depende", "tal vez", "quizás", "consider"]
    sad_keywords = ["lamento", "lo siento", "triste", "malo", "difícil", "problema", "error", "fallo"]
    
    # Contar coincidencias
    happy_count = sum(1 for kw in happy_keywords if kw in text_lower)
    curious_count = sum(1 for kw in curious_keywords if kw in text_lower)
    surprised_count = sum(1 for kw in surprised_keywords if kw in text_lower)
    thinking_count = sum(1 for kw in thinking_keywords if kw in text_lower)
    sad_count = sum(1 for kw in sad_keywords if kw in text_lower)
    
    # Retornar emoción con más coincidencias
    scores = {
        "happy": happy_count,
        "curious": curious_count,
        "surprised": surprised_count,
        "thinking": thinking_count,
        "sad": sad_count
    }
    
    max_emotion = max(scores, key=scores.get)
    if scores[max_emotion] > 0:
        return max_emotion
    return "neutral"


def _pcm16_bytes_to_float32(audio_bytes: bytes, channels: int = 1):
    pcm = np.frombuffer(audio_bytes, dtype=np.int16)
    if pcm.size == 0:
        return np.empty((0, channels), dtype=np.float32)

    if channels > 1:
        usable = (pcm.size // channels) * channels
        pcm = pcm[:usable].reshape(-1, channels)
    else:
        pcm = pcm.reshape(-1, 1)

    return (pcm.astype(np.float32) / 32768.0)


def stream_audio_to_ws(audio_bytes: bytes, sample_rate: int = 24000, channels: int = 1, start_delay_ms: int = 0):
    if WS_LOOP is None:
        return

    try:
        data = _pcm16_bytes_to_float32(audio_bytes, channels=channels)
        if data.size == 0:
            send_ws_state({"type": "audio_end"})
            return

        chunk_size = 1024
        started_at = time.perf_counter()

        if start_delay_ms > 0:
            time.sleep(start_delay_ms / 1000.0)

        # Asegurar que el frontend sepa que está hablando
        send_ws_state({
            "type": "audio_start",
            "sample_rate": int(sample_rate),
            "channels": int(channels),
        })

        for start in range(0, len(data), chunk_size):
            chunk = data[start:start + chunk_size]
            payload = base64.b64encode(chunk.astype(np.float32).tobytes()).decode("ascii")

            send_ws_state({
                "type": "audio_chunk",
                "format": "pcm_f32le",
                "sample_rate": int(sample_rate),
                "channels": int(channels),
                "data": payload,
            })

            played_seconds = (start + len(chunk)) / sample_rate
            elapsed_seconds = time.perf_counter() - started_at
            sleep_time = played_seconds - elapsed_seconds
            if sleep_time > 0:
                # Mantener tiempo real del stream para que la boca siga el audio.
                time.sleep(sleep_time)

        send_ws_state({"type": "audio_end"})
    except Exception:
        pass


def play_audio_locally(audio_bytes: bytes, sample_rate: int = 24000, channels: int = 1):
    if not _have_sounddevice:
        print("[BMO] Audio local desactivado: falta sounddevice.")
        return

    try:
        data = _pcm16_bytes_to_float32(audio_bytes, channels=channels)
        if data.size == 0:
            return
        sounddevice.play(data, samplerate=sample_rate)
        sounddevice.wait()
    except Exception as e:
        print(f"[BMO] Error reproduciendo audio local: {e}")

# =========================
# Siri Voice UI
# =========================
class SiriVoiceUI:
    def __init__(self):
        self.current_amplitude = 0
        self.speaking = False
        self.pos = 0
        self.samplerate = None

    def _callback(self, outdata, frames, time_info, status):
        chunk = self.data[self.pos:self.pos + frames]

        if chunk.ndim == 1:
            chunk = chunk.reshape(-1, 1)

        n_frames = chunk.shape[0]

        if n_frames < frames:
            outdata[:n_frames] = chunk
            outdata[n_frames:] = 0
            self.speaking = False
            raise sounddevice.CallbackStop()

        outdata[:] = chunk
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
                panel = Panel(
                    Align.center(
                        Text(wave, style="bold #1D8D01"),
                        vertical="middle"
                    ),
                    title="[bold #1D8D01]MIA",
                    border_style="#1D8D01",
                )
                live.update(panel)
                time.sleep(0.02)

    def speak(self, audio_bytes):
        self.data = _pcm16_bytes_to_float32(audio_bytes, channels=1)
        self.samplerate = 24000
        self.pos = 0
        self.speaking = True

        audio_thread = threading.Thread(target=self._play_stream)
        audio_thread.start()

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

# =========================
# ElevenLabs TTS
# =========================
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")

tts_client = ElevenLabs(api_key=elevenlabs_api_key) if elevenlabs_api_key else None

def speak(text: str):

    if not elevenlabs_api_key:
        print("[BMO] Audio desactivado: falta ELEVENLABS_API_KEY en .env")
        return

    try:
        global CURRENT_EMOTION

        # 🔥 Detectar emoción de la respuesta
        emotion = detect_emotion_from_text(text)
        CURRENT_EMOTION = emotion
        
        # 🔥 Enviar emoción al frontend
        send_ws_state({"emotion": emotion})
        
        audio = tts_client.text_to_speech.convert(
            voice_id=elevenlabs_voice_id,
            model_id="eleven_multilingual_v2",
            text=text,
            output_format="pcm_24000",
        )

        if hasattr(audio, "__iter__") and not isinstance(audio, (bytes, bytearray)):
            audio_bytes = b"".join(audio)
        else:
            audio_bytes = audio

        # Mantener estado de speaking para animacion en frontend.
        send_ws_state({"state": "speaking"})

        # Enviar chunks al navegador para lip-sync (aunque el audio audible sea local).
        ws_audio_thread = None
        if WS_CLIENTS_COUNT > 0:
            ws_audio_thread = threading.Thread(
                target=stream_audio_to_ws,
                args=(audio_bytes, 24000, 1, LIPSYNC_OFFSET_MS),
                daemon=False,
            )
            ws_audio_thread.start()

        # Modo audible solo terminal.
        if _have_sounddevice:
            play_audio_locally(audio_bytes, sample_rate=24000, channels=1)
        else:
            print("[BMO] Audio local no disponible: instala/activa sounddevice en el entorno.")

        if ws_audio_thread is not None:
            ws_audio_thread.join()

        # Señalizar fin del habla
        send_ws_state({"state": "idle"})

    except Exception as e:
        print(f"[BMO] Error de audio/TTS: {e}")

# =========================
# Ollama Local LLM
# =========================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

def _get_ollama_models():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=(4, 10))
        if response.status_code != 200:
            return []

        data = response.json()
        models = []
        for item in data.get("models", []):
            name = item.get("name")
            if name:
                models.append(name)
        return models
    except Exception:
        return []

def _select_ollama_model():
    installed = _get_ollama_models()
    if not installed:
        return OLLAMA_MODEL

    if OLLAMA_MODEL in installed:
        return OLLAMA_MODEL

    preferred_fallbacks = ["mistral", "llama3.2:3b", "llama3", "phi3:mini"]
    for candidate in preferred_fallbacks:
        if candidate in installed:
            return candidate

    return installed[0]

def ask_ollama(messages):
    model_name = _select_ollama_model()

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model_name,
            "messages": messages,
            "stream": False
        },
        timeout=(5, 180)
    )

    if response.status_code != 200:
        raise Exception(response.text)

    data = response.json()
    return data["message"]["content"]

# =========================
# Agent
# =========================
class Agent:
    def __init__(self):
         # iniciar websocket en hilo separado
        WS_STATUS_EVENT.clear()
        ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
        ws_thread.start()
        WS_STATUS_EVENT.wait(timeout=2.0)

        self.messages = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente virtual llamado BIMO "
                    "inspirado en la personalidad de BIMO de la serie Hora de Aventura. "
                    "Mi nombre es fabian pero SIEMPRE te diriges a mí como señor. "
                    "Tienes una personalidad graciosa, directa y servicial."
                )
            }
        ]

    def run(self, user_input):

        self.messages.append({
            "role": "user",
            "content": user_input
        })

        # Mantener contexto corto para evitar latencia alta y timeouts.
        max_history = 16  # sin contar el mensaje system
        if len(self.messages) > (1 + max_history):
            self.messages = [self.messages[0]] + self.messages[-max_history:]

        try:
            reply = ask_ollama(self.messages)

            self.messages.append({
                "role": "assistant",
                "content": reply
            })

            print(f"\nBMO: {reply}\n")
            speak(reply)

        except requests.exceptions.ConnectTimeout:
            print("\n[BMO] Error: Ollama no respondió a tiempo (timeout).\n")
        except requests.exceptions.ReadTimeout:
            fallback = "Señor, Ollama está tardando demasiado en responder. Verifique que el modelo esté cargado o use uno más ligero."
            print("\n[BMO] Error: tiempo de espera agotado leyendo respuesta de Ollama.\n")
            print(f"\nBMO: {fallback}\n")
            speak(fallback)
        except requests.exceptions.ConnectionError:
            print(f"\n[BMO] Error: No se pudo conectar a Ollama en {OLLAMA_BASE_URL}. Inicia Ollama y el modelo.\n")
        except Exception as e:
            print(f"\n[BMO] Error inesperado: {e}\n")