"""
================================================================================
ENTERPRISE COMMON UTILITIES, AST SECURITY GATE & SANITIZATION HELPERS
================================================================================
Houses shared text-processing, AST security auditing, subprocess environment
scrubbing, SQL identifier quoting, and workspace path-traversal guards used
across multiple pipeline stages.
================================================================================
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


FORBIDDEN_ETL_IMPORTS: Set[str] = {
    "subprocess", "socket", "ssl", "http", "urllib", "urllib3", "requests",
    "httpx", "aiohttp", "websocket", "websockets", "ftplib", "smtplib",
    "poplib", "imaplib", "telnetlib", "xmlrpc", "ctypes", "cffi", "winreg",
    "msvcrt", "pty", "tty", "termios", "webbrowser", "pickle", "_pickle",
    "cPickle", "marshal", "shelve", "dill", "cloudpickle", "importlib",
    "builtins", "code", "codeop", "runpy", "dotenv", "paramiko", "fabric",
    "shutil", "posix", "nt",
}

FORBIDDEN_BUILTIN_CALLS: Set[str] = {
    "eval", "exec", "compile", "__import__", "breakpoint", "input",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
}

FORBIDDEN_OS_METHODS: Set[str] = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "kill",
    "putenv", "unsetenv", "chmod", "chown", "chroot", "fork", "forkpty",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve",
    "spawnvp", "spawnvpe", "execl", "execle", "execlp", "execlpe",
    "execv", "execve", "execvp", "execvpe", "startfile",
}

FORBIDDEN_UNCONDITIONAL_OS_ATTRS: Set[str] = {
    "system", "popen", "startfile", "fork", "forkpty", "chroot",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve",
    "spawnvp", "spawnvpe", "execl", "execle", "execlp", "execlpe",
    "execv", "execve", "execvp", "execvpe",
}

FORBIDDEN_PANDAS_METHODS: Set[str] = {
    "read_pickle", "to_pickle",
}

FORBIDDEN_DESTRUCTIVE_METHODS: Set[str] = {
    "rmtree", "unlink", "rmdir", "move", "copyfile", "copy2", "copytree",
}

FORBIDDEN_DUNDER_ATTRS: Set[str] = {
    "__subclasses__", "__globals__", "__builtins__", "__code__", "__closure__",
}

SENSITIVE_ENV_SUBSTRINGS = (
    "API_KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL",
    "PRIVATE_KEY", "ACCESS_KEY", "AUTH", "KAGGLE_KEY", "GEMINI",
    "OPENROUTER", "OPENAI", "ANTHROPIC", "AWS_SECRET", "AZURE_CLIENT",
)


def extract_python_code_robust(raw_text: str) -> str:
    """
    Extracts raw Python code safely even if model includes conversational preamble
    or markdown code fences (```python ... ```).
    """
    text = str(raw_text or "").strip()
    match = re.search(r'```(?:python)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def validate_etl_ast_security(code: str) -> List[str]:
    """
    Static AST Security Gate executed BEFORE running any LLM-generated ETL code.
    Blocks network access, subprocess spawning, dynamic eval/exec, destructive
    filesystem deletions, aliased OS/pickle bypasses, and .env credential reads.
    Returns a list of violation descriptions (empty list == safe to execute).
    """
    violations: List[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as se:
        return [f"SyntaxError during AST security scan: {se}"]

    # Pass 1: Track module aliases and direct symbol imports to defeat alias bypasses
    # (e.g. `import os as o; o.system(...)`, `from os import system`, `import pandas as p; p.read_pickle(...)`)
    os_aliases: Set[str] = {"os"}
    pandas_aliases: Set[str] = {"pd", "pandas"}
    direct_forbidden_symbols: Dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                bound_name = alias.asname or root_mod
                if root_mod in FORBIDDEN_ETL_IMPORTS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden module import '{alias.name}' blocked by AST Security Gate."
                    )
                elif root_mod == "os":
                    os_aliases.add(bound_name)
                elif root_mod == "pandas":
                    pandas_aliases.add(bound_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in FORBIDDEN_ETL_IMPORTS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden from-import '{node.module}' blocked by AST Security Gate."
                    )
                elif root_mod == "os":
                    for alias in node.names:
                        if alias.name == "*":
                            violations.append(
                                f"Line {node.lineno}: Wildcard 'from os import *' blocked by AST Security Gate."
                            )
                        elif alias.name in FORBIDDEN_OS_METHODS:
                            bound_name = alias.asname or alias.name
                            direct_forbidden_symbols[bound_name] = f"os.{alias.name}"
                            violations.append(
                                f"Line {node.lineno}: Forbidden OS symbol import 'from os import {alias.name}' blocked by AST Security Gate."
                            )
                elif root_mod == "pandas":
                    for alias in node.names:
                        if alias.name in FORBIDDEN_PANDAS_METHODS:
                            bound_name = alias.asname or alias.name
                            direct_forbidden_symbols[bound_name] = f"pandas.{alias.name}"
                            violations.append(
                                f"Line {node.lineno}: Forbidden unsafe deserialization import 'from pandas import {alias.name}' blocked by AST Security Gate."
                            )

    # Pass 2: Audit calls, attributes, runtime symbols, and .env paths
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in FORBIDDEN_BUILTIN_CALLS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden builtin call '{func.id}()' blocked by AST Security Gate."
                    )
                elif func.id in direct_forbidden_symbols:
                    violations.append(
                        f"Line {node.lineno}: Forbidden imported call '{func.id}()' ({direct_forbidden_symbols[func.id]}) blocked by AST Security Gate."
                    )
            elif isinstance(func, ast.Attribute):
                attr = func.attr
                if attr in FORBIDDEN_DESTRUCTIVE_METHODS:
                    violations.append(
                        f"Line {node.lineno}: Destructive filesystem call '.{attr}()' blocked by AST Security Gate."
                    )
                elif attr in FORBIDDEN_PANDAS_METHODS:
                    violations.append(
                        f"Line {node.lineno}: Unsafe pickle call '.{attr}()' blocked by AST Security Gate."
                    )
                elif attr in FORBIDDEN_UNCONDITIONAL_OS_ATTRS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden OS execution call '.{attr}()' blocked by AST Security Gate."
                    )
                elif isinstance(func.value, ast.Name) and func.value.id in os_aliases and attr in FORBIDDEN_OS_METHODS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden OS call '{func.value.id}.{attr}()' blocked by AST Security Gate."
                    )
                elif isinstance(func.value, ast.Name) and func.value.id in pandas_aliases and attr in FORBIDDEN_PANDAS_METHODS:
                    violations.append(
                        f"Line {node.lineno}: Unsafe deserialization '{func.value.id}.{attr}()' blocked by AST Security Gate."
                    )

        # 3. Block dunder sandbox-escape attributes & __builtins__ introspection
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_DUNDER_ATTRS:
            violations.append(
                f"Line {node.lineno}: Sandbox-escape attribute '{node.attr}' blocked by AST Security Gate."
            )
        elif isinstance(node, ast.Name) and node.id in {"__builtins__", "__loader__", "__spec__"}:
            violations.append(
                f"Line {node.lineno}: Restricted runtime symbol '{node.id}' blocked by AST Security Gate."
            )

        # 4. Block direct .env secret file access inside ETL scripts
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            val_low = node.value.strip().lower()
            if val_low == ".env" or val_low.endswith(("/.env", "\\.env")):
                violations.append(
                    f"Line {node.lineno}: Direct access to '.env' credential file is forbidden inside ETL scripts."
                )

    return violations


def build_sanitized_subprocess_env(extra_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Constructs a least-privilege environment dictionary for child ETL subprocesses,
    stripping all API keys, cloud tokens, and credentials from os.environ.
    """
    clean_env: Dict[str, str] = {}
    for k, v in os.environ.items():
        k_up = k.upper()
        if any(secret_tok in k_up for secret_tok in SENSITIVE_ENV_SUBSTRINGS):
            continue
        clean_env[k] = v

    clean_env["PYTHONIOENCODING"] = "utf-8"
    clean_env["PYTHONUTF8"] = "1"
    if extra_env:
        clean_env.update(extra_env)
    return clean_env


