"""
scanner.py
----------
Descobre automaticamente os aplicativos instalados no sistema e monta
um índice {nome_normalizado: caminho_do_executavel}.

Isso evita ter que cadastrar manualmente cada programa (abordagem 2
do brainstorm: "Descoberta automática").
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
from pathlib import Path


INDEX_FILE = Path.home() / ".app_agent_index.json"


def _normalize(name: str) -> str:
    """Deixa o nome minúsculo e sem caracteres estranhos, para facilitar o match."""
    name = name.lower().strip()
    name = re.sub(r"\.(exe|desktop|app)$", "", name)
    name = re.sub(r"[^a-z0-9\s]", "", name)
    return name.strip()


def _scan_linux() -> dict[str, str]:
    apps: dict[str, str] = {}

    # 1) Arquivos .desktop (têm nome "bonito" + caminho do Exec)
    desktop_dirs = [
        Path("/usr/share/applications"),
        Path.home() / ".local/share/applications",
    ]
    for d in desktop_dirs:
        if not d.exists():
            continue
        for f in d.glob("*.desktop"):
            try:
                content = f.read_text(errors="ignore")
            except OSError:
                continue

            name_match = re.search(r"^Name=(.+)$", content, re.MULTILINE)
            exec_match = re.search(r"^Exec=(.+)$", content, re.MULTILINE)
            if not name_match or not exec_match:
                continue

            pretty_name = name_match.group(1).strip()
            # remove placeholders tipo %U, %f, %F do Exec
            exec_cmd = re.sub(r"%[a-zA-Z]", "", exec_match.group(1)).strip()
            exec_bin = exec_cmd.split()[0] if exec_cmd else None
            if not exec_bin:
                continue

            apps[_normalize(pretty_name)] = exec_bin
            apps[_normalize(f.stem)] = exec_bin  # também indexa pelo slug do arquivo

    # 2) Executáveis soltos no PATH (fallback, cobre CLIs sem .desktop)
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(path_dir)
        if not p.exists():
            continue
        for exe in p.iterdir():
            if os.access(exe, os.X_OK) and exe.is_file():
                apps.setdefault(_normalize(exe.name), str(exe))

    return apps


def _scan_macos() -> dict[str, str]:
    apps: dict[str, str] = {}
    search_dirs = [Path("/Applications"), Path.home() / "Applications"]
    for d in search_dirs:
        if not d.exists():
            continue
        for app in d.glob("*.app"):
            apps[_normalize(app.stem)] = str(app)
    return apps


def _scan_windows() -> dict[str, str]:
    apps: dict[str, str] = {}
    # Locais comuns de atalhos/instalações
    program_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    for base in program_dirs:
        base_path = Path(base)
        if not base_path.exists():
            continue
        for exe in base_path.rglob("*.exe"):
            apps.setdefault(_normalize(exe.stem), str(exe))
    return apps


def scan_installed_apps() -> dict[str, str]:
    """Detecta o SO e roda o scanner apropriado."""
    system = platform.system()
    if system == "Linux":
        return _scan_linux()
    if system == "Darwin":
        return _scan_macos()
    if system == "Windows":
        return _scan_windows()
    raise RuntimeError(f"Sistema operacional não suportado: {system}")


def build_index(force: bool = False) -> dict[str, str]:
    """Carrega o índice do disco, ou reconstrói se não existir / force=True."""
    if INDEX_FILE.exists() and not force:
        return json.loads(INDEX_FILE.read_text())

    index = scan_installed_apps()
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    return index


def resolve_app(name: str, index: dict[str, str] | None = None) -> str | None:
    """Tenta achar o executável de um app pelo nome (com aprendizado manual)."""
    index = index if index is not None else build_index()
    key = _normalize(name)

    if key in index:
        return index[key]

    # match parcial: "vscode" dentro de "visual studio code"
    for k, v in index.items():
        if key in k or k in key:
            return v

    # fallback: tenta achar no PATH diretamente (ex: comandos simples)
    return shutil.which(name)


def learn_app(name: str, executable_path: str) -> None:
    """Ensina manualmente onde fica um app que não foi encontrado (abordagem 3)."""
    index = build_index()
    index[_normalize(name)] = executable_path
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))
