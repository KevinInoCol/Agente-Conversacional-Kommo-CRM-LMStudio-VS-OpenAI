# Para generar el entorno virtual
conda create --name LangChain-LlamaIndex-Kommo python=3.11

# Para activar el entorno virtual
conda activate LangChain-LlamaIndex-Kommo

# Con este levantamos el endpoint
uvicorn app:app --reload --host 0.0.0.0 --port 8000


# Comando para el forwarding:
ngrok http 8000


Luego copia la API key ubicada en la pestaña "Your Authtoken"
ngrok config add-authtoken TU_TOKEN_AQUI









(LlamaIndex-proj-Kommo) kevininofuente@MacBook-Pro-de-Kevin Projecto_kommo % pip show llama-cloud-services
Name: llama-cloud-services
Version: 0.6.54
Summary: Tailored SDK clients for LlamaCloud services.
Home-page: 
Author: 
Author-email: Logan Markewich <logan@runllama.ai>
License-Expression: MIT
Location: /opt/anaconda3/envs/LlamaIndex-proj-Kommo/lib/python3.11/site-packages
Requires: click, llama-cloud, llama-index-core, platformdirs, pydantic, python-dotenv, tenacity
Required-by: llama-parse



[INTERESADO] → mueve a "Lead Interesado":
  - Intención CLARA de compra: "lo quiero", "me interesa comprarlo", pide precio para adquirir.
  - NO se activa por preguntas informativas ("¿qué es VitaCalm?", "¿para qué sirve?").


Mensajes que pueden permitir al cliente entrar a "Cerrar Venta"
  - "Voy a transferir ahora"
  - "Hago el pago ahora"
  - "En 5 min envío el comprobante"
  - "Te mando el voucher en un momento"
  - "Procedo al pago"