"""
main.py
-------
Loop de terminal: digite um pedido em linguagem natural, o LLM decide
a tool, o executor roda.

Backend padrão: Ollama local (LLM_BACKEND=ollama).
Para usar a API da Anthropic na nuvem em vez disso:
    export LLM_BACKEND=anthropic
    export ANTHROPIC_API_KEY=...

Uso:
    python -m app_agent.main
"""

from __future__ import annotations

import os

from . import executor, scanner

BACKEND = os.environ.get("LLM_BACKEND", "ollama")

if BACKEND == "anthropic":
    from . import llm_anthropic as llm
else:
    from . import llm_ollama as llm


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
            decision = llm.interpret(user_text)
            print(f"[decisão] {decision}")
            result = executor.run(decision)
            print(result)
        except Exception as exc:  # noqa: BLE001 - loop de CLI, queremos capturar tudo
            print(f"Erro: {exc}")


if __name__ == "__main__":
    main()
