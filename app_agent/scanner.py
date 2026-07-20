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
import unicodedata
from pathlib import Path


INDEX_FILE = Path.home() / ".app_agent_index.json"


def _normalize(name: str) -> str:
    """
    Deixa o nome minúsculo, sem acentos e sem caracteres estranhos,
    para facilitar o match (ex: "Configurações" -> "configuracoes").
    """
    name = name.lower().strip()
    name = re.sub(r"\.(exe|desktop|app)$", "", name)
    # remove acentos (á->a, ç->c, ã->a...) em vez de apagar a letra inteira
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
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

            apps_normalized_pretty = _normalize(pretty_name)
            apps_normalized_stem = _normalize(f.stem)
            if apps_normalized_pretty:
                apps[apps_normalized_pretty] = exec_bin
            if apps_normalized_stem:
                apps[apps_normalized_stem] = exec_bin  # também indexa pelo slug do arquivo

    # 2) Executáveis soltos no PATH (fallback, cobre CLIs sem .desktop)
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(path_dir)
        if not p.exists():
            continue
        for exe in p.iterdir():
            if os.access(exe, os.X_OK) and exe.is_file():
                normalized = _normalize(exe.name)
                if normalized:  # ignora nomes tipo "[" que viram string vazia
                    apps.setdefault(normalized, str(exe))

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


MIN_TOKEN_LEN = 3      # match por palavra inteira (seguro)
MIN_SUBSTRING_LEN = 5   # match por substring cru (só como último recurso)

KNOWN_BROWSERS = ["google chrome", "chrome", "firefox", "vivaldi", "brave", "microsoft edge", "edge", "opera", "chromium"]


def resolve_app(name: str, index: dict[str, str] | None = None) -> str | None:
    """Tenta achar o executável de um app pelo nome (com aprendizado manual)."""
    index = index if index is not None else build_index()
    key = _normalize(name)

    if not key:
        return None

    if key in index:
        return index[key]

    # 1) match por palavra inteira: "code" bate com "visual studio code",
    # mas "cut" NÃO bate com "executavel" (que contém "cut" como substring
    # cru, mas não como palavra própria). Isso evita falsos positivos tipo
    # o app_agent confundir um path qualquer com o comando `cut` do shell.
    if len(key) >= MIN_TOKEN_LEN:
        key_tokens = set(key.split())
        best_match: tuple[int, str] | None = None
        for k, v in index.items():
            if len(k) < MIN_TOKEN_LEN:
                continue
            k_tokens = set(k.split())
            if key_tokens and k_tokens and (key_tokens <= k_tokens or k_tokens <= key_tokens):
                score = abs(len(k) - len(key))
                if best_match is None or score < best_match[0]:
                    best_match = (score, v)
        if best_match:
            return best_match[1]

    # 2) fallback: substring cru, só pra chaves mais longas/específicas
    # (reduz drasticamente a chance de uma palavra curta e comum "vazar"
    # de dentro de outra sem querer)
    if len(key) >= MIN_SUBSTRING_LEN:
        best_match = None
        for k, v in index.items():
            if len(k) < MIN_SUBSTRING_LEN:
                continue
            if key in k or k in key:
                score = abs(len(k) - len(key))
                if best_match is None or score < best_match[0]:
                    best_match = (score, v)
        if best_match:
            return best_match[1]

    # fallback: tenta achar no PATH diretamente (ex: comandos simples)
    return shutil.which(name)


def list_known_browsers(index: dict[str, str] | None = None) -> list[str]:
    """Lista quais navegadores conhecidos foram encontrados no índice atual."""
    index = index if index is not None else build_index()
    return [name for name in KNOWN_BROWSERS if resolve_app(name, index)]


def resolve_any_browser(index: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """Acha QUALQUER navegador instalado, na ordem de preferência de KNOWN_BROWSERS."""
    index = index if index is not None else build_index()
    for name in KNOWN_BROWSERS:
        path = resolve_app(name, index)
        if path:
            return path, name
    return None, None


def learn_app(name: str, executable_path: str) -> None:
    """Ensina manualmente onde fica um app que não foi encontrado (abordagem 3)."""
    index = build_index()
    index[_normalize(name)] = executable_path
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))