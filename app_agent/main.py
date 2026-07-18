"""
main.py
-------
Loop de terminal: digite um pedido em linguagem natural, o agente
encadeia quantas tools forem necessárias (loop multi-etapas) até
concluir a tarefa ou responder em texto.

Backend: Ollama local (100% offline, sem chave de API).

Uso:
    python -m app_agent.main
"""

from __future__ import annotations

from . import llm_ollama as llm
from . import scanner


def print_step(decision: dict, result: str) -> None:
    """Callback chamado a cada tool executada dentro do loop do agente."""
    print(f"  [tool] {decision.get('tool')}({ {k: v for k, v in decision.items() if k != 'tool'} })")
    print(f"  [resultado] {result}")


def main() -> None:
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