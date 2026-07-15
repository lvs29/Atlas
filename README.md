# App Agent

Agente que traduz comandos em linguagem natural ("abra o Chrome e pesquise
por IA") em chamadas de ferramentas seguras, executadas pelo seu código —
o LLM nunca roda código arbitrário, apenas escolhe qual tool usar.

## Arquitetura

```
Usuário → LLM (escolhe tool) → Executor → Tool (browser.open, system.open_app...)
```

- `scanner.py` — descobre automaticamente os apps instalados (Linux/macOS/Windows)
  e monta um índice `{nome: caminho_do_executavel}`. Guarda em
  `~/.app_agent_index.json`.
- `tools.py` — as ferramentas de fato (abrir app, abrir navegador com
  pesquisa, ensinar localização de um app, listar apps conhecidos).
- `executor.py` — pega a decisão do LLM (dict com `tool` + parâmetros) e
  chama a função certa.
- `llm_ollama.py` — backend **local** (padrão): usa o Ollama, com tool
  calling nativo, 100% offline.
- `llm_anthropic.py` — backend na nuvem (Anthropic), caso queira trocar.
- `main.py` — loop de terminal simples para testar tudo. Escolhe o backend
  pela env var `LLM_BACKEND` (`ollama` por padrão, ou `anthropic`).

## Como rodar (local, com Ollama)

```bash
# 1. Instale o Ollama: https://ollama.com/download
# 2. Baixe um modelo com suporte a tool calling
ollama pull llama3.1
# (alternativas: qwen2.5, mistral-nemo, firefunction-v2 — teste qual
#  segue melhor o schema de tools no seu hardware)

# 3. Instale as deps do projeto e rode
pip install -r requirements.txt
python -m app_agent.main
```

O Ollama sobe seu próprio servidor em `http://localhost:11434` assim que
você instala (rode `ollama serve` manualmente se ele não subir sozinho).

## Alternativa: nuvem (Anthropic)

```bash
export LLM_BACKEND=anthropic
export ANTHROPIC_API_KEY="sua-chave-aqui"
python -m app_agent.main
```

Exemplos de comando:

```
> abra o chrome e pesquise por hackathon de IA
> abra o spotify
> liste os apps que você conhece
```

Se um app não for encontrado, você pode ensinar manualmente:

```
> aprenda que o caminho do photoshop é /opt/photoshop/photoshop
```

## Próximos passos sugeridos

1. **Mais tools**: `filesystem.move`, `filesystem.copy`, `terminal.run`
   (com allowlist de comandos!), `email.send`, `calendar.create_event`.
2. **Confirmação antes de agir**: para tools "perigosas" (deletar arquivo,
   rodar comando), peça confirmação do usuário antes de executar.
3. **Reconstruir índice sob demanda**: `scanner.build_index(force=True)`
   quando o usuário instalar algo novo.
4. **Logs**: registre cada decisão do LLM + resultado, para debug e para
   criar um dataset de fine-tuning depois.
5. **Interface**: trocar o `input()` por uma janela (Tkinter/PyQt) ou até
   um app com bandeja do sistema, já que a lógica central não muda.
6. **Modelos locais pequenos alucinam mais**: se o modelo local começar a
   inventar parâmetros ou não chamar tool nenhuma, tente um modelo maior
   (7B+), reduza o número de tools expostas por vez, ou deixe o
   `SYSTEM_PROMPT` mais restritivo/explícito em `llm_ollama.py`.
