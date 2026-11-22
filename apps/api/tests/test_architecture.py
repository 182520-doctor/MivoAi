"""Guard the DDD dependency direction without requiring an external linter."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
CONTEXT_ROOT = APP_ROOT / "contexts"
FORBIDDEN_INFRASTRUCTURE = (
    "fastapi",
    "httpx",
    "sqlite3",
    "starlette",
    "uvicorn",
)


def _source_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py"))


def test_context_application_does_not_import_context_infrastructure() -> None:
    violations: list[str] = []
    for path in _source_files(CONTEXT_ROOT):
        if path.name in {"application.py", "domain.py", "ports.py"}:
            source = path.read_text(encoding="utf-8")
            if "app.infrastructure" in source or "app.interfaces" in source:
                violations.append(str(path.relative_to(APP_ROOT)))
            if ".infrastructure." in source:
                violations.append(str(path.relative_to(APP_ROOT)))
            if path.name == "application.py" and ".schemas" in source:
                violations.append(
                    f"{path.relative_to(APP_ROOT)} imports an HTTP schema"
                )
    assert violations == []


def test_domain_and_ports_remain_framework_neutral() -> None:
    violations: list[str] = []
    for path in _source_files(CONTEXT_ROOT):
        if path.name not in {"domain.py", "ports.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        for dependency in FORBIDDEN_INFRASTRUCTURE:
            if f"import {dependency}" in source or f"from {dependency}" in source:
                violations.append(
                    f"{path.relative_to(APP_ROOT)} imports {dependency}"
                )
    assert violations == []


def test_contexts_do_not_import_another_context_repository() -> None:
    violations: list[str] = []
    for context_dir in CONTEXT_ROOT.iterdir():
        if not context_dir.is_dir():
            continue
        context_name = context_dir.name
        for path in _source_files(context_dir):
            source = path.read_text(encoding="utf-8")
            for other_dir in CONTEXT_ROOT.iterdir():
                if not other_dir.is_dir() or other_dir.name == context_name:
                    continue
                forbidden = (
                    f"app.contexts.{other_dir.name}.repository"
                )
                forbidden_infra = (
                    f"app.contexts.{other_dir.name}.infrastructure"
                )
                if forbidden in source or forbidden_infra in source:
                    violations.append(
                        f"{path.relative_to(APP_ROOT)} imports {other_dir.name} internals"
                    )
    assert violations == []
