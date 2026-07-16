"""
tools.py
--------
Cada função aqui é uma "tool" que o LLM pode escolher, sempre com
parâmetros explícitos (nunca código arbitrário).
"""

from __future__ import annotations

import subprocess
import urllib.parse
from typing import Any, Callable

from . import scanner
from . import web_search as web_search_module


def open_app(params: dict[str, Any]) -> str:
    """{"tool": "system.open_app", "app": "spotify"}"""
    app_name = params["app"]
    path = scanner.resolve_app(app_name)

    if not path:
        return (
            f"Não encontrei '{app_name}' instalado. "
            f"Você pode me dizer o caminho do executável para eu aprender."
        )

    subprocess.Popen([path])
    return f"Abrindo {app_name} ({path})"


def open_browser(params: dict[str, Any]) -> str:
    """{"tool": "browser.open", "browser": "chrome", "query": "inteligência artificial"}"""
    browser = params.get("browser", "chrome")
    query = params.get("query") or params.get("search")

    path = scanner.resolve_app(browser)
    if not path:
        return f"Não encontrei o navegador '{browser}' instalado."

    args = [path]
    if query:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        args.append(url)

    subprocess.Popen(args)
    return f"Abrindo {browser}" + (f" pesquisando por '{query}'" if query else "")


def learn_app_location(params: dict[str, Any]) -> str:
    """{"tool": "system.learn_app", "app": "photoshop", "path": "/opt/photoshop/photoshop"}"""
    scanner.learn_app(params["app"], params["path"])
    return f"Aprendido: '{params['app']}' -> {params['path']}"


def list_known_apps(params: dict[str, Any]) -> str:
    """{"tool": "system.list_apps"}"""
    index = scanner.build_index()
    names = sorted(set(index.keys()))
    preview = ", ".join(names[:30])
    return f"{len(names)} apps conhecidos. Exemplos: {preview}"


def web_search(params: dict[str, Any]) -> str:
    """{"tool": "web.search", "query": "quem ganhou o oscar de 2026"}"""
    query = params["query"]
    return web_search_module.search(query)


# Registro central: nome da tool -> função executora
TOOLS: dict[str, Callable[[dict[str, Any]], str]] = {
    "system.open_app": open_app,
    "browser.open": open_browser,
    "system.learn_app": learn_app_location,
    "system.list_apps": list_known_apps,
    "web.search": web_search,
}


TOOLS_SCHEMA = [
    {
        "name": "system.open_app",
        "description": "Abre um aplicativo instalado no sistema pelo nome.",
        "input_schema": {
            "type": "object",
            "properties": {"app": {"type": "string"}},
            "required": ["app"],
        },
    },
    {
        "name": "browser.open",
        "description": "Abre um navegador, opcionalmente já pesquisando um termo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "browser": {"type": "string", "description": "ex: chrome, firefox"},
                "query": {"type": "string", "description": "termo de pesquisa (opcional)"},
            },
            "required": ["browser"],
        },
    },
    {
        "name": "system.learn_app",
        "description": "Ensina o caminho de um app que não foi encontrado automaticamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["app", "path"],
        },
    },
    {
        "name": "system.list_apps",
        "description": "Lista os apps conhecidos pelo índice atual.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "web.search",
        "description": (
            "Pesquisa na web em background, sem abrir nenhuma janela para o "
            "usuário. Use quando você não souber a resposta de algo, ou "
            "precisar de informação atual (notícias, preços, eventos "
            "recentes, fatos que podem ter mudado). Depois de receber os "
            "resultados, responda ao usuário em texto com um resumo da "
            "resposta — não despeje os resultados brutos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "termo de busca"}
            },
            "required": ["query"],
        },
    },
]


def to_openai_format(schema: list[dict]) -> list[dict]:
    """
    Converte o schema (formato Anthropic: name/description/input_schema)
    para o formato OpenAI-style (type/function/parameters), usado pelo
    Ollama e por outros runtimes locais compatíveis.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in schema
    ]


OPENAI_TOOLS_SCHEMA = to_openai_format(TOOLS_SCHEMA)