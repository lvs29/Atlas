"""
filesystem_tools.py
--------------------
Tools de arquivo: abrir com o programa padrão, listar pasta, ler
conteúdo de um arquivo de texto.

Limites de segurança:
- read_file trunca o conteúdo (MAX_READ_CHARS) para não despejar um
  arquivo gigante inteiro na resposta do modelo.
- list_dir limita a quantidade de entradas mostradas (MAX_LIST_ENTRIES).
- Nenhuma dessas tools deleta ou sobrescreve nada — são só leitura/abertura.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

MAX_READ_CHARS = 5000
MAX_LIST_ENTRIES = 100


def open_file(path_str: str) -> str:
    """Abre um arquivo com o programa padrão do sistema (ex: PDF, imagem, planilha)."""
    path = Path(path_str).expanduser()
    if not path.exists():
        return f"Arquivo não encontrado: {path_str}"

    system = platform.system()
    try:
        if system == "Linux":
            subprocess.Popen(["xdg-open", str(path)])
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        elif system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            return f"Sistema operacional não suportado: {system}"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao abrir '{path_str}': {exc}"

    return f"Abrindo {path}"


def list_dir(path_str: str | None) -> str:
    """Lista o conteúdo de uma pasta (padrão: pasta do usuário, se não informado)."""
    path = Path(path_str).expanduser() if path_str else Path.home()

    if not path.exists():
        return f"Pasta não encontrada: {path}"
    if not path.is_dir():
        return f"'{path}' não é uma pasta."

    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return f"Sem permissão para ler: {path}"

    if not entries:
        return f"{path} está vazia."

    lines = []
    for entry in entries[:MAX_LIST_ENTRIES]:
        kind = "pasta" if entry.is_dir() else "arquivo"
        lines.append(f"[{kind}] {entry.name}")

    suffix = ""
    if len(entries) > MAX_LIST_ENTRIES:
        suffix = f"\n... e mais {len(entries) - MAX_LIST_ENTRIES} itens."

    return f"Conteúdo de {path}:\n" + "\n".join(lines) + suffix


def read_file(path_str: str) -> str:
    """Lê o conteúdo de um arquivo de texto (trunca se for muito grande)."""
    path = Path(path_str).expanduser()

    if not path.exists():
        return f"Arquivo não encontrado: {path_str}"
    if not path.is_file():
        return f"'{path_str}' não é um arquivo."

    try:
        content = path.read_text(errors="ignore")
    except (UnicodeDecodeError, PermissionError, OSError) as exc:
        return f"Não consegui ler '{path_str}' como texto: {exc}"

    truncated = content[:MAX_READ_CHARS]
    if len(content) > MAX_READ_CHARS:
        truncated += f"\n[... truncado, arquivo tem {len(content)} caracteres no total ...]"

    return truncated or "(arquivo vazio)"