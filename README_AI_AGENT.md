# AI-LAB Autonomous Coding Agent (Antigravity Engine)

A local-first, Windows desktop application and autonomous software engineering agent running entirely on top of local Ollama models (such as `qwen2.5-coder:1.5b` and `qwen2.5-coder:latest`).

---

## 🏛️ Architecture Overview

The system is built with a modular, decoupled architecture:

```
[PySide6 Desktop Application] <---> [AgentWorker QThread]
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     [AutonomousAgentEngine]                             [OllamaClient]
     ├── State Machine (10 States)                       ├── Discovery (/api/tags)
     ├── Evidence-Based Debugger                         ├── Structured JSON Extractor
     └── Self-Healing Recovery Loop                      └── Streaming Telemetry
                  │
  ┌───────────────┼───────────────────────────────┐
  ▼               ▼                               ▼
[ToolRegistry]  [SecurityPolicy & Approvals]   [SQLiteMemory]
├── list_files  ├── Path Traversal Jail        ├── Tasks & Plan Steps
├── read_file   ├── Sensitive File Masking     ├── Checkpoints
├── search_code ├── Command Allowlist          ├── Tool Execution Logs
├── write_file  └── Human Approval Gate        └── Resumption State
├── apply_patch
├── git_status & git_diff
└── run_tests & run_build
```

---

## 💻 Desktop Application Features

1. **Chat and Task Panel**:
   - Natural language objective input.
   - Dynamic Model Selector (`qwen2.5-coder:1.5b`, `qwen2.5-coder:latest`, etc.).
   - Live Task State Indicator (`INVESTIGATING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `RECOVERING`, `COMPLETED`, etc.).
   - Interactive Plan Checklist showing real-time step status.
   - Internal reasoning stream with tool execution summaries.

2. **Project Explorer**:
   - Workspace directory browser with folder picker.
   - Tree view of workspace files.
   - Integrated source code regex/substring search.
   - Double-click to inspect code in the viewer.

3. **Code and Diff Viewer**:
   - Monospace source code editor with line numbers.
   - Colorized Git / Patch Diff viewer (`+` green, `-` red).

4. **Execution Console**:
   - Live streaming of executed terminal commands.
   - Stdout and Stderr separation with exit code and elapsed time tracking.
   - Mid-flight process cancellation button.

5. **Approval Center (Human-in-the-Loop)**:
   - Evaluates actions and assigns risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - Modal approval dialog for high-risk actions (modifications, test execution, external scripts).
   - Guarantees actions are never executed silently if rejected or cancelled.

6. **Task History**:
   - Persistent SQLite storage for all past tasks and checkpoints.
   - "Resume Selected Task" capability to restore context and resume interrupted work.

---

## 🚀 How to Launch the Application

### Option 1: One-Click Windows Launcher
Double-click:
```cmd
launch_agent.bat
```

### Option 2: Command Line (Desktop GUI)
```powershell
py -3.12 main.py .
```

### Option 3: Headless CLI (for Automation and Scripted Workflows)
```powershell
py -3.12 cli.py --task "Diagnose and fix the test failure in test_inventory.py" --workspace . --auto-approve safe
```

---

## 🧪 Evaluation & Verification Suite

Run the full automated test suite (24 tests covering security jail, file tools, approval gates, command timeouts, memory persistence, and seeded bug fixing):

```powershell
py -3.12 run_evaluations.py
```

### Measured Benchmark Results
- **Total Tests**: 24
- **Passed**: 24
- **Failures / Errors**: 0
- **Pass Rate**: 100.0%
- **Execution Time**: 7.69 seconds
- **Local Model Connectivity**: Verified with Ollama Qwen2.5-Coder models.
- **Seeded Bug Fixing**: Verified end-to-end against real Python subprocess execution.
