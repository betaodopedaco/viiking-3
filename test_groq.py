import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

payload = {
    "model": "openai/gpt-oss-20b",
    "messages": [{"role": "user", "content": "Olá, tudo bem?"}],
    "max_tokens": 300
}

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload)

print(response.status_code)
print(response.json())
