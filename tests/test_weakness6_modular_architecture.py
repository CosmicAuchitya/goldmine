from pathlib import Path

from autonomous_engine.build_web_client import (
    FRONTEND_SRC_DIR,
    WEB_CLIENT_PATH,
    check_frontend_parity,
)
from autonomous_engine.pulse_payload_builder import _extract_executive_pulse as builder_pulse
from autonomous_engine.api_server import _extract_executive_pulse as api_pulse


def test_w6_frontend_modular_sources_compile_byte_exact_and_pass_node_check():
    expected_modules = [
        "shell_head.html",
        "styles.css",
        "body.html",
        "js/01_i18n_and_state.js",
        "js/02_upload_and_pulse.js",
        "js/03_leaks_qa_and_workspace.js",
        "shell_foot.html",
    ]
    for rel in expected_modules:
        p = FRONTEND_SRC_DIR / rel
        assert p.exists() and p.stat().st_size > 0, f"Missing frontend source module: {p}"

    ok, msg = check_frontend_parity(FRONTEND_SRC_DIR, WEB_CLIENT_PATH)
    assert ok is True, msg


def test_w6_api_server_modularized_pulse_builder_preserves_contract():
    assert api_pulse is builder_pulse
    api_lines = len(Path("autonomous_engine/api_server.py").read_text(encoding="utf-8").splitlines())
    builder_lines = len(Path("autonomous_engine/pulse_payload_builder.py").read_text(encoding="utf-8").splitlines())
    assert builder_lines >= 600
    assert api_lines < 3600, f"Expected api_server.py trimmed below 3600 lines, got {api_lines}"
