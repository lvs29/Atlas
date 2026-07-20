"""
web_search.py
-------------
Ferramentas de web em background (sem abrir navegador nenhum):
- search(): busca no DuckDuckGo
- fetch_page(): lê o texto de uma página específica (só leitura, não clica em nada)
- download(): baixa um arquivo de uma URL

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

Limites de segurança:
- fetch_page trunca o texto extraído (MAX_PAGE_CHARS) e também devolve
  os links reais da página (href resolvidos), pra o modelo ter uma URL
  de verdade pra usar em vez de inventar uma.
- download só salva em DOWNLOAD_DIR (nunca sobrescreve um caminho
  arbitrário do sistema), corta a conexão se o arquivo passar de
  MAX_DOWNLOAD_BYTES, e avisa se o Content-Type devolvido parece ser
  uma página HTML em vez do binário esperado (ex: baixou a home page
  em vez do .exe de verdade).
- Nenhuma dessas tools "interage" com a página (clica, preenche
  formulário, faz login) — é só leitura/download via HTTP puro.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://html.duckduckgo.com/html/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AppAgent/1.0)"}
MAX_RESULTS = 5
MAX_PAGE_CHARS = 3000
MAX_LINKS = 15

DOWNLOAD_DIR = Path.home() / "app_agent_downloads"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
BINARY_EXTENSIONS = (".exe", ".msi", ".zip", ".dmg", ".deb", ".rpm", ".appimage", ".tar.gz")


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


def fetch_page(url: str) -> str:
    """
    Lê o texto de uma página específica (GET + extração de texto, sem
    clicar em nada) e também devolve os links reais encontrados nela,
    pra quem for usar o resultado ter uma URL de verdade em vez de
    precisar adivinhar uma.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        return f"Erro ao acessar '{url}': {exc}"

    soup = BeautifulSoup(response.text, "html.parser")

    # extrai os links ANTES de remover script/nav/footer (eles podem estar lá)
    seen_hrefs: set[str] = set()
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = urljoin(url, a["href"])
        if text and href.startswith(("http://", "https://")) and href not in seen_hrefs:
            seen_hrefs.add(href)
            links.append((text, href))

    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = "\n".join(line for line in text.splitlines() if line.strip())

    if not text and not links:
        return f"A página '{url}' não retornou conteúdo legível."

    truncated = text[:MAX_PAGE_CHARS]
    if len(text) > MAX_PAGE_CHARS:
        truncated += f"\n[... truncado, página tem {len(text)} caracteres no total ...]"

    links_block = ""
    if links:
        top_links = links[:MAX_LINKS]
        lines = [f"- {link_text}: {href}" for link_text, href in top_links]
        links_block = "\n\nLinks encontrados na página (use estes, não invente outros):\n" + "\n".join(lines)

    return f"Conteúdo de {url}:\n{truncated}{links_block}"


def download(url: str, filename: str | None = None) -> str:
    """Baixa um arquivo de uma URL para DOWNLOAD_DIR (nunca em outro lugar do sistema)."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1].split("?")[0] or "download"
    dest = DOWNLOAD_DIR / filename

    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=30) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            total_bytes = 0
            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DOWNLOAD_BYTES:
                        f.close()
                        dest.unlink(missing_ok=True)
                        return (
                            f"Download cancelado: arquivo passou de "
                            f"{MAX_DOWNLOAD_BYTES // (1024 * 1024)}MB."
                        )
                    f.write(chunk)
    except requests.exceptions.RequestException as exc:
        return f"Erro ao baixar '{url}': {exc}"

    warning = ""
    expects_binary = filename.lower().endswith(BINARY_EXTENSIONS)
    looks_like_html = "html" in content_type.lower()
    if expects_binary and looks_like_html:
        warning = (
            f"\nAVISO: o servidor devolveu Content-Type '{content_type}', que parece "
            "ser uma página HTML, não o arquivo binário esperado. É provável que a URL "
            "usada seja a página do site (não o link direto do arquivo) — confira o "
            "conteúdo antes de considerar isso o arquivo real."
        )

    return f"Baixado em {dest} ({total_bytes} bytes, Content-Type: {content_type or 'desconhecido'}){warning}"