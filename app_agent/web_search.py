"""
web_search.py
-------------
Busca na web em background (sem abrir navegador nenhum) para o agente
usar quando não sabe a resposta de algo.

Usa o DuckDuckGo HTML (html.duckduckgo.com), que:
- não precisa de chave de API;
- não precisa de JavaScript/navegador headless (é só um GET + parse de HTML);
- é o motor de busca mais tolerante a scraping simples.

Nota sobre "resultado do Gemini": a caixa de AI Overview do Google não
tem API pública, muda de estrutura com frequência e fazer scraping dela
viola os Termos de Serviço do Google. Em vez disso, esta tool traz os
melhores resultados de busca como texto, e o próprio LLM do agente
sintetiza a resposta final a partir deles (no próximo passo do loop),
o que dá um resultado equivalente sem depender de scraping frágil.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://html.duckduckgo.com/html/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AppAgent/1.0)"}
MAX_RESULTS = 5


def search(query: str, max_results: int = MAX_RESULTS) -> str:
    """Busca a query e devolve título + trecho dos melhores resultados, como texto."""
    try:
        response = requests.post(
            SEARCH_URL, data={"q": query}, headers=HEADERS, timeout=15
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        return f"Erro ao pesquisar: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one(".result__title")
        snippet_el = result.select_one(".result__snippet")

        title = title_el.get_text(strip=True) if title_el else ""
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        if title or snippet:
            results.append(f"- {title}: {snippet}")

    if not results:
        return f"Nenhum resultado encontrado para '{query}'."

    return "Resultados da pesquisa:\n" + "\n".join(results)