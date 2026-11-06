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
}

FORBIDDEN_BUILTIN_CALLS: Set[str] = {
    "eval", "exec", "compile", "__import__", "breakpoint", "input",
}

FORBIDDEN_OS_METHODS: Set[str] = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "kill",
    "putenv", "unsetenv", "chmod", "chown", "chroot", "fork", "forkpty",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve",
    "spawnvp", "spawnvpe", "execl", "execle", "execlp", "execlpe",
    "execv", "execve", "execvp", "execvpe", "startfile",
}

FORBIDDEN_DESTRUCTIVE_METHODS: Set[str] = {
    "rmtree", "unlink", "rmdir",
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
    filesystem deletions, and .env credential reads.
    Returns a list of violation descriptions (empty list == safe to execute).
    """
    violations: List[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as se:
        return [f"SyntaxError during AST security scan: {se}"]

    for node in ast.walk(tree):
        # 1. Check import statements
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in FORBIDDEN_ETL_IMPORTS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden module import '{alias.name}' blocked by AST Security Gate."
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in FORBIDDEN_ETL_IMPORTS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden from-import '{node.module}' blocked by AST Security Gate."
                    )

        # 2. Check dangerous function & method calls
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in FORBIDDEN_BUILTIN_CALLS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden builtin call '{func.id}()' blocked by AST Security Gate."
                    )
            elif isinstance(func, ast.Attribute):
                attr = func.attr
                if attr in FORBIDDEN_DESTRUCTIVE_METHODS:
                    violations.append(
                        f"Line {node.lineno}: Destructive filesystem call '.{attr}()' blocked by AST Security Gate."
                    )
                elif isinstance(func.value, ast.Name) and func.value.id == "os" and attr in FORBIDDEN_OS_METHODS:
                    violations.append(
                        f"Line {node.lineno}: Forbidden OS call 'os.{attr}()' blocked by AST Security Gate."
                    )
                elif isinstance(func.value, ast.Name) and func.value.id == "pd" and attr == "read_pickle":
                    violations.append(
                        f"Line {node.lineno}: Unsafe deserialization 'pd.read_pickle()' blocked by AST Security Gate."
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
