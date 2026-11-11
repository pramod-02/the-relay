import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
BACKEND = os.getenv("BACKEND", "standin").lower()
STANDIN_URL = os.getenv("STANDIN_URL", "http://127.0.0.1:8000")
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "3"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "45"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "1"))
DAILY_REQUEST_BUDGET = int(os.getenv("DAILY_REQUEST_BUDGET", "100"))
