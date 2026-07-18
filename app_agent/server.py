"""
server.py
---------
Expõe o agente como servidor HTTP: você manda um prompt, ele roda o
loop multi-etapas (tools + web.search quando precisar) e devolve tanto
o "processo de pensamento" (cada tool chamada + resultado) quanto a
resposta final.

Backend: Ollama local (100% offline, sem chave de API).

Uso (desenvolvimento, com auto-reload):
    uvicorn app_agent.server:app --reload --host 0.0.0.0 --port 8080

Uso (produção):
    python -m app_agent.server
    # ou, recomendado, via um servidor ASGI de produção:
    uvicorn app_agent.server:app --host 0.0.0.0 --port 8080 --workers 4

A porta pode ser configurada pela variável de ambiente PORT (padrão: 8080),
seguindo a convenção usada por serviços de deploy como Heroku, Railway e
Cloud Run.

Teste com:
    curl -X POST http://localhost:8080/run \
         -H "Content-Type: application/json" \
         -d '{"prompt": "abra o vscode"}'

Docs interativas (Swagger) em: http://localhost:8080/docs
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import llm_ollama as llm
from . import scanner

DEFAULT_PORT = 8080

app = FastAPI(
    title="App Agent Server",
    description="Agente que traduz linguagem natural em ações no sistema.",
    version="1.0.0",
)


class RunRequest(BaseModel):
    prompt: str


class Step(BaseModel):
    tool: str
    params: dict[str, Any]
    result: str


class RunResponse(BaseModel):
    steps: list[Step]
    final_answer: str


@app.on_event("startup")
def build_app_index() -> None:
    """Indexa os apps instalados uma vez, na subida do servidor."""
    scanner.build_index()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest) -> RunResponse:
    """
    Roda o agente para um prompt e devolve o processo de pensamento
    (cada tool chamada + resultado, na ordem) e a resposta final.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="O campo 'prompt' não pode ser vazio.")

    steps: list[Step] = []

    def on_step(decision: dict[str, Any], result: str) -> None:
        tool_name = decision.get("tool", "?")
        params = {k: v for k, v in decision.items() if k != "tool"}
        steps.append(Step(tool=tool_name, params=params, result=result))

    try:
        final_answer = llm.run_agent(request.prompt, on_step=on_step)
    except RuntimeError as exc:
        # ex: Ollama não está rodando
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RunResponse(steps=steps, final_answer=final_answer)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", DEFAULT_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)