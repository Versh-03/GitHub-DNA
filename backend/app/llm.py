"""Thin LLM adapter. Configured for Groq API with openai/gpt-oss-20b."""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load from backend/.env or root .env
backend_env = Path(__file__).resolve().parents[1] / ".env"
root_env = Path(__file__).resolve().parents[2] / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv()


class LLMNotConfigured(Exception):
    pass


def llm_available() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY"))


def get_model() -> str:
    return os.getenv("LLM_MODEL", "openai/gpt-oss-20b")


def _client() -> OpenAI:
    key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    if not key:
        raise LLMNotConfigured("GROQ_API_KEY or LLM_API_KEY is not set. Configure backend/.env")
    return OpenAI(
        api_key=key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        timeout=60,
        max_retries=0,  # Explicit single retry control managed by agent orchestrator
    )


def chat(messages: list, tools: list | None = None, temperature: float = 0.2,
         max_tokens: int = 1200, tool_choice="auto"):
    """Send messages to the LLM. Returns the assistant message object
    (has .content and, if the model wants to use a tool, .tool_calls)."""
    kwargs = dict(
        model=get_model(),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    response = _client().chat.completions.create(**kwargs)
    return response.choices[0].message
