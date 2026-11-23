"""SQLite repository for creative projects and artifact workflows."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from app.adapters.persistence.database import Database


class CreativeProjectRepository:
    """Persist creative projects, workflow runs, and structured artifacts."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _project_payload(row) -> dict[str, object]:
        return {
            "id": row["id"],
            "sessionId": row["session_id"],
            "title": row["title"],
            "domain": row["domain"],
            "status": row["status"],
            "workspacePath": row["workspace_path"],
            "spec": json.loads(row["spec_json"] or "{}"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _workflow_payload(run, steps) -> dict[str, object]:
        return {
            "id": run["id"],
            "projectId": run["project_id"],
            "workflowKey": run["workflow_key"],
            "status": run["status"],
            "currentStepKey": run["current_step_key"],
            "steps": [
                {
                    "id": step["id"],
                    "stepKey": step["step_key"],
                    "title": step["title"],
                    "status": step["status"],
                    "sortOrder": step["sort_order"],
                    "artifactKind": step["artifact_kind"],
                    "artifactPath": step["artifact_path"],
                    "summary": step["summary"],
                }
                for step in steps
            ],
        }

    def create_project(
        self,
        *,
        title: str,
        domain: str,
        workspace_path: str,
        spec: dict[str, object],
        session_id: str | None = None,
    ) -> dict[str, object]:
        project_id = str(uuid.uuid4())
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO creative_projects
                    (id, session_id, title, domain, workspace_path, spec_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    session_id,
                    title,
                    domain,
                    workspace_path,
                    json.dumps(spec, ensure_ascii=False),
                ),
            )
            connection.execute(
                """
                INSERT INTO project_threads (id, project_id, role)
                VALUES (?, ?, 'main_director')
                """,
                (str(uuid.uuid4()), project_id),
            )
        project = self.get_project(project_id)
        if not project:
            raise RuntimeError("creative project was not created")
        return project

    def list_projects(self) -> list[dict[str, object]]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM creative_projects
                ORDER BY updated_at DESC, rowid DESC
                """
            ).fetchall()
        return [self._project_payload(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM creative_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._project_payload(row) if row else None

    def attach_thread(self, project_id: str, codex_thread_id: str) -> None:
        """Persist the Codex thread used by the project's main director."""

        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE project_threads
                SET codex_thread_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND role = 'main_director'
                """,
                (codex_thread_id, project_id),
            )

    def get_thread(self, project_id: str) -> str | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT codex_thread_id
                FROM project_threads
                WHERE project_id = ? AND role = 'main_director'
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return (
            str(row["codex_thread_id"])
            if row and row["codex_thread_id"]
            else None
        )

    def update_artifact_status(
        self,
        project_id: str,
        canonical_path: str,
        status: str,
    ) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE creative_artifacts
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND canonical_path = ?
                """,
                (status, project_id, canonical_path),
            )
        return cursor.rowcount > 0

    def update_step_status(
        self,
        project_id: str,
        step_key: str,
        status: str,
    ) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_step_runs
                SET status = ?, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN ? = 'approved'
                        THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE workflow_run_id = (
                    SELECT id FROM workflow_runs
                    WHERE project_id = ?
                    ORDER BY created_at DESC, rowid DESC LIMIT 1
                ) AND step_key = ?
                """,
                (status, status, project_id, step_key),
            )
        return cursor.rowcount > 0

    def set_workflow_status(self, project_id: str, status: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE workflow_runs
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ?
                AND id = (
                    SELECT id FROM workflow_runs
                    WHERE project_id = ?
                    ORDER BY created_at DESC, rowid DESC LIMIT 1
                )
                """,
                (status, project_id, project_id),
            )

    def reconcile_workspace(self, project_id: str) -> dict[str, object]:
        """Import changed artifacts and advance the project workflow."""

        project = self.get_project(project_id)
        workflow = self.get_latest_workflow_for_project(project_id)
        if not project or not workflow:
            return {
                "projectId": project_id,
                "changedArtifacts": [],
                "currentStepKey": None,
            }
        root = Path(str(project["workspacePath"]))
        completed_steps: list[str] = []
        changed_artifacts: list[str] = []
        with self._database.transaction() as connection:
            for step in workflow["steps"]:
                relative = step.get("artifactPath")
                if not relative:
                    continue
                file_path = root / str(relative)
                if not file_path.is_file():
                    continue
                content = file_path.read_text(encoding="utf-8")
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                artifact = connection.execute(
                    """
                    SELECT * FROM creative_artifacts
                    WHERE project_id = ? AND canonical_path = ?
                    """,
                    (project_id, str(relative)),
                ).fetchone()
                if not artifact:
                    changed_artifacts.append(str(relative))
                    connection.execute(
                        """
                        INSERT INTO creative_artifacts
                            (id, project_id, workflow_step_run_id, kind, title,
                             canonical_path, current_version, status)
                        VALUES (?, ?, ?, ?, ?, ?, 1, 'draft')
                        """,
                        (
                            str(uuid.uuid4()),
                            project_id,
                            step["id"],
                            step.get("artifactKind") or "document",
                            step["title"],
                            str(relative),
                        ),
                    )
                    artifact = connection.execute(
                        """
                        SELECT * FROM creative_artifacts
                        WHERE project_id = ? AND canonical_path = ?
                        """,
                        (project_id, str(relative)),
                    ).fetchone()
                    connection.execute(
                        """
                        INSERT INTO creative_artifact_versions
                            (id, artifact_id, version, content_hash, file_path,
                             change_note)
                        VALUES (?, ?, 1, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            artifact["id"],
                            digest,
                            str(file_path),
                            "Codex 首次生成",
                        ),
                    )
                else:
                    latest = connection.execute(
                        """
                        SELECT content_hash, version
                        FROM creative_artifact_versions
                        WHERE artifact_id = ?
                        ORDER BY version DESC LIMIT 1
                        """,
                        (artifact["id"],),
                    ).fetchone()
                    if not latest or latest["content_hash"] != digest:
                        changed_artifacts.append(str(relative))
                        version = int(latest["version"]) + 1 if latest else 1
                        connection.execute(
                            """
                            INSERT INTO creative_artifact_versions
                                (id, artifact_id, version, content_hash, file_path,
                                 change_note)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(uuid.uuid4()),
                                artifact["id"],
                                version,
                                digest,
                                str(file_path),
                                "Codex 更新阶段产物",
                            ),
                        )
                        connection.execute(
                            """
                            UPDATE creative_artifacts
                            SET current_version = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (version, artifact["id"]),
                        )
                if content.strip() and "待" not in content[:120]:
                    completed_steps.append(str(step["stepKey"]))

            current = next(
                (
                    step["stepKey"]
                    for step in workflow["steps"]
                    if step["stepKey"] not in completed_steps
                ),
                None,
            )
            for step_key in completed_steps:
                connection.execute(
                    """
                    UPDATE workflow_step_runs
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE workflow_run_id = ? AND step_key = ?
                    """,
                    (workflow["id"], step_key),
                )
            connection.execute(
                """
                UPDATE workflow_runs
                SET current_step_key = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN ? IS NULL
                        THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = ?
                """,
                (
                    current,
                    "completed" if current is None else "running",
                    current,
                    workflow["id"],
                ),
            )
            connection.execute(
                """
                UPDATE creative_projects
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                ("completed" if current is None else "in_progress", project_id),
            )
        return {
            "projectId": project_id,
            "changedArtifacts": changed_artifacts,
            "completedSteps": completed_steps,
            "currentStepKey": current,
            "status": "completed" if current is None else "in_progress",
        }

    def create_workflow_run(
        self,
        *,
        project_id: str,
        workflow_key: str,
        steps: list[dict[str, object]],
    ) -> dict[str, object]:
        run_id = str(uuid.uuid4())
        current_step = str(steps[0]["stepKey"]) if steps else None
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO workflow_runs
                    (id, project_id, workflow_key, status, current_step_key)
                VALUES (?, ?, ?, 'ready', ?)
                """,
                (run_id, project_id, workflow_key, current_step),
            )
            for index, step in enumerate(steps):
                connection.execute(
                    """
                    INSERT INTO workflow_step_runs
                        (id, workflow_run_id, step_key, title, sort_order,
                         artifact_kind, artifact_path, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        step["stepKey"],
                        step["title"],
                        index + 1,
                        step.get("artifactKind"),
                        step.get("artifactPath"),
                        step.get("summary", ""),
                    ),
                )
        workflow = self.get_workflow_run(run_id)
        if not workflow:
            raise RuntimeError("workflow run was not created")
        return workflow

    def get_workflow_run(self, run_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            run = connection.execute(
                "SELECT * FROM workflow_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if not run:
                return None
            steps = connection.execute(
                """
                SELECT * FROM workflow_step_runs
                WHERE workflow_run_id = ?
                ORDER BY sort_order ASC
                """,
                (run_id,),
            ).fetchall()
        return self._workflow_payload(run, steps)

    def get_latest_workflow_for_project(
        self,
        project_id: str,
    ) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            run = connection.execute(
                """
                SELECT * FROM workflow_runs
                WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if not run:
                return None
            steps = connection.execute(
                """
                SELECT * FROM workflow_step_runs
                WHERE workflow_run_id = ?
                ORDER BY sort_order ASC
                """,
                (run["id"],),
            ).fetchall()
        return self._workflow_payload(run, steps)

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
    ) -> dict[str, object]:
        artifact_id = str(uuid.uuid4())
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO creative_artifacts
                    (id, project_id, workflow_step_run_id, kind, title,
                     canonical_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    project_id,
                    workflow_step_run_id,
                    kind,
                    title,
                    canonical_path,
                ),
            )
            connection.execute(
                """
                INSERT INTO creative_artifact_versions
                    (id, artifact_id, version, content_hash, file_path,
                     change_note)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    artifact_id,
                    content_hash,
                    file_path,
                    change_note,
                ),
            )
            row = connection.execute(
                "SELECT * FROM creative_artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
        return dict(row)
