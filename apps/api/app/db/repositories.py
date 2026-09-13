"""Repository methods that isolate SQL from conversation business rules."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from app.db.database import Database
from app.models.conversation import Conversation, ConversationMessage, TurnRecord


class ConversationRepository:
    """Persist session metadata, turns, messages, and idempotent submissions."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _to_conversation(row) -> Conversation:
        return Conversation(
            id=row["id"],
            title=row["title"],
            thread_id=row["codex_thread_id"],
            status=row["status"],
        )

    @staticmethod
    def _to_message(row) -> ConversationMessage:
        return ConversationMessage(
            id=row["id"],
            session_id=row["session_id"],
            turn_id=row["turn_id"],
            role=row["role"],
            content=row["content"],
            status=row["status"],
            reasoning=row["reasoning_text"] or "",
            reasoning_tokens=row["reasoning_tokens"] or 0,
        )

    def list_conversations(self) -> list[Conversation]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, title, codex_thread_id, status
                FROM sessions
                ORDER BY updated_at DESC, rowid DESC
                """
            ).fetchall()
        return [self._to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, title, codex_thread_id, status
                FROM sessions
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return self._to_conversation(row) if row else None

    def create_conversation(self, title: str = "新的创意对话") -> Conversation:
        conversation = Conversation(id=str(uuid.uuid4()), title=title, thread_id=None)
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, title, codex_thread_id, status)
                VALUES (?, ?, NULL, 'idle')
                """,
                (conversation.id, conversation.title),
            )
            connection.execute(
                "INSERT OR IGNORE INTO conversations (id, title, thread) VALUES (?, ?, NULL)",
                (conversation.id, conversation.title),
            )
        return conversation

    def attach_thread(
        self, conversation_id: str, thread_id: str, title: str
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET codex_thread_id = ?, title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (thread_id, title, conversation_id),
            )
            connection.execute(
                "UPDATE conversations SET thread = ?, title = ? WHERE id = ?",
                (thread_id, title, conversation_id),
            )

    def list_messages(self, conversation_id: str) -> list[ConversationMessage]:
        """Return chronological local history for one session.

        This method deliberately does not call Codex. SQLite is the product source
        of truth for what the browser shows in the conversation detail view.
        """

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT
                    messages.id,
                    messages.session_id,
                    messages.turn_id,
                    messages.role,
                    messages.content,
                    messages.status,
                    turns.reasoning_text,
                    turns.reasoning_tokens
                FROM messages
                LEFT JOIN turns ON turns.id = messages.turn_id
                WHERE messages.session_id = ?
                ORDER BY messages.created_at ASC, messages.rowid ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [self._to_message(row) for row in rows]

    def create_turn_with_messages(
        self, conversation_id: str, client_message_id: str, user_content: str
    ) -> TurnRecord:
        """Create the local turn, user message, and assistant placeholder atomically."""

        turn = TurnRecord(
            id=str(uuid.uuid4()),
            user_message_id=client_message_id,
            assistant_message_id=str(uuid.uuid4()),
        )
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO turns (id, session_id, status)
                VALUES (?, ?, 'running')
                """,
                (turn.id, conversation_id),
            )
            connection.execute(
                """
                INSERT INTO messages (id, session_id, turn_id, role, content, status)
                VALUES (?, ?, ?, 'user', ?, 'done')
                """,
                (turn.user_message_id, conversation_id, turn.id, user_content),
            )
            connection.execute(
                """
                INSERT INTO messages (id, session_id, turn_id, role, content, status)
                VALUES (?, ?, ?, 'assistant', '', 'streaming')
                """,
                (turn.assistant_message_id, conversation_id, turn.id),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'running', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )
        return turn

    def create_generation_task(
        self,
        *,
        session_id: str,
        turn_id: str,
        user_id: str,
        provider_id: str,
        model_id: str,
        prompt: str,
        original_request: dict[str, object],
        normalized_request: dict[str, object],
        client_request_id: str,
        task_type: str = "text",
        status: str = "running",
    ) -> str:
        """Create the canonical audit record before an external request is sent."""

        task_id = str(uuid.uuid4())
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO generation_tasks
                    (id, request_id, session_id, turn_id, user_id, provider_id, model_id,
                    task_type, prompt, original_request_json, normalized_request_json,
                     status, client_request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task_id,
                    session_id,
                    turn_id,
                    user_id,
                    provider_id,
                    model_id,
                    task_type,
                    prompt,
                    json.dumps(original_request, ensure_ascii=False),
                    json.dumps(normalized_request, ensure_ascii=False),
                    status,
                    client_request_id,
                ),
            )
        return task_id

    def update_generation_task_status(
        self,
        task_id: str,
        *,
        status: str,
        progress: int | None = None,
        provider_task_id: str | None = None,
        response: dict[str, object] | None = None,
        error_code: str | None = None,
        error: str | None = None,
        completed: bool = False,
    ) -> None:
        """Update a task and append an auditable state transition event."""

        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET status = ?, progress = COALESCE(?, progress),
                    provider_task_id = COALESCE(?, provider_task_id),
                    provider_response_json = COALESCE(?, provider_response_json),
                    error_code = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = ?
                """,
                (
                    status,
                    progress,
                    provider_task_id,
                    json.dumps(response, ensure_ascii=False) if response is not None else None,
                    error_code,
                    error,
                    int(completed),
                    task_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    status,
                    json.dumps(
                        {"progress": progress, "error": error}, ensure_ascii=False
                    ),
                ),
            )

    def create_asset(
        self,
        *,
        session_id: str | None,
        task_id: str,
        asset_type: str,
        source: str,
        local_path: str | None,
        remote_url: str | None,
        mime_type: str | None,
        size: int | None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        asset_id = str(uuid.uuid4())
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO assets
                    (id, session_id, task_id, type, source, local_path, remote_url,
                     mime_type, size, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    session_id,
                    task_id,
                    asset_type,
                    source,
                    local_path,
                    remote_url,
                    mime_type,
                    size,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return asset_id

    def set_generation_task_assets(self, task_id: str, asset_ids: list[str]) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET result_asset_ids_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(asset_ids, ensure_ascii=False), task_id),
            )

    def get_generation_task(self, task_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM generation_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in (
            "original_request_json",
            "normalized_request_json",
            "provider_request_json",
            "provider_response_json",
            "result_asset_ids_json",
        ):
            raw = result.get(key)
            fallback = "[]" if "asset" in key else "{}"
            result[key.removesuffix("_json")] = json.loads(raw or fallback)
        return result

    def get_asset(self, asset_id: str) -> dict[str, object] | None:
        with self._database.transaction() as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    def update_generation_task_request(
        self, task_id: str, provider_request: dict[str, object]
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET provider_request_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(provider_request, ensure_ascii=False), task_id),
            )

    def finish_generation_task(
        self,
        task_id: str,
        *,
        status: str,
        response: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE generation_tasks
                SET status = ?, provider_response_json = ?, error_message = ?,
                    updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, json.dumps(response or {}, ensure_ascii=False), error, task_id),
            )

    def set_codex_turn(self, local_turn_id: str, codex_turn_id: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET codex_turn_id = ? WHERE id = ?",
                (codex_turn_id, local_turn_id),
            )

    def append_assistant_content(self, message_id: str, delta: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = content || ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (delta, message_id),
            )

    def replace_assistant_content(self, message_id: str, content: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (content, message_id),
            )

    def append_reasoning(self, turn_id: str, delta: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET reasoning_text = reasoning_text || ? WHERE id = ?",
                (delta, turn_id),
            )

    def replace_reasoning(self, turn_id: str, text: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET reasoning_text = ? WHERE id = ?",
                (text, turn_id),
            )

    def update_reasoning_tokens(self, turn_id: str, tokens: int) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE turns SET reasoning_tokens = ? WHERE id = ?",
                (tokens, turn_id),
            )

    def finish_turn(
        self,
        conversation_id: str,
        turn_id: str,
        assistant_message_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        message_status = "error" if error else "done"
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE turns
                SET status = ?, error = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error, turn_id),
            )
            connection.execute(
                """
                UPDATE messages
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (message_status, assistant_message_id),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'idle', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )

    def submission_exists(self, client_message_id: str) -> bool:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT 1 FROM submissions WHERE id = ?", (client_message_id,)
            ).fetchone()
        return row is not None

    def start_submission(self, client_message_id: str, conversation_id: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO submissions (id, conversation, session_id, status)
                VALUES (?, ?, ?, ?)
                """,
                (client_message_id, conversation_id, conversation_id, "started"),
            )

    def finish_submission(self, client_message_id: str) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE submissions
                SET status = 'finished', finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (client_message_id,),
            )


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
                "SELECT * FROM creative_projects WHERE id = ?", (project_id,)
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
        return str(row["codex_thread_id"]) if row and row["codex_thread_id"] else None

    def update_artifact_status(
        self, project_id: str, canonical_path: str, status: str
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
        self, project_id: str, step_key: str, status: str
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
        """Import changed artifact files and advance the automatic workflow.

        The workspace is the model's writable surface, while SQLite remains the
        business source of truth. This bridge makes both views converge after a
        completed Codex turn.
        """

        project = self.get_project(project_id)
        workflow = self.get_latest_workflow_for_project(project_id)
        if not project or not workflow:
            return {"projectId": project_id, "changedArtifacts": [], "currentStepKey": None}
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
                            str(uuid.uuid4()), project_id, step["id"],
                            step.get("artifactKind") or "document",
                            step["title"], str(relative),
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
                            str(uuid.uuid4()), artifact["id"], digest,
                            str(file_path), "Codex 首次生成",
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
                                str(uuid.uuid4()), artifact["id"], version, digest,
                                str(file_path), "Codex 更新阶段产物",
                            ),
                        )
                        connection.execute(
                            """
                            UPDATE creative_artifacts
                            SET current_version = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (version, artifact["id"]),
                        )
                if content.strip() and "待" not in content[:120]:
                    completed_steps.append(str(step["stepKey"]))

            current = next(
                (
                    step["stepKey"] for step in workflow["steps"]
                    if step["stepKey"] not in completed_steps
                ),
                None,
            )
            for step_key in completed_steps:
                connection.execute(
                    """
                    UPDATE workflow_step_runs
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE workflow_run_id = ? AND step_key = ?
                    """,
                    (workflow["id"], step_key),
                )
            connection.execute(
                """
                UPDATE workflow_runs
                SET current_step_key = ?, status = ?, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN ? IS NULL THEN CURRENT_TIMESTAMP ELSE completed_at END
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
                "SELECT * FROM workflow_runs WHERE id = ?", (run_id,)
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
        self, project_id: str
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
                    (id, project_id, workflow_step_run_id, kind, title, canonical_path)
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
                    (id, artifact_id, version, content_hash, file_path, change_note)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (str(uuid.uuid4()), artifact_id, content_hash, file_path, change_note),
            )
            row = connection.execute(
                "SELECT * FROM creative_artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
        return dict(row)
