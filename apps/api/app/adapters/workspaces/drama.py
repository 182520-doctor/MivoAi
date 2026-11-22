"""Create isolated filesystem workspaces for short-drama projects."""

from __future__ import annotations

from pathlib import Path


class DramaWorkspaceManager:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def ensure(self, project_id: str) -> Path:
        workspace = self._root / "projects" / project_id
        for folder in (
            "story_bible",
            "scripts",
            "breakdown",
            "episode_plans",
            "reviews",
            "assets",
            "keyframes",
            "nine_grids",
            "storyboards",
            "shots",
            "audio",
            "exports",
        ):
            (workspace / folder).mkdir(parents=True, exist_ok=True)
        readme = workspace / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Drama Project Workspace\n\n"
                "This directory is isolated to one short-drama project.\n",
                encoding="utf-8",
            )
        return workspace
