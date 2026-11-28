"""
=============================================================================
DATAX-RAY WORKSTREAM 6 — ZERO-CDN MODULAR FRONTEND COMPILER (`build_web_client`)
=============================================================================
Solves Weakness #6 (10,500-Line `web_client.html` Monolith Maintenance Risk)
WITHOUT introducing Node/Webpack/CDN runtime dependencies:
  - Source of truth lives cleanly split under `autonomous_engine/frontend_src/`:
      1. `shell_head.html`                 (HTML <head> & metadata)
      2. `styles.css`                      (Pure CSS design system & responsive media rules)
      3. `body.html`                       (Pure HTML semantic layout & modals)
      4. `js/01_i18n_and_state.js`         (43-language i18n, appState, theme & auth helpers)
      5. `js/02_upload_and_pulse.js`       (Upload, Intent Handshake, Pulse & Growth/Stock UI)
      6. `js/03_leaks_qa_and_workspace.js` (Ranked Leaks, 200-Q, Ask AI, Billing, Connectors)
      7. `shell_foot.html`                 (Closing tags)
  - `--extract`: Splits `web_client.html` into modular `frontend_src/` files.
  - `--build`:   Compiles `frontend_src/` into zero-CDN `web_client.html` + `node --check`.
  - `--check`:   CI parity gate ensuring `frontend_src/` matches `web_client.html` byte-for-byte.
=============================================================================
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Tuple


ENGINE_DIR = Path(__file__).resolve().parent
WEB_CLIENT_PATH = ENGINE_DIR / "web_client.html"
FRONTEND_SRC_DIR = ENGINE_DIR / "frontend_src"


def _find_line_index(lines: list[str], predicate, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if predicate(lines[i]):
            return i
    raise ValueError("Expected structural boundary not found in web_client.html")


def extract_frontend_sources(
    html_path: Path = WEB_CLIENT_PATH,
    src_dir: Path = FRONTEND_SRC_DIR,
) -> Dict[str, int]:
    """Splits monolithic `web_client.html` into clean modular CSS/HTML/JS source files."""
    raw_text = html_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines(keepends=True)

    style_open = _find_line_index(lines, lambda l: l.strip() == "<style>")
    style_close = _find_line_index(lines, lambda l: l.strip() == "</style>", start=style_open + 1)
    script_open = _find_line_index(lines, lambda l: l.strip() == "<script>", start=style_close + 1)
    # Use the LAST top-level </script> tag (ignores any nested template literal strings)
    script_close = max(i for i, l in enumerate(lines) if l.strip() == "</script>")

    js_split_1 = _find_line_index(
        lines,
        lambda l: "function handleFileSelection(" in l,
        start=script_open + 1,
    )
    js_split_2 = _find_line_index(
        lines,
        lambda l: "async function loadAndRenderRankedLeaks(" in l,
        start=js_split_1 + 1,
    )

    parts = {
        "shell_head.html": "".join(lines[: style_open + 1]),
        "styles.css": "".join(lines[style_open + 1 : style_close]),
        "body.html": "".join(lines[style_close : script_open + 1]),
        "js/01_i18n_and_state.js": "".join(lines[script_open + 1 : js_split_1]),
        "js/02_upload_and_pulse.js": "".join(lines[js_split_1 : js_split_2]),
        "js/03_leaks_qa_and_workspace.js": "".join(lines[js_split_2 : script_close]),
        "shell_foot.html": "".join(lines[script_close:]),
    }

    (src_dir / "js").mkdir(parents=True, exist_ok=True)
    line_counts: Dict[str, int] = {}
    for rel, content in parts.items():
        target = src_dir / rel
        target.write_text(content, encoding="utf-8", newline="")
        line_counts[rel] = len(content.splitlines())
    return line_counts


def assemble_web_client_html(src_dir: Path = FRONTEND_SRC_DIR) -> str:
    """Deterministically compiles modular `frontend_src/` files into self-contained zero-CDN HTML."""
    order = (
        "shell_head.html",
        "styles.css",
        "body.html",
        "js/01_i18n_and_state.js",
        "js/02_upload_and_pulse.js",
        "js/03_leaks_qa_and_workspace.js",
        "shell_foot.html",
    )
    chunks = []
    for rel in order:
        p = src_dir / rel
        if not p.exists():
            raise FileNotFoundError(f"Missing frontend source module: {p}")
        chunks.append(p.read_text(encoding="utf-8"))
    return "".join(chunks)


def syntax_check_compiled_js(src_dir: Path = FRONTEND_SRC_DIR) -> Tuple[bool, str]:
    """Runs `node --check` on the concatenated JS modules if Node.js is available."""
    node_bin = shutil.which("node")
    if not node_bin:
        return True, "node not installed; skipped JS syntax check"
    js_bundle = "".join(
        (src_dir / rel).read_text(encoding="utf-8")
        for rel in (
            "js/01_i18n_and_state.js",
            "js/02_upload_and_pulse.js",
            "js/03_leaks_qa_and_workspace.js",
        )
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
        tf.write(js_bundle)
        tmp_js = Path(tf.name)
    try:
        proc = subprocess.run([node_bin, "--check", str(tmp_js)], capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout).strip()
        return True, "node --check PASSED"
    finally:
        tmp_js.unlink(missing_ok=True)


def build_web_client(
    src_dir: Path = FRONTEND_SRC_DIR,
    out_path: Path = WEB_CLIENT_PATH,
) -> Dict[str, object]:
    ok_js, js_msg = syntax_check_compiled_js(src_dir)
    if not ok_js:
        raise RuntimeError(f"Frontend JS syntax error: {js_msg}")
    compiled = assemble_web_client_html(src_dir)
    out_path.write_text(compiled, encoding="utf-8", newline="")
    return {
        "built_path": str(out_path),
        "bytes": len(compiled.encode("utf-8")),
        "lines": len(compiled.splitlines()),
        "js_check": js_msg,
    }


def check_frontend_parity(
    src_dir: Path = FRONTEND_SRC_DIR,
    html_path: Path = WEB_CLIENT_PATH,
) -> Tuple[bool, str]:
    ok_js, js_msg = syntax_check_compiled_js(src_dir)
    if not ok_js:
        return False, f"JS syntax error: {js_msg}"
    compiled = assemble_web_client_html(src_dir)
    current = html_path.read_text(encoding="utf-8")
    if compiled != current:
        return False, "web_client.html is out of sync with frontend_src/. Run `python -m autonomous_engine.build_web_client --build`."
    return True, f"Byte-exact parity verified ({len(compiled.splitlines())} lines; {js_msg})"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DataX-Ray Zero-CDN Modular Frontend Compiler")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--extract", action="store_true", help="Extract web_client.html into frontend_src/ modules")
    group.add_argument("--build", action="store_true", help="Compile frontend_src/ into web_client.html")
    group.add_argument("--check", action="store_true", help="Verify byte-exact parity and JS syntax")
    args = parser.parse_args()

    if args.extract:
        counts = extract_frontend_sources()
        print("[+] Extracted modular frontend sources:", counts)
    elif args.build:
        info = build_web_client()
        print("[+] Built zero-CDN web_client.html:", info)
    elif args.check:
        ok, msg = check_frontend_parity()
        print(("[+] " if ok else "[-] ") + msg)
        raise SystemExit(0 if ok else 1)
