"""
agent_loop.py
-------------
Lógica do "loop de agente": em vez de escolher 1 tool e parar, o
modelo vê o resultado de cada ação e decide se chama outra tool ou
se já pode responder em texto dizendo que terminou.

Isso é o que permite tarefas compostas, tipo:
    "abra o VS Code e depois abra o navegador na documentação do projeto"

Backend-agnóstico: os backends (llm_ollama.py, llm_anthropic.py) só
formatam mensagens no protocolo de cada API e delegam a execução das
tools pra cá.
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
    "Se uma ferramenta falhar ou um app não for encontrado, explique o "
    "problema em texto em vez de insistir chamando a mesma tool de novo "
    "com os mesmos parâmetros. "
    "Se o usuário perguntar algo que você não sabe responder com "
    "confiança, ou que exija informação atual, use a tool web.search "
    "para pesquisar antes de responder — nunca invente uma resposta. "
    "Depois de pesquisar, responda em texto com um resumo da informação "
    "encontrada, na sua própria voz, sem apenas colar os resultados "
    "brutos da busca."
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