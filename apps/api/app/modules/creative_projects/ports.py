"""Persistence ports required by creative-project use cases."""

from __future__ import annotations

from typing import Protocol


class CreativeProjectRepositoryPort(Protocol):
    def create_project(
        self,
        *,
        title: str,
        domain: str,
        workspace_path: str,
        spec: dict[str, object],
        session_id: str | None = None,
    ) -> dict[str, object]: ...

    def list_projects(self) -> list[dict[str, object]]: ...

    def get_project(self, project_id: str) -> dict[str, object] | None: ...

    def attach_thread(self, project_id: str, codex_thread_id: str) -> None: ...

    def get_thread(self, project_id: str) -> str | None: ...

    def update_artifact_status(
        self,
        project_id: str,
        canonical_path: str,
        status: str,
    ) -> bool: ...

    def update_step_status(
        self,
        project_id: str,
        step_key: str,
        status: str,
    ) -> bool: ...

    def set_workflow_status(self, project_id: str, status: str) -> None: ...

    def reconcile_workspace(self, project_id: str) -> dict[str, object]: ...

    def create_workflow_run(
        self,
        *,
        project_id: str,
        workflow_key: str,
        steps: list[dict[str, object]],
    ) -> dict[str, object]: ...

    def get_latest_workflow_for_project(
        self,
        project_id: str,
    ) -> dict[str, object] | None: ...

    def create_artifact(
        self,
        *,
        project_id: str,
        workflow_step_run_id: str | None,
        kind: str,
        title: str,
        canonical_path: str,
        content_hash: str,
        file_path: str,
        change_note: str,
    ) -> dict[str, object]: ...
