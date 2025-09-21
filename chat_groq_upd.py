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
if use_redis:
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
if use_redis:
import json
app.run(host="0.0.0.0", port=port)
