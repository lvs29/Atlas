"""
llm_anthropic.py
----------------
Backend que usa a API da Anthropic (nuvem) pedindo tool use: o modelo
recebe a frase do usuário e devolve qual tool chamar + parâmetros
(JSON), nunca código.

Requer a env var ANTHROPIC_API_KEY.

Alternativa local: veja llm_ollama.py
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from .tools import TOOLS_SCHEMA

SYSTEM_PROMPT = (
    "Você é um agente que traduz pedidos do usuário em chamadas de "
    "ferramentas do sistema operacional. Sempre responda usando uma "
    "tool call. Nunca invente parâmetros que o usuário não pediu."
)


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Defina a variável de ambiente ANTHROPIC_API_KEY antes de rodar."
        )
    return anthropic.Anthropic(api_key=api_key)


def interpret(user_text: str) -> dict[str, Any]:
    """Manda o texto do usuário para o modelo e retorna a decisão estruturada."""
    client = get_client()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        tools=TOOLS_SCHEMA,
        messages=[{"role": "user", "content": user_text}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return {"tool": block.name, **block.input}

    # Se o modelo não chamou nenhuma tool, devolve o texto pra debug
    text_blocks = [b.text for b in response.content if b.type == "text"]
    raise RuntimeError(
        "O modelo não escolheu nenhuma tool. Resposta: " + " ".join(text_blocks)
    )
