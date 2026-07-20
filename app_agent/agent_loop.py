"""
agent_loop.py
-------------
Lógica do "loop de agente": em vez de escolher 1 tool e parar, o
modelo vê o resultado de cada ação e decide se chama outra tool ou
se já pode responder em texto dizendo que terminou.

Isso é o que permite tarefas compostas, tipo:
    "abra o VS Code e depois abra o navegador na documentação do projeto"

Usado pelo backend do agente (llm_ollama.py), que formata as mensagens
no protocolo da API do Ollama e delega a execução das tools pra cá.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from . import executor

MAX_STEPS = 8

# Callback opcional: (decision: dict, result: str) -> None
# Usado pro chamador (ex: main.py) mostrar progresso passo a passo.
StepCallback = Optional[Callable[[dict[str, Any], str], None]]

SYSTEM_PROMPT = (
    "Você é um agente que executa tarefas no computador do usuário "
    "chamando ferramentas do sistema operacional, uma ou mais vezes em "
    "sequência. Depois de ver o resultado de cada ferramenta, decida se "
    "precisa chamar outra para completar o pedido, ou se já pode "
    "responder em texto explicando o que foi feito. "
    "Nunca invente parâmetros que o usuário não pediu. "
    "\n\n"
    "REGRA CRÍTICA: nunca invente uma URL, link ou caminho de arquivo. "
    "Se você não sabe o endereço exato de algo, use web.search (pra "
    "achar o site certo) e/ou web.fetch_page (pra ler uma página e "
    "pegar os links reais listados nela) ANTES de usar essa URL em "
    "outra tool como web.download ou browser.open_url. Nunca use "
    "domínios de exemplo (como example.com) ou caminhos-modelo (como "
    "'/caminho/do/arquivo') como se fossem reais — se você não tem um "
    "valor real vindo do usuário ou do resultado de uma tool anterior, "
    "não invente um, peça mais informação ou pesquise primeiro. "
    "\n\n"
    "'browser' em browser.open precisa ser sempre o nome de um "
    "navegador de verdade instalado (chrome, firefox, vivaldi, edge...) "
    "— nunca o nome de um site (youtube, google, etc). Para abrir um "
    "site ou link específico, use browser.open_url com a URL completa. "
    "\n\n"
    "Se uma ferramenta falhar ou um app não for encontrado, explique o "
    "problema em texto em vez de insistir chamando a mesma tool de novo "
    "com os mesmos parâmetros. "
    "Se o usuário perguntar algo que você não sabe responder com "
    "confiança, ou que exija informação atual, use a tool web.search "
    "para pesquisar antes de responder — nunca invente uma resposta. "
    "Depois de pesquisar, responda em texto com um resumo da informação "
    "encontrada, na sua própria voz, sem apenas colar os resultados "
    "brutos da busca. "
    "Só leia, abra ou baixe arquivos e páginas que sejam claramente "
    "relevantes para o que o usuário pediu — não explore o sistema de "
    "arquivos ou baixe coisas por conta própria. "
    "\n\n"
    "Sua resposta final em texto deve refletir fielmente o que as "
    "ferramentas realmente fizeram: se uma tool já executou uma ação "
    "com sucesso, não negue nem contradiga isso na resposta final."
)


def execute_tool(decision: dict[str, Any], on_step: StepCallback = None) -> str:
    """Roda uma tool via executor, capturando erro como texto (pro modelo se adaptar)."""
    try:
        result = executor.run(decision)
    except Exception as exc:  # noqa: BLE001 - queremos devolver o erro pro modelo, não crashar
        result = f"Erro ao executar '{decision.get('tool')}': {exc}"

    if on_step:
        on_step(decision, result)

    return result