# chat_groq_upd.py
import os
import re
import time
import uuid
import json
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# Optional Redis import (se usar, configure REDIS_URL)
try:
    import redis
except Exception:
    redis = None

app = Flask(__name__, template_folder="templates")
CORS(app, resources={r"/*": {"origins": "*"}})

# Serve embed.min.js (coloque o arquivo em /static/embed.min.js)
@app.route('/embed.min.js')
def embed_js():
    return send_from_directory('static', 'embed.min.js')

# ------------ CONFIGURÁVEIS via ENV ------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_ENDPOINT = os.environ.get("GROQ_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")

# Assistent name (usar no lugar de "ChatGPT" / "OpenAI" etc)
ASSISTANT_NAME = os.environ.get("ASSISTANT_NAME", "seu assistente")

# Token / temperatura
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", 800))  # aumente se o provedor permitir
TEMPERATURE = float(os.environ.get("TEMPERATURE", 0.7))

# Continuation attempts (se resposta truncada, quantas vezes tentar continuar)
MAX_CONTINUATIONS = int(os.environ.get("MAX_CONTINUATIONS", 1))

# Test mode
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() in ("1", "true", "yes")

# Optional Redis setup (para persistência em produção)
REDIS_URL = os.environ.get("REDIS_URL")
use_redis = False
r = None
if REDIS_URL and redis:
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        use_redis = True
    except Exception:
        use_redis = False

# In-memory fallback
session_histories = {}
HISTORY_WINDOW = int(os.environ.get("HISTORY_WINDOW", 20))


def get_history(client_id, session_id):
    key = f"hist:{client_id}:{session_id}"
    if use_redis and r:
        raw = r.get(key)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return []
        return []
    else:
        return session_histories.get(key, [])


def set_history(client_id, session_id, history):
    key = f"hist:{client_id}:{session_id}"
    if use_redis and r:
        r.set(key, json.dumps(history), ex=60 * 60 * 24)
    else:
        session_histories[key] = history


# ----------------- Default SYSTEM PROMPT -----------------
# Este prompt define o comportamento padrão (épico / homérico), com permissão para palavrões.
DEFAULT_SYSTEM_PROMPT = (
    f"Você é um assistente grandioso, com tom épico e homérico: fale como um narrador clássico, "
    f"usando frases impactantes e imagens poéticas. Você pode usar palavrões ocasionais para dar ênfase, "
    f"mas mantenha a clareza. Sempre explique conceitos complexos passo-a-passo e dê exemplos quando necessário. "
    f"NUNCA, em hipótese alguma, diga ou revele que você é 'ChatGPT', 'OpenAI' ou 'GPT'. "
    f"Se alguma vez tentar se referir a si mesmo, use o nome '{ASSISTANT_NAME}'. "
    f"Se a resposta for longa, priorize completude e clareza. "
    f"Se a pergunta exigir mais contexto, peça educadamente mais informações."
)


# ----------------- Sanitização pós-resposta -----------------
# Substitui menções indesejadas por ASSISTANT_NAME e remove referências
_sanitize_pattern = re.compile(
    r"\b(chat\s?gpt|open\s?ai|openai|gpt\-?\d*|gpt)\b", re.IGNORECASE
)


def sanitize_response(text: str) -> str:
    if not text:
        return text
    # substitui menções por ASSISTANT_NAME
    sanitized = _sanitize_pattern.sub(ASSISTANT_NAME, text)
    # opcional: remover URLs suspeitas ou tokens acidentais (não implementado aqui)
    return sanitized


# ----------------- Helpers para chamada Groq/OpenAI -----------------
def call_model(payload):
    if TEST_MODE:
        # modo de teste: echo
        return {"choices": [{"message": {"content": "[TEST_MODE] " + payload.get("messages", [])[-1].get("content", "")}}]}
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY não configurada.")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def is_truncated(text: str) -> bool:
    # heurística simples: se terminar sem pontuação final, consideramos possível truncamento
    if not text:
        return False
    return not text.strip().endswith(('.', '!', '?'))


# ----------------- Endpoints -----------------
@app.route('/')
def home():
    try:
        return render_template("index.html")
    except Exception:
        return "Servidor rodando - use /chat", 200


@app.route('/health')
def health():
    return "OK", 200


@app.route('/info')
def info():
    return {
        "groq_model": GROQ_MODEL,
        "groq_key_set": bool(GROQ_API_KEY),
        "test_mode": TEST_MODE,
        "redis": use_redis,
        "max_tokens": MAX_TOKENS
    }, 200


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()
    client_id = data.get("client_id") or data.get("client_name") or "public"
    session_id = data.get("session_id") or f"sess_{uuid.uuid4().hex[:8]}"

    if not user_message:
        return jsonify({"error": "Mensagem vazia"}), 400

    # Get or create history
    history = get_history(client_id, session_id)

    # Determine system prompt:
    # 1) If request provided explicit system_prompt, use it
    # 2) Else use a client-specific prompt map stored in server (you can expand this map)
    # 3) Else fallback to DEFAULT_SYSTEM_PROMPT
    client_prompt_override = data.get("system_prompt")
    PROMPT_MAP = data.get("prompt_map") or {}  # allows passing a small map in request if desired

    system_prompt = client_prompt_override or PROMPT_MAP.get(client_id) or DEFAULT_SYSTEM_PROMPT

    # Ensure system prompt is the first message for the session
    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": system_prompt})

    # append user message
    history.append({"role": "user", "content": user_message})

    # keep window
    history = history[-HISTORY_WINDOW:]
    # prepare payload
    payload = {
        "model": GROQ_MODEL,
        "messages": history,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE
    }

    try:
        # First attempt
        resp_json = call_model(payload)
        bot_text = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        # Sanitizar
        bot_text = sanitize_response(bot_text)

        # Se parecer truncado, tentar continuação automática (até MAX_CONTINUATIONS)
        continuations = 0
        while is_truncated(bot_text) and continuations < MAX_CONTINUATIONS:
            continuations += 1
            # append assistant partial, then ask to continue
            history.append({"role": "assistant", "content": bot_text})
            history.append({"role": "user", "content": "Por favor, continue a resposta anterior."})
            history = history[-HISTORY_WINDOW:]
            payload["messages"] = history
            resp_json = call_model(payload)
            more = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            more = sanitize_response(more)
            # concatena
            bot_text = (bot_text + "\n" + more).strip()

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Groq error: {str(e)}"}), 500
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

    # finalize history and save
    history.append({"role": "assistant", "content": bot_text})
    set_history(client_id, session_id, history[-HISTORY_WINDOW:])

    return jsonify({"response": bot_text, "session_id": session_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
