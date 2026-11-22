from pathlib import Path

from app.db.database import Database
from app.db.repositories import CreativeProjectRepository
from app.services.creative_project_service import CreativeProjectService


def test_create_novel_project_initializes_workspace(tmp_path: Path):
    database = Database(tmp_path / "creative.db")
    service = CreativeProjectService(
        CreativeProjectRepository(database), tmp_path / "workspaces"
    )

    project = service.create_novel_project(
        title="猫的六章小说",
        idea="一只猫想完成一次属于自己的冒险",
        target_words=6000,
        chapter_count=6,
    )

    workspace = Path(str(project["workspacePath"]))
    assert project["domain"] == "novel"
    assert project["spec"]["chapterCount"] == 6
    assert workspace.joinpath("AGENTS.md").is_file()
    assert workspace.joinpath("project.json").is_file()
    assert workspace.joinpath("canon/novel-bible.md").is_file()
    assert workspace.joinpath("structure/chapter-outline.md").is_file()
    assert workspace.joinpath("exports/novel.md").is_file()
    assert workspace.joinpath("exports/novel-project.md").is_file()
    assert "## 第一章" in workspace.joinpath("exports/novel.md").read_text(
        encoding="utf-8"
    )
    project_markdown = workspace.joinpath("exports/novel-project.md").read_text(
        encoding="utf-8"
    )
    assert "小说项目总览" in project_markdown
    assert "一、需求澄清" in project_markdown
    assert "二、小说设定集" in project_markdown
    assert "三、章节大纲" in project_markdown
    assert "五、小说正文" in project_markdown
    assert "一只猫想完成一次属于自己的冒险" in project_markdown
    for internal_path in (
        "state/creative-brief.md",
        "canon/novel-bible.md",
        "structure/chapter-outline.md",
        "structure/plot-beats.md",
        "exports/novel.md",
        "state/revision-report.md",
    ):
        assert internal_path not in project_markdown
    assert workspace.joinpath("state/workflow.json").is_file()
    assert workspace.joinpath("skills/novel-writing/SKILL.md").is_file()
    assert workspace.joinpath("knowledge/story-architecture.md").is_file()
    assert workspace.joinpath("schemas/novel-project.schema.json").is_file()
    assert project["workflow"]["workflowKey"] == "novel.default.v1"
    assert [step["stepKey"] for step in project["workflow"]["steps"]] == [
        "intake",
        "novel_bible",
        "chapter_outline",
        "plot_beats",
        "novel_draft",
        "revision_review",
    ]

    loaded = service.get_project(str(project["id"]))
    assert loaded is not None
    assert loaded["workflow"]["currentStepKey"] == "intake"
    database.close()


def test_novel_prompt_exposes_only_the_user_request(tmp_path: Path):
    database = Database(tmp_path / "creative.db")
    service = CreativeProjectService(
        CreativeProjectRepository(database), tmp_path / "workspaces"
    )
    project = service.create_novel_project(
        title="雨夜便利店",
        idea="一个便利店店员在雨夜遇到未来的自己",
    )

    prompt = service.build_novel_prompt(str(project["id"]))

    assert prompt == "一个便利店店员在雨夜遇到未来的自己"
    assert str(project["workspacePath"]) not in prompt
    assert "exports/novel.md" not in prompt
    database.close()


def test_screenplay_route_wrapper_creates_novel_project(tmp_path: Path):
    database = Database(tmp_path / "creative.db")
    service = CreativeProjectService(
        CreativeProjectRepository(database), tmp_path / "workspaces"
    )

    project = service.create_screenplay_project(
        title="兼容旧入口",
        idea="旧入口也应该走小说项目",
        target_minutes=3,
        episode_count=2,
    )

    assert project["domain"] == "novel"
    assert project["spec"]["chapterCount"] == 2
    assert project["spec"]["targetWords"] == 3000
    database.close()


def test_public_file_resolution_stays_inside_creative_workspace(tmp_path: Path):
    database = Database(tmp_path / "creative.db")
    service = CreativeProjectService(
        CreativeProjectRepository(database), tmp_path / "workspaces"
    )
    project = service.create_novel_project(
        title="安全查看",
        idea="验证浏览器可以查看创作文件",
    )
    artifact = Path(str(project["workspacePath"])) / "canon/novel-bible.md"

    assert service.resolve_public_file(str(artifact)) == artifact.resolve()
    assert (
        service.resolve_project_file(str(project["id"]), "canon/novel-bible.md")
        == artifact.resolve()
    )

    outside = tmp_path / "outside.md"
    outside.write_text("private", encoding="utf-8")
    try:
        service.resolve_public_file(str(outside))
    except ValueError as exc:
        assert "只能查看" in str(exc)
    else:
        raise AssertionError("outside file should not be public")
    database.close()
