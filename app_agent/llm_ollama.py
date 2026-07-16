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

from .agent_loop import MAX_STEPS, SYSTEM_PROMPT, StepCallback, execute_tool
from .tools import OPENAI_TOOLS_SCHEMA

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3.1"


def _call_ollama(messages: list[dict[str, Any]], model: str) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "tools": OPENAI_TOOLS_SCHEMA,
        "stream": False,
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Não consegui conectar ao Ollama em http://localhost:11434. "
            "Ele está rodando? (tente `ollama serve` em outro terminal)"
        ) from exc

    return response.json().get("message", {})


def run_agent(
    user_text: str,
    model: str = DEFAULT_MODEL,
    on_step: StepCallback = None,
    max_steps: int = MAX_STEPS,
) -> str:
    """
    Loop multi-etapas: manda o pedido, executa as tools que o modelo
    escolher, devolve o resultado pra ele, e repete até o modelo
    responder só com texto (sem tool call) ou atingir max_steps.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for _ in range(max_steps):
        message = _call_ollama(messages, model)
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            return message.get("content", "").strip() or "(sem resposta do modelo)"

        # guarda a mensagem do assistente (com as tool_calls) no histórico
        messages.append(message)

        for call in tool_calls:
            fn = call["function"]
            args = fn["arguments"]
            if isinstance(args, str):
                args = json.loads(args)

            decision = {"tool": fn["name"], **args}
            result = execute_tool(decision, on_step)

            messages.append(
                {"role": "tool", "name": fn["name"], "content": result}
            )

    return (
        f"Parei depois de {max_steps} passos sem uma resposta final do modelo. "
        "A tarefa pode ser complexa demais ou o modelo está em loop — "
        "tente um modelo maior ou quebre o pedido em partes menores."
    )


def interpret(user_text: str, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """
    Modo compatível de 1 passo só (mantido por retrocompatibilidade).
    Prefira run_agent() para tarefas que podem precisar de mais de uma tool.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    message = _call_ollama(messages, model)
    tool_calls = message.get("tool_calls") or []

    if not tool_calls:
        raise RuntimeError(
            f"O modelo '{model}' não escolheu nenhuma tool. "
            f"Resposta: {message.get('content', '')}"
        )

    call = tool_calls[0]["function"]
    args = call["arguments"]
    if isinstance(args, str):
        args = json.loads(args)

    return {"tool": call["name"], **args}