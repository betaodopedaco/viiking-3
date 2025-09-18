import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Config
HF_MODEL = os.environ.get('HF_MODEL', 'microsoft/DialoGPT-small')
HF_TOKEN = os.environ.get('HF_TOKEN')  # obrigatória no Render (env var)
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

    # Aqui estava o erro: precisa usar '\n' dentro da mesma string literal,
    # não quebrar a linha no código. Linha corrigida abaixo.
    prompt = (history + '\nUser: ' + user_message + '\nBot:').strip()

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
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            return jsonify({'error': f'HuggingFace API error: {resp.status_code} - {err}'}), 500

        result = resp.json()

        bot_text = ''
        if isinstance(result, dict) and 'error' in result:
            return jsonify({'error': result.get('error')}), 500
        elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            bot_text = result[0].get('generated_text') or result[0].get('text') or ''
        elif isinstance(result, dict) and 'generated_text' in result:
            bot_text = result.get('generated_text')
        else:
            bot_text = str(result)

        bot_text = bot_text.strip()

        new_history = (history + f'\nUser: {user_message}\nBot: {bot_text}') if history else f'User: {user_message}\nBot: {bot_text}'
        session_histories[session_id] = new_history[-2000:]

        return jsonify({'response': bot_text})

    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Erro de conexão com HuggingFace: ' + str(e)}), 500
    except Exception as e:
        return jsonify({'error': 'Erro interno: ' + str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
