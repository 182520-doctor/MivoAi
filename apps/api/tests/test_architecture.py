"""Guard the domain-first module boundaries without an external linter."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
MODULES_ROOT = APP_ROOT / "modules"
DELIVERY_ROOT = APP_ROOT / "delivery"
ADAPTERS_ROOT = APP_ROOT / "adapters"
HTTP_ROUTES_ROOT = DELIVERY_ROOT / "http" / "routes"
SQLITE_ROOT = ADAPTERS_ROOT / "persistence" / "sqlite"

FORBIDDEN_FRAMEWORKS = (
    "fastapi",
    "httpx",
    "sqlite3",
    "starlette",
    "uvicorn",
)
REMOVED_LAYER_IMPORTS = (
    "app.api.",
    "app.contexts.",
    "app.db.",
    "app.infrastructure.",
    "app.interfaces.",
    "app.models.",
    "app.services.",
)
EXPECTED_HTTP_ROUTES = {
    "assets.py",
    "conversations.py",
    "creative_projects.py",
    "drama.py",
    "media_generation.py",
    "media_processing.py",
    "providers.py",
    "system.py",
    "workflows.py",
}


def _source_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py"))


def test_removed_layer_imports_are_not_reintroduced() -> None:
    violations: list[str] = []
    for path in _source_files(APP_ROOT):
        source = path.read_text(encoding="utf-8")
        for module in REMOVED_LAYER_IMPORTS:
            if module in source:
                violations.append(
                    f"{path.relative_to(APP_ROOT)} imports {module[:-1]}"
                )
    assert violations == []


def test_modules_do_not_depend_on_delivery_or_adapters() -> None:
    violations: list[str] = []
    for path in _source_files(MODULES_ROOT):
        if path.name not in {"application.py", "domain.py", "ports.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        if "app.adapters" in source or "app.delivery" in source:
            violations.append(str(path.relative_to(APP_ROOT)))
    assert violations == []


def test_delivery_does_not_depend_on_concrete_adapters() -> None:
    violations: list[str] = []
    for path in _source_files(DELIVERY_ROOT):
        source = path.read_text(encoding="utf-8")
        if "app.adapters" in source:
            violations.append(str(path.relative_to(APP_ROOT)))
    assert violations == []


def test_domain_and_ports_remain_framework_neutral() -> None:
    violations: list[str] = []
    for path in _source_files(MODULES_ROOT):
        if path.name not in {"domain.py", "ports.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        for dependency in FORBIDDEN_FRAMEWORKS:
            if (
                f"import {dependency}" in source
                or f"from {dependency}" in source
            ):
                violations.append(
                    f"{path.relative_to(APP_ROOT)} imports {dependency}"
                )
    assert violations == []


def test_http_routes_do_not_access_adapters_or_define_pydantic_models() -> None:
    violations: list[str] = []
    for path in _source_files(HTTP_ROUTES_ROOT):
        source = path.read_text(encoding="utf-8")
        if "app.adapters" in source or "repository" in source:
            violations.append(
                f"{path.relative_to(APP_ROOT)} accesses persistence"
            )
        if "BaseModel" in source:
            violations.append(
                f"{path.relative_to(APP_ROOT)} defines an HTTP schema"
            )
    assert violations == []


def test_all_business_modules_have_public_boundaries() -> None:
    violations: list[str] = []
    for module_dir in MODULES_ROOT.iterdir():
        if (
            not module_dir.is_dir()
            or module_dir.name == "__pycache__"
        ):
            continue
        for filename in ("__init__.py", "application.py", "ports.py"):
            if not (module_dir / filename).is_file():
                violations.append(f"{module_dir.name}: missing {filename}")
    assert violations == []


def test_http_delivery_is_centralized() -> None:
    actual = {
        path.name
        for path in HTTP_ROUTES_ROOT.iterdir()
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
    }
    assert actual == EXPECTED_HTTP_ROUTES


def test_http_and_agent_entrypoints_are_separate_from_domains() -> None:
    assert (DELIVERY_ROOT / "http" / "routes").is_dir()
    assert (DELIVERY_ROOT / "http" / "schemas").is_dir()
    assert (DELIVERY_ROOT / "agent" / "media_tools.py").is_file()


def test_repositories_live_in_the_persistence_adapter() -> None:
    expected = {
        "assets.py",
        "conversations.py",
        "creative_projects.py",
        "drama.py",
        "media_generation.py",
        "providers.py",
        "workflows.py",
    }
    actual = {
        path.name
        for path in SQLITE_ROOT.iterdir()
        if path.is_file()
        and path.suffix == ".py"
        and path.name != "__init__.py"
    }
    assert actual == expected
