"""Isolated FastAPI Router for Database Fortress Health & On-Demand Atomic Backups."""
from pathlib import Path
from typing import Any, Callable, Dict
from fastapi import APIRouter, Request


def build_system_router(
    *,
    workspace_root: Path,
    require_role: Callable,
) -> APIRouter:
    router = APIRouter(tags=["System & Database Fortress"])

    @router.get("/api/v1/system/db-health")
    def get_database_fortress_health(request: Request) -> Dict[str, Any]:
        """Admin-only live PRAGMA integrity_check & foreign-key audit across workspace SQLite DBs."""
        require_role(request, "admin")
        from ..db_adapter import DatabaseAdapter

        runs_dir = Path(workspace_root).resolve() / "runs"
        dbs = []
        if runs_dir.exists():
            seen = set()
            for pat in ("*.sqlite", "*.db"):
                for db_f in sorted(runs_dir.rglob(pat)):
                    if "backups" in db_f.parts or db_f.name.endswith(".bak"):
                        continue
                    res = db_f.resolve()
                    if res in seen:
                        continue
                    seen.add(res)
                    chk = DatabaseAdapter(res, database_url="").check_integrity()
                    dbs.append({
                        "db": str(res.relative_to(runs_dir)).replace("\\", "/"),
                        **chk,
                    })
        return {
            "status": "ok",
            "databases_checked": len(dbs),
            "all_healthy": all(d.get("healthy", False) for d in dbs),
            "databases": dbs,
        }

    @router.post("/api/v1/system/db-backup")
    def trigger_atomic_db_backup(request: Request) -> Dict[str, Any]:
        """Admin-only atomic WAL-safe online snapshot of all workspace SQLite databases."""
        require_role(request, "admin")
        from ..db_adapter import backup_all_workspace_databases
        return backup_all_workspace_databases(workspace_root, keep_last=10)

    return router
