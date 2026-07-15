"""
llm_ollama.py
-------------
Backend que roda 100% local via Ollama (https://ollama.com), usando a
API de chat com tool calling nativo. Não sai da máquina, não precisa
de chave de API.

Pré-requisitos:
    1. Instalar o Ollama: https://ollama.com/download
    2. Baixar um modelo com suporte a tool calling, por ex:
           ollama pull llama3.1
       (outras opções: qwen2.5, mistral-nemo, firefunction-v2)
    3. O serviço do Ollama já sobe sozinho em http://localhost:11434
       depois da instalação (rodar `ollama serve` se não estiver ativo).

Modelos pequenos "alucinam" tool call com mais frequência que modelos
grandes na nuvem — vale testar 2 ou 3 modelos e ver qual segue melhor
o schema no seu hardware.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from .tools import OPENAI_TOOLS_SCHEMA

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3.1"

SYSTEM_PROMPT = (
    "Você é um agente que traduz pedidos do usuário em chamadas de "
    "ferramentas do sistema operacional. Sempre responda usando uma "
    "tool call. Nunca invente parâmetros que o usuário não pediu."
)


def interpret(user_text: str, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Manda o texto do usuário para o Ollama local e retorna a decisão estruturada."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "tools": OPENAI_TOOLS_SCHEMA,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Não consegui conectar ao Ollama em http://localhost:11434. "
            "Ele está rodando? (tente `ollama serve` em outro terminal)"
        ) from exc

    data = response.json()
    message = data.get("message", {})
    tool_calls = message.get("tool_calls") or []

    if not tool_calls:
        content = message.get("content", "")
        raise RuntimeError(
            f"O modelo '{model}' não escolheu nenhuma tool. Resposta: {content}"
        )

    call = tool_calls[0]["function"]
    args = call["arguments"]
    # o Ollama às vezes devolve os argumentos como string JSON, às vezes como dict
    if isinstance(args, str):
        args = json.loads(args)

    return {"tool": call["name"], **args}
