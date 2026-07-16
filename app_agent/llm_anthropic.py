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

import os
from typing import Any

import anthropic

from .agent_loop import MAX_STEPS, SYSTEM_PROMPT, StepCallback, execute_tool
from .tools import TOOLS_SCHEMA

MODEL = "claude-sonnet-4-6"


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Defina a variável de ambiente ANTHROPIC_API_KEY antes de rodar."
        )
    return anthropic.Anthropic(api_key=api_key)


def run_agent(
    user_text: str,
    on_step: StepCallback = None,
    max_steps: int = MAX_STEPS,
) -> str:
    """
    Loop multi-etapas: manda o pedido, executa as tools que o modelo
    escolher, devolve o resultado pra ele, e repete até o modelo
    responder só com texto (sem tool call) ou atingir max_steps.
    """
    client = get_client()
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_text}]

    for _ in range(max_steps):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b.text for b in response.content if b.type == "text"]

        # guarda a resposta do assistente (texto + tool_use) no histórico
        messages.append({"role": "assistant", "content": response.content})

        if not tool_use_blocks:
            return " ".join(text_blocks).strip() or "(sem resposta do modelo)"

        tool_results = []
        for block in tool_use_blocks:
            decision = {"tool": block.name, **block.input}
            result = execute_tool(decision, on_step)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )

        messages.append({"role": "user", "content": tool_results})

    return (
        f"Parei depois de {max_steps} passos sem uma resposta final do modelo. "
        "A tarefa pode ser complexa demais ou o modelo está em loop — "
        "tente quebrar o pedido em partes menores."
    )


def interpret(user_text: str) -> dict[str, Any]:
    """
    Modo compatível de 1 passo só (mantido por retrocompatibilidade).
    Prefira run_agent() para tarefas que podem precisar de mais de uma tool.
    """
    client = get_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        tools=TOOLS_SCHEMA,
        messages=[{"role": "user", "content": user_text}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return {"tool": block.name, **block.input}

    text_blocks = [b.text for b in response.content if b.type == "text"]
    raise RuntimeError(
        "O modelo não escolheu nenhuma tool. Resposta: " + " ".join(text_blocks)
    )