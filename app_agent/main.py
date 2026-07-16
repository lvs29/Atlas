"""
main.py
-------
Loop de terminal: digite um pedido em linguagem natural, o agente
encadeia quantas tools forem necessárias (loop multi-etapas) até
concluir a tarefa ou responder em texto.

Backend padrão: Ollama local (LLM_BACKEND=ollama).
Para usar a API da Anthropic na nuvem em vez disso:
    export LLM_BACKEND=anthropic
    export ANTHROPIC_API_KEY=...

Uso:
    python -m app_agent.main
"""

from __future__ import annotations

import os

from . import scanner

BACKEND = os.environ.get("LLM_BACKEND", "ollama")

if BACKEND == "anthropic":
    from . import llm_anthropic as llm
else:
    from . import llm_ollama as llm


def print_step(decision: dict, result: str) -> None:
    """Callback chamado a cada tool executada dentro do loop do agente."""
    print(f"  [tool] {decision.get('tool')}({ {k: v for k, v in decision.items() if k != 'tool'} })")
    print(f"  [resultado] {result}")


def main() -> None:
    print(f"Backend: {BACKEND}")
    print("Indexando aplicativos instalados... (só na primeira vez)")
    scanner.build_index()
    print("Pronto! Digite um comando (ou 'sair').\n")

    while True:
        try:
            user_text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_text or user_text.lower() in {"sair", "exit", "quit"}:
            break

        try:
            final_text = llm.run_agent(user_text, on_step=print_step)
            print(final_text)
        except Exception as exc:  # noqa: BLE001 - loop de CLI, queremos capturar tudo
            print(f"Erro: {exc}")


if __name__ == "__main__":
    main()