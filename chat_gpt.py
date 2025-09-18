# MAGNATUNS — Repositório pronto para deploy (corrigido)

Este documento contém **todos os arquivos** já corrigidos e organizados para você **copiar/colar** na pasta `magnatuns-prog` e subir no GitHub. Esta versão evita instalar `torch`/`transformers` localmente (que causavam erro de build) e usa a **Hugging Face Inference API** — assim o deploy no Render funciona rápido e sem compilar pacotes nativos.

---

## Estrutura final do repositório

```
magnatuns-prog/
├── chat_gpt.py
├── requirements.txt
├── runtime.txt
├── Procfile
└── templates/
    └── index.html
```

---

## 1) `chat_gpt.py` (back-end usando HuggingFace Inference API)

```python
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

        result = resp.json()

        # A resposta pode vir em formatos diferentes; tratamos os mais comuns
        bot_text = ''
        if isinstance(result, dict) and 'error' in result:
            return jsonify({'error': result.get('error')}), 500
        elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            # normalmente: [{'generated_text': '...'}]
            bot_text = result[0].get('generated_text') or result[0].get('text') or ''
        elif isinstance(result, dict) and 'generated_text' in result:
            bot_text = result.get('generated_text')
        else:
            # fallback: converte pra string se possível
            bot_text = str(result)

        bot_text = bot_text.strip()

        # Atualiza histórico (curta) — guarda apenas última interação com limites para não crescer demais
        new_history = (history + f'
User: {user_message}
Bot: {bot_text}') if history else f'User: {user_message}
Bot: {bot_text}'
        # limita a ~2000 chars
        session_histories[session_id] = new_history[-2000:]

        return jsonify({'response': bot_text})

    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Erro de conexão com HuggingFace: ' + str(e)}), 500
    except Exception as e:
        return jsonify({'error': 'Erro interno: ' + str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
```

**Observações:**

* Você precisa criar a variável de ambiente `HF_TOKEN` no painel do Render com a sua chave da Hugging Face.
* `HF_MODEL` é opcional; por padrão usei `microsoft/DialoGPT-small`. Se preferir outro modelo, defina `HF_MODEL` como env var.

---

## 2) `requirements.txt`

```
flask==3.0.3
flask-cors==3.0.10
requests==2.31.0
gunicorn==22.0.0
```

> Note: removemos `torch` e `transformers` para evitar compilação de pacotes nativos no build do Render.

---

## 3) `runtime.txt`

```
python-3.10.12
```

(Mantenha esse arquivo na raiz do repositório para forçar Python 3.10 no Render.)

---

## 4) `Procfile`

```
web: gunicorn chat_gpt:app
```

---

## 5) `templates/index.html` (seu front-end)

Cole aqui exatamente o HTML que você já me enviou — coloque no arquivo `templates/index.html`:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat com DialoGPT</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .chat-container {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
            height: 500px;
            display: flex;
            flex-direction: column;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .message {
            margin-bottom: 10px;
            padding: 8px 12px;
            border-radius: 15px;
            max-width: 80%;
            word-wrap: break-word;
        }
        .user-message {
            background-color: #007bff;
            color: white;
            margin-left: auto;
        }
        .bot-message {
            background-color: #e9ecef;
            color: #333;
        }
        .chat-input {
            display: flex;
            gap: 10px;
        }
        #user-input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 20px;
            outline: none;
        }
        button {
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
        }
        button:hover {
            background-color: #0056b3;
        }
        .loading {
            display: none;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <h2>🤖 Chat com DialoGPT</h2>
        
        <div class="chat-messages" id="chat-messages">
            <div class="message bot-message">
                Olá! Sou um assistente baseado em DialoGPT. Como posso ajudar você?
            </div>
        </div>
        
        <div class="chat-input">
            <input type="text" id="user-input" placeholder="Digite sua mensagem...">
            <button onclick="sendMessage()">Enviar</button>
        </div>
        
        <div id="loading" class="loading">Gerando resposta...</div>
    </div>

    <script>
        // Gerar um ID único para esta sessão
        const sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
        
        function addMessage(text, isUser = false) {
            const chatMessages = document.getElementById('chat-messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = isUser ? 'message user-message' : 'message bot-message';
            messageDiv.textContent = text;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        async function sendMessage() {
            const userInput = document.getElementById('user-input');
            const message = userInput.value.trim();
            const loading = document.getElementById('loading');
            
            if (!message) return;
            
            addMessage(message, true);
            userInput.value = '';
            loading.style.display = 'block';
            
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        message: message,
                        session_id: sessionId
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    addMessage('Erro: ' + data.error);
                } else {
                    addMessage(data.response);
                }
            } catch (error) {
                addMessage('Erro de conexão com o servidor');
            } finally {
                loading.style.display = 'none';
            }
        }

        // Enviar mensagem ao pressionar Enter
        document.getElementById('user-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
```

---

## Instruções de deploy no Render (passo a passo)

1. Apague qualquer `Dockerfile` do repositório (se existir).
2. Faça commit & push do repositório com a estrutura mostrada.
3. No Render: **New → Web Service** → Conecte ao repositório e selecione o branch.
4. Em **Environment** escolha `Python 3`.
5. Em **Build Command** coloque (recomendado):

```
pip install --prefer-binary -r requirements.txt
```

6. **Start Command**: deixe em branco (o Render usa o `Procfile`).
7. Em **Environment** (env vars) adicione: `HF_TOKEN` com a sua chave Hugging Face. Opcional: `HF_MODEL` se quiser outro modelo.
8. Crie o serviço e aguarde o build. Ao terminar, acesse a URL que o Render disponibilizar.

---

## Se você ainda preferir rodar o modelo local com Torch (não recomendado no Render gratuito)

* Garanta `runtime.txt` com `python-3.10.12` e use `pip install --prefer-binary -r requirements.txt`.
* Mesmo assim, alguns pacotes podem tentar compilar em Rust se a versão do Python for nova. Em projetos maiores é melhor usar um servidor com suporte (VPS) ou um container próprio.

---

## Próximos passos que eu posso fazer pra você

* Gerar um **script Python** que cria todos esses arquivos localmente (para você só rodar e fazer o commit).
* Ou te passar os comandos git exatos (`git init`, `git add`, `git commit`, `git push`) pra subir no GitHub.

Me diz qual dos dois quer que eu gere agora e eu já deixo pronto.
