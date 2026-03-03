from openai import OpenAI
from dotenv import load_dotenv
from agent import Agent, speak

load_dotenv()

# =========================
# Inicializar OpenAI y el agente
# =========================
client = OpenAI()
agent = Agent()

# =========================
# Loop principal
# =========================
while True: 
    user_input = input("You: ")

    if not user_input:
        continue

    if user_input.lower() in ["salir", "exit", "adiós", "hasta pronto"]:
        print("Mia: Hasta pronto, señor.")
        speak("Hasta pronto, señor.")
        break
 
    agent.messages.append({"role": "user", "content": user_input})

    while True:

        response = client.responses.create(
            model="gpt-5-nano",
            input=agent.messages,
            tools=agent.tools,
        )

        called_tool = agent.proccess_response(response)

        if not called_tool:
            break