def sanitize_untrusted_metadata_token(val: str, max_len: int = 120) -> str:
    """
    Neutralizes control characters, newlines, markdown code-fence breakouts,
    and prompt-delimiter injections inside untrusted table/column/sheet names.
    """
    s = str(val or "")
    # Remove ASCII control characters and normalize whitespace to single space
    s = re.sub(r'[\x00-\x1f\x7f]+', ' ', s)
    # Remove prompt-boundary / code-fence breakout sequences
    s = s.replace("```", "").replace("<|", "").replace("|>", "")
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def quote_sql_ident(ident: str) -> str:
    """
    Safely quotes a SQL column/table identifier by doubling internal double quotes,
    preventing SQL identifier injection and reserved-keyword syntax errors.
    """
    clean = str(ident or "").replace("\x00", "")
    escaped = clean.replace('"', '""')
    return f'"{escaped}"'


def resolve_safe_workspace_path(user_path: str, workspace_root: Optional[Path] = None) -> Path:
    """
    Resolves a user-supplied path and verifies it stays strictly within workspace_root,
    preventing directory traversal outside the repository boundary.
    """
    root = (workspace_root or Path.cwd()).resolve()
    raw_p = Path(str(user_path or "").strip())
    resolved = raw_p.resolve() if raw_p.is_absolute() else (root / raw_p).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(
            f"Security Violation: Path '{user_path}' resolves outside workspace root '{root}'."
        )
    return resolved
