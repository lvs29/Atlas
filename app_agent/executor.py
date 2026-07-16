"""
executor.py
-----------
Recebe a decisão estruturada do LLM (dict com "tool" + parâmetros) e
despacha para a função correspondente no registro de tools.

O LLM nunca executa código: ele só escolhe "o quê" fazer, o executor
decide "como".
"""

from __future__ import annotations

from typing import Any

from .tools import TOOLS


class ToolNotFound(Exception):
    pass


def run(decision: dict[str, Any]) -> str:
    tool_name = decision.get("tool")
    if tool_name not in TOOLS:
        raise ToolNotFound(f"Tool desconhecida: {tool_name!r}")

    tool_fn = TOOLS[tool_name]
    return tool_fn(decision)