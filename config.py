import os

# --- Repos base directory (all source repos auto-cloned here) ---
REPOS_BASE_DIR = os.getenv("REPOS_BASE_DIR", "/home/ubuntu/repos")

# --- Assets-Chatbot repo ---
CHATBOT_REPO_PATH = os.getenv("CHATBOT_REPO_PATH", "/home/ubuntu/repos/assets-chatbot")
CHATBOT_CONTEXT_DIR = os.getenv("CHATBOT_CONTEXT_DIR", "context/repos")

# --- Branch ---
GIT_BRANCH = os.getenv("GIT_BRANCH", "main")

# --- LLM (Groq) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "90"))

# --- Webhook ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
APP_PORT = int(os.getenv("APP_PORT", "5000"))

# --- Commit identity ---
GIT_USER_NAME = os.getenv("GIT_USER_NAME", "readme-bot")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "readme-bot@automation")