import ollama
from google import genai
from groq import Groq
#from types import SimpleNamespace

from services.prompts import SYSTEM_PROMPT

from config.config import (
    AI_PROVIDER,
    OLLAMA_MODEL,
    GEMINI_MODEL,
    GEMINI_API_KEY,
    GROQ_MODEL,
    GROQ_API_KEY,
)


def ask_ai(messages):

    if AI_PROVIDER == "ollama":
        return _ask_ollama(messages)

    elif AI_PROVIDER == "gemini":
        return _ask_gemini(messages)

    elif AI_PROVIDER == "groq":
        return _ask_groq(messages)

    else:
        raise ValueError(f"Unsupported AI provider: {AI_PROVIDER}")


def _ask_ollama(messages):

    return ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ] + messages
    )


def _ask_gemini(messages):

    client = genai.Client(api_key=GEMINI_API_KEY)

    contents = [
        {
            "role": "user",
            "parts": [{"text": SYSTEM_PROMPT}]
        }
    ]

    for message in messages:
        contents.append({
            "role": message["role"],
            "parts": [{"text": message["content"]}]
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents
    )

    # Keep the response structure compatible with Ollama
    return {
    "message": {
        "content": response.text
    }
    }

def _ask_groq(messages):

    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ] + messages
    )

    # Keep the response structure compatible with Ollama
    return {
    "message": {
        "content": response.choices[0].message.content
    }
    }