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

from . import filesystem_tools
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
        known = scanner.list_known_browsers()
        hint = (
            f" Navegadores encontrados no sistema: {', '.join(known)}."
            if known
            else " Nenhum navegador conhecido foi encontrado no sistema."
        )
        return f"'{browser}' não é um navegador instalado.{hint}"

    args = [path]
    if query:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        args.append(url)

    subprocess.Popen(args)
    return f"Abrindo {browser}" + (f" pesquisando por '{query}'" if query else "")


def open_url(params: dict[str, Any]) -> str:
    """{"tool": "browser.open_url", "url": "https://www.youtube.com/results?search_query=mr+beast"}"""
    url = params["url"]
    browser_name = params.get("browser")

    if browser_name:
        path = scanner.resolve_app(browser_name)
        used_name = browser_name
    else:
        path, used_name = scanner.resolve_any_browser()

    if not path:
        return "Não encontrei nenhum navegador instalado para abrir essa URL."

    subprocess.Popen([path, url])
    return f"Abrindo {url} no {used_name}"


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


def open_file(params: dict[str, Any]) -> str:
    """{"tool": "filesystem.open_file", "path": "/home/user/documento.pdf"}"""
    return filesystem_tools.open_file(params["path"])


def list_dir(params: dict[str, Any]) -> str:
    """{"tool": "filesystem.list_dir", "path": "/home/user/Downloads"}"""
    return filesystem_tools.list_dir(params.get("path"))


def read_file(params: dict[str, Any]) -> str:
    """{"tool": "filesystem.read_file", "path": "/home/user/notas.txt"}"""
    return filesystem_tools.read_file(params["path"])


def download_file(params: dict[str, Any]) -> str:
    """{"tool": "web.download", "url": "https://exemplo.com/arquivo.pdf"}"""
    return web_search_module.download(params["url"], params.get("filename"))


def fetch_page(params: dict[str, Any]) -> str:
    """{"tool": "web.fetch_page", "url": "https://exemplo.com/artigo"}"""
    return web_search_module.fetch_page(params["url"])


# Registro central: nome da tool -> função executora
TOOLS: dict[str, Callable[[dict[str, Any]], str]] = {
    "system.open_app": open_app,
    "browser.open": open_browser,
    "browser.open_url": open_url,
    "system.learn_app": learn_app_location,
    "system.list_apps": list_known_apps,
    "web.search": web_search,
    "filesystem.open_file": open_file,
    "filesystem.list_dir": list_dir,
    "filesystem.read_file": read_file,
    "web.download": download_file,
    "web.fetch_page": fetch_page,
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
        "description": (
            "Abre um navegador, opcionalmente já pesquisando um termo no "
            "Google. IMPORTANTE: 'browser' precisa ser o nome de um "
            "navegador de verdade instalado (chrome, firefox, vivaldi, "
            "edge...) — nunca o nome de um site (não use 'youtube', "
            "'google', etc). Para abrir um site específico, use "
            "browser.open_url."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "browser": {"type": "string", "description": "nome do navegador instalado, ex: chrome, firefox"},
                "query": {"type": "string", "description": "termo de pesquisa no Google (opcional)"},
            },
            "required": ["browser"],
        },
    },
    {
        "name": "browser.open_url",
        "description": (
            "Abre uma URL completa e específica no navegador (ex: um site "
            "direto, um resultado de busca do YouTube, um link encontrado "
            "por web.fetch_page). Use esta tool em vez de browser.open "
            "quando você já tem a URL exata que quer abrir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL completa a abrir"},
                "browser": {"type": "string", "description": "navegador a usar (opcional; usa o primeiro encontrado se omitido)"},
            },
            "required": ["url"],
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
    {
        "name": "filesystem.open_file",
        "description": "Abre um arquivo específico (caminho completo) com o programa padrão do sistema.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "caminho completo do arquivo"}},
            "required": ["path"],
        },
    },
    {
        "name": "filesystem.list_dir",
        "description": "Lista os arquivos e pastas dentro de uma pasta. Se 'path' não for informado, usa a pasta do usuário.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "caminho da pasta (opcional)"}},
        },
    },
    {
        "name": "filesystem.read_file",
        "description": "Lê o conteúdo de um arquivo de texto (trunca se for muito grande).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "caminho completo do arquivo"}},
            "required": ["path"],
        },
    },
    {
        "name": "web.download",
        "description": "Baixa um arquivo de uma URL para a pasta de downloads do agente (~/app_agent_downloads).",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL do arquivo"},
                "filename": {"type": "string", "description": "nome do arquivo salvo (opcional)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web.fetch_page",
        "description": (
            "Lê o texto de uma página web específica (só leitura — não "
            "clica em nada, não preenche formulário, não faz login). Use "
            "quando o usuário mandar um link e pedir pra ler/resumir o "
            "conteúdo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL da página"}},
            "required": ["url"],
        },
    },
]


def to_openai_format(schema: list[dict]) -> list[dict]:
    """
    Converte o schema (formato name/description/input_schema) para o
    formato OpenAI-style (type/function/parameters), usado pelo Ollama
    e por outros runtimes locais compatíveis.
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