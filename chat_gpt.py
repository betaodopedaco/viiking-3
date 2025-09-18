import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS


app = Flask(__name__)
CORS(app)


# Config
HF_MODEL = os.environ.get('HF_MODEL', 'microsoft/DialoGPT-small')
HF_TOKEN = os.environ.get('HF_TOKEN') # obrigatória no Render (env var)
HF_API = f'https://api-inference.huggingface.co/models/{HF_MODEL}'


# Histórico simples por sessão (em memória)
session_histories = {}


@app.route('/')
def home():
return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
if HF_TOKEN is None:
return jsonify({'error': 'HF_TOKEN não configurado. Defina a variável de ambiente HF_TOKEN no Render.'}), 500


data = request.get_json(force=True)
user_message = data.get('message', '').strip()
session_id = data.get('session_id', 'default')


if not user_message:
return jsonify({'error': 'Mensagem vazia'}), 400


# Recupera histórico (string) e monta prompt simples
history = session_histories.get(session_id, '')
# Formato de prompt simples: mantém alternância User / Bot
prompt = (history + '
User: ' + user_message + '
Bot:').strip()


headers = {
'Authorization': f'Bearer {HF_TOKEN}',
'Content-Type': 'application/json'
}


payload = {
'inputs': prompt,
'parameters': {
'max_new_tokens': 150,
'temperature': 0.7,
'top_k': 50,
'top_p': 0.9,
'repetition_penalty': 1.1
}
}


try:
resp = requests.post(HF_API, headers=headers, json=payload, timeout=30)
if resp.status_code != 200:
# tenta extrair mensagem de erro da API
try:
err = resp.json()
except Exception:
err = resp.text
return jsonify({'error': f'HuggingFace API error: {resp.status_code} - {err}'}), 500


app.run(host='0.0.0.0', port=port, debug=True)
