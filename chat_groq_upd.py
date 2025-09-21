# chat_groq_upd.py
import os
import requests
import time
import uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Optional Redis import
try:
    import redis
except Exception:
    redis = None

app = Flask(__name__, template_folder="templates")
CORS(app, resources={r"/*": {"origins": "*"}})

# Config
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() in ("1", "true", "yes")
GROQ_ENDPOINT = os.environ.get("GROQ_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")

# Optional Redis setup (for production use)
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

# In-memory fallback (not persistent across restarts)
session_histories = {}
HISTORY_WINDOW = int(os.environ.get("HISTORY_WINDOW", 20))


def get_history(client_id, session_id):
    key = f"hist:{client_id}:{session_id}"
    if use_redis and r:
        raw = r.get(key)
        if raw:
            try:
                import json
                return json.loads(raw)
            except Exception:
                return []
        return []
    else:
        return session_histories.get(key, [])


def set_history(client_id, session_id, history):
    key = f"hist:{client_id}:{session_id}"
    if use_redis and r:
        import json
        # persist 24h
        r.set(key, json.dumps(history), ex=60 * 60 * 24)
    else:
        session_histories[key] = history


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
        "redis": use_redis
    }, 200


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()
    client_id = data.get("client_id") or data.get("client_name") or "public"
    session_id = data.get("session_id") or f"sess_{uuid.uuid4().hex[:8]}"

    if not user_message:
        return jsonify({"error": "Mensagem vazia"}), 400

    # Test mode (echo)
    if TEST_MODE:
        bot_text = f"[TEST_MODE] Recebi: {user_message}"
        hist = get_history(client_id, session_id)
        hist.append({"role": "user", "content": user_message})
        hist.append({"role": "assistant", "content": bot_text})
        set_history(client_id, session_id, hist[-HISTORY_WINDOW:])
        return jsonify({"response": bot_text, "session_id": session_id})

    if not GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY não configurada"}), 500

    # History management (RAG can be added later)
    history = get_history(client_id, session_id)
    # Optionally prepend a system prompt for branding/personality
    system_prompt = data.get("system_prompt")
    if system_prompt and (not history or history[0].get('role') != 'system'):
        history.insert(0, {"role": "system", "content": system_prompt})

    history.append({"role": "user", "content": user_message})

    payload = {
        "model": GROQ_MODEL,
        "messages": history,
        "max_tokens": int(os.environ.get("MAX_TOKENS", 150)),
        "temperature": float(os.environ.get("TEMPERATURE", 0.7))
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        bot_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Groq error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

    history.append({"role": "assistant", "content": bot_text})
    set_history(client_id, session_id, history[-HISTORY_WINDOW:])

    return jsonify({"response": bot_text, "session_id": session_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
