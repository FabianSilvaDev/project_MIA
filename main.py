from dotenv import load_dotenv
from agent import Agent, speak, get_websocket_status

load_dotenv()

# =========================
# Inicializar agente
# =========================
agent = Agent()

ws_status = get_websocket_status()
if ws_status["ready"]:
    print(
        f"[BMO] WebSocket listo en ws://{ws_status['host']}:{ws_status['port']} "
        f"(clientes: {ws_status['clients']})"
    )
else:
    print(
        f"[BMO] WebSocket NO listo en ws://{ws_status['host']}:{ws_status['port']}. "
        "Revise si el puerto esta ocupado."
    )

# =========================
# Loop principal
# =========================
while True:

    user_input = input("You: ")

    if not user_input:
        continue

    normalized_input = user_input.strip().lower()

    if normalized_input in ["salir", "exit", "adiós", "hasta pronto", "chao mia"]:
        speak("Hasta pronto, señor.")
        break

    if normalized_input in ["ws", "estado ws", "websocket"]:
        ws_status = get_websocket_status()
        print(
            f"[BMO] WS ready={ws_status['ready']} started={ws_status['started']} "
            f"url=ws://{ws_status['host']}:{ws_status['port']} clients={ws_status['clients']}"
        )
        continue

    # Ruta rápida para probar audio sin esperar respuesta del modelo.
    if normalized_input in ["hola bmo", "hola, bmo", "hola bimo", "hola, bimo"]:
        quick_reply = (
            "¡Hola señor! Me alegra verlo aquí. ¿En qué puedo ayudarlo hoy? "
            "¡Estoy a su disposición, señor!"
        )
        print(f"\nBMO: {quick_reply}\n")
        speak(quick_reply)
        continue

    # 🔥 SOLO llamamos a run()
    agent.run(user_input)