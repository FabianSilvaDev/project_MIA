from dotenv import load_dotenv
from agent import Agent, speak

load_dotenv()

# =========================
# Inicializar agente
# =========================
agent = Agent()

print("\n🔹 Mia está en línea, señor.\n")

# =========================
# Loop principal
# =========================
while True:

    user_input = input("Señor: ")

    if not user_input:
        continue

    if user_input.lower() in ["salir", "exit", "adiós", "hasta pronto", "chao mia"]:
        print("\nMia: Hasta pronto, señor.\n")
        speak("Hasta pronto, señor.")
        break

    # 🔥 SOLO llamamos a run()
    agent.run(user_input)