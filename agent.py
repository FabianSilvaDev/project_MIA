import os
import sys
import tempfile
import subprocess
import io
import threading
import time
import requests
import numpy as np

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
    import soundfile  # type: ignore
    _have_sounddevice = True
except Exception:
    _have_sounddevice = False

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
        buffer = io.BytesIO(audio_bytes)
        self.data, self.samplerate = soundfile.read(buffer)
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
        print("TTS no disponible. Configura ELEVENLABS_API_KEY.")
        return

    try:
        audio = tts_client.text_to_speech.convert(
            voice_id=elevenlabs_voice_id,
            model_id="eleven_multilingual_v2",
            text=text,
        )

        if hasattr(audio, "__iter__") and not isinstance(audio, (bytes, bytearray)):
            audio_bytes = b"".join(audio)
        else:
            audio_bytes = audio

        if _have_sounddevice:
            ui = SiriVoiceUI()
            ui.speak(audio_bytes)
        else:
            play(audio_bytes)

    except Exception as e:
        print(f"Error TTS: {e}")

# =========================
# Ollama Local LLM
# =========================
def ask_ollama(messages):
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "mistral",  # puedes cambiar a "llama3"
            "messages": messages,
            "stream": False
        }
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
        self.messages = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente virtual llamado Mia (Genero: mujer). "
                    "Hablas español latinoamericano con un estilo muy conciso, claro y seguro, "
                    "inspirado en la personalidad de JARVIS de Iron Man. "
                    "Mi nombre es fabian pero SIEMPRE te diriges a mí como señor. "
                    "Tomas pausas al hablar y tienes una personalidad graciosa, directa y servicial."
                )
            }
        ]

    def run(self, user_input):

        self.messages.append({
            "role": "user",
            "content": user_input
        })

        try:
            reply = ask_ollama(self.messages)

            self.messages.append({
                "role": "assistant",
                "content": reply
            })

            print(f"\nMia: {reply}\n")
            speak(reply)

        except Exception as e:
            print(f"\nError consultando el modelo: {e}\n")