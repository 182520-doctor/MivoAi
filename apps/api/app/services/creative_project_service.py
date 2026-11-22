"""Creative project orchestration for novel-oriented Agent workflows."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.db.repositories import CreativeProjectRepository

NOVEL_STEPS: tuple[dict[str, str], ...] = (
    {
        "stepKey": "intake",
        "title": "需求澄清",
        "artifactKind": "creative_brief",
        "artifactPath": "state/creative-brief.md",
        "summary": "确认题材、读者、篇幅、叙事视角、基调和必须保留的创意点。",
    },
    {
        "stepKey": "novel_bible",
        "title": "小说设定集",
        "artifactKind": "novel_bible",
        "artifactPath": "canon/novel-bible.md",
        "summary": "沉淀人物小传、世界观、关系网、叙事声音、主题和连续性事实。",
    },
    {
        "stepKey": "chapter_outline",
        "title": "章节大纲",
        "artifactKind": "chapter_outline",
        "artifactPath": "structure/chapter-outline.md",
        "summary": "把故事拆成章节目标、人物变化、冲突升级、悬念和情绪落点。",
    },
    {
        "stepKey": "plot_beats",
        "title": "情节节拍",
        "artifactKind": "plot_beats",
        "artifactPath": "structure/plot-beats.md",
        "summary": "拆出开端、铺垫、转折、高潮、余韵和每章关键描写段落。",
    },
    {
        "stepKey": "novel_draft",
        "title": "小说正文",
        "artifactKind": "novel_markdown",
        "artifactPath": "exports/novel.md",
        "summary": "输出像小说一样可直接阅读的 Markdown 正文，包含章节标题和完整叙述。",
    },
    {
        "stepKey": "revision_review",
        "title": "修订审查",
        "artifactKind": "quality_report",
        "artifactPath": "state/revision-report.md",
        "summary": "检查人物弧光、伏笔回收、叙事节奏、语言风格和设定冲突。",
    },
)


class CreativeProjectService:
    """Create and expose durable creative projects backed by a workspace folder."""

    def __init__(
        self, repository: CreativeProjectRepository, workspace_root: Path
    ) -> None:
        self._repository = repository
        self._workspace_root = workspace_root

    @property
    def repository(self) -> CreativeProjectRepository:
        return self._repository

    def list_projects(self) -> list[dict[str, Any]]:
        return self._repository.list_projects()

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        project = self._repository.get_project(project_id)
        if not project:
            return None
        return {
            **project,
            "workflow": self._repository.get_latest_workflow_for_project(project_id),
        }

    def workspace_path(self, project_id: str) -> Path:
        project = self.get_project(project_id)
        if not project:
            raise ValueError("创作项目不存在")
        return Path(str(project["workspacePath"]))

    def resolve_public_file(self, raw_path: str) -> Path:
        """Resolve a browser-requested artifact without escaping project storage."""

        root = self._workspace_root.resolve()
        candidate = Path(raw_path).expanduser().resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("只能查看创作项目目录中的文件") from exc
        if not candidate.is_file():
            raise FileNotFoundError("创作文件不存在")
        if candidate.suffix.lower() not in {".md", ".json", ".txt"}:
            raise ValueError("暂不支持查看此文件类型")
        return candidate

    def resolve_project_file(self, project_id: str, relative_path: str) -> Path:
        """Resolve a stable project URL to a file inside that project's workspace."""

        workspace = self.workspace_path(project_id).resolve()
        candidate = (workspace / relative_path).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError as exc:
            raise ValueError("文件路径无效") from exc
        return self.resolve_public_file(str(candidate))

    def create_novel_project(
        self,
        *,
        title: str,
        idea: str,
        target_words: int = 3000,
        chapter_count: int = 1,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a durable novel project and its starter workflow."""

        clean_title = title.strip() or self._title_from_idea(idea)
        spec = {
            "idea": idea.strip(),
            "targetWords": target_words,
            "chapterCount": chapter_count,
            "domainPack": "novel.v1",
            "approvalPolicy": {
                "novelBible": "required",
                "chapterOutline": "required",
                "finalNovelMarkdown": "required",
            },
        }
        workspace_path = self._allocate_workspace_path(clean_title)
        self._initialize_workspace(workspace_path, clean_title, spec)
        project = self._repository.create_project(
            title=clean_title,
            domain="novel",
            workspace_path=str(workspace_path),
            spec=spec,
            session_id=session_id,
        )
        workflow = self._repository.create_workflow_run(
            project_id=str(project["id"]),
            workflow_key="novel.default.v1",
            steps=[dict(step) for step in NOVEL_STEPS],
        )
        self._create_initial_artifacts(project, workflow, workspace_path)
        return {**project, "workflow": workflow}

    def create_screenplay_project(
        self,
        *,
        title: str,
        idea: str,
        target_minutes: int = 3,
        episode_count: int = 1,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible wrapper for the earlier route name."""

        return self.create_novel_project(
            title=title,
            idea=idea,
            target_words=max(target_minutes, 1) * 1000,
            chapter_count=episode_count,
            session_id=session_id,
        )

    def build_novel_prompt(self, project_id: str) -> str:
        """Return only the user's request; workflow policy lives in the workspace."""

        project = self.get_project(project_id)
        if not project:
            raise ValueError("创作项目不存在")
        spec = project["spec"]
        return str(spec.get("idea") or project["title"]).strip()

    def build_director_prompt(self, project_id: str) -> str:
        """Backward-compatible wrapper for the older endpoint name."""

        return self.build_novel_prompt(project_id)

    @staticmethod
    def _title_from_idea(idea: str) -> str:
        text = idea.strip()
        if not text:
            return "新的小说项目"
        return text[:18]

    def _allocate_workspace_path(self, title: str) -> Path:
        self._workspace_root.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title).strip("-")
        slug = slug[:40] or "novel-project"
        candidate = self._workspace_root / slug
        index = 2
        while candidate.exists():
            candidate = self._workspace_root / f"{slug}-{index}"
            index += 1
        return candidate

    def _initialize_workspace(
        self, workspace_path: Path, title: str, spec: dict[str, Any]
    ) -> None:
        for relative in (
            "state",
            "canon",
            "structure/episodes",
            "production",
            "references",
            "exports",
            ".zaojing",
            "skills/novel-writing",
            "knowledge",
            "schemas",
        ):
            (workspace_path / relative).mkdir(parents=True, exist_ok=True)
        self._write_json(workspace_path / "project.json", {"title": title, **spec})
        self._write_json(
            workspace_path / ".zaojing/context_manifest.json",
            {
                "version": 1,
                "sourceOfTruth": "sqlite",
                "domainPack": "novel.v1",
                "pinnedFiles": [
                    "project.json",
                    "AGENTS.md",
                    "canon/novel-bible.md",
                    "structure/chapter-outline.md",
                    "exports/novel.md",
                    "exports/novel-project.md",
                    "state/workflow.json",
                ],
            },
        )
        (workspace_path / "skills/novel-writing/SKILL.md").write_text(
            """# 小说写作 Skill

## 目标

把用户的创意发展为连续、完整、可阅读的 Markdown 小说。

## 执行规则

1. 默认自动补全不影响主线的缺失信息。
2. 先建立需求、人物、世界观和章节结构，再写正文。
3. 每章必须有事件推进、人物变化和情绪落点。
4. 不使用镜头号、场景号或导演调度格式。
5. 修改设定时同步检查后续章节的影响。

## 输出要求

先更新结构化 JSON，再渲染对应 Markdown 文件，最后更新聚合文档。
""",
            encoding="utf-8",
        )
        (workspace_path / "knowledge/story-architecture.md").write_text(
            """# 故事结构知识卡

## 基本原则

- 主角需要同时拥有外在目标和内在缺口。
- 冲突应逐步升级，并迫使主角做出选择。
- 每章结尾留下新的问题、代价或情绪变化。
- 结尾应回应开头提出的核心情感问题。
""",
            encoding="utf-8",
        )
        self._write_json(
            workspace_path / "schemas/novel-project.schema.json",
            {
                "type": "object",
                "required": ["title", "idea", "chapterCount", "targetWords"],
                "properties": {
                    "title": {"type": "string"},
                    "idea": {"type": "string"},
                    "chapterCount": {"type": "integer", "minimum": 1},
                    "targetWords": {"type": "integer", "minimum": 500},
                },
            },
        )
        self._write_json(
            workspace_path / "state/workflow.json",
            {"workflowKey": "novel.default.v1", "steps": list(NOVEL_STEPS)},
        )
        (workspace_path / "AGENTS.md").write_text(
            f"""# {title}

你是造境的小说创作 Agent。用户消息只表达创作意图；项目规格、执行阶段、
文件位置和质量约束由当前工作空间提供，不要要求用户重复这些内部信息。

## 上下文读取顺序

1. `project.json`
2. `state/workflow.json`
3. `skills/novel-writing/SKILL.md`
4. `knowledge/story-architecture.md`
5. `canon/novel-bible.md`、`structure/chapter-outline.md` 和已有正文

## 自动执行流程

信息足够时一次性连续完成，不要逐阶段要求用户确认：

1. 更新 `state/creative-brief.md`
2. 更新 `canon/novel-bible.md`
3. 更新 `structure/chapter-outline.md`
4. 更新 `structure/plot-beats.md`
5. 更新 `exports/novel.md`
6. 更新 `state/revision-report.md`
7. 更新 `exports/novel-project.md`

只有缺失信息会导致故事无法成立或存在重大方向冲突时，才向用户提出最多三个问题。
其他缺失信息应根据题材、篇幅和目标读者自行作出合理决定。

## 工作原则

- 先澄清创作目标，再写小说设定集，再拆章节和情节节拍，最后写正文。
- 最终正文写入 `exports/novel.md`，必须像小说一样自然可读。
- 每次更新阶段产物后，同步维护 `exports/novel-project.md` 聚合文件。
- 不使用剧本格式，不写镜头号、场景号、导演调度和拍摄术语。
- 所有新增设定必须能回写到小说设定集或修订审查报告。
- 用户要求修改主线、人物或关键道具时，先说明影响范围，再给出修改方案。
- 每个阶段输出都要适合后续扩展到漫画、图片、视频、短剧制作。
- 最终回复只总结完成情况，不复述内部工作流提示词，不输出本机绝对路径。
""",
            encoding="utf-8",
        )
        initial_files = self._initial_novel_files(title, spec)
        for relative_path, content in initial_files.items():
            (workspace_path / relative_path).write_text(content, encoding="utf-8")

    def _create_initial_artifacts(
        self, project: dict[str, Any], workflow: dict[str, Any], workspace_path: Path
    ) -> None:
        for step in workflow["steps"]:
            path = step.get("artifactPath")
            kind = step.get("artifactKind")
            if not path or not kind:
                continue
            full_path = workspace_path / str(path)
            content = full_path.read_text(encoding="utf-8")
            self._repository.create_artifact(
                project_id=str(project["id"]),
                workflow_step_run_id=str(step["id"]),
                kind=str(kind),
                title=str(step["title"]),
                canonical_path=str(path),
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                file_path=str(full_path),
                change_note="初始化阶段产物",
            )

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _initial_novel_files(title: str, spec: dict[str, Any]) -> dict[str, str]:
        idea = str(spec.get("idea") or "").strip() or title
        chapter_count = int(spec.get("chapterCount") or 1)
        target_words = int(spec.get("targetWords") or 3000)
        chapter_lines = "\n".join(
            f"{index}. 第 {index} 章：围绕主角的一次关键选择展开，"
            "保留悬念并推动人物变化。"
            for index in range(1, chapter_count + 1)
        )
        beat_lines = "\n".join(
            f"- 第 {index} 章：开场钩子 -> 冲突升级 -> 情绪转折 -> 章末悬念"
            for index in range(1, chapter_count + 1)
        )
        files = {
            "state/creative-brief.md": f"""# 需求澄清

## 原始创意

{idea}

## 当前目标

- 形式：Markdown 小说
- 章节数：{chapter_count}
- 目标字数：约 {target_words} 字
- 输出位置：`exports/novel.md`
- 聚合文件：`exports/novel-project.md`
- 写作要求：像小说一样自然叙述，不使用剧本、分镜或导演调度格式。

## 仍可继续追问

- 主角名字和年龄是否需要指定
- 故事面向儿童、青少年还是成人读者
- 文风更偏温暖、悬疑、幽默还是奇幻
""",
            "canon/novel-bible.md": f"""# 小说设定集

## 核心命题

{idea}

## 叙事声音

第三人称有限视角，语言有画面感，但以人物感受推动情节。

## 主角设计

- 主角：待命名
- 外在目标：完成一次看似普通、实则改变自我的冒险
- 内在缺口：害怕离开熟悉环境，或不相信自己能独立解决问题
- 成长方向：从被动等待，变成主动选择

## 主要关系

- 陪伴者：帮助主角看见自身盲点
- 阻力者：制造误会、压力或诱惑
- 关键道具：承载伏笔，在结尾完成回收

## 连续性规则

- 每一章都要推动人物变化，不能只发生事件
- 重要道具首次出现后，需要在后文回收
- 结尾要回应开头的情感问题
""",
            "structure/chapter-outline.md": f"""# 章节大纲

{chapter_lines}
""",
            "structure/plot-beats.md": f"""# 情节节拍

{beat_lines}
""",
            "exports/novel.md": f"""# {title}

> 这是一份初始 Markdown 小说草稿。Agent 后续会在这个文件中继续扩写、修订和完善。

## 第一章 还没有名字的出发

黄昏慢慢落在窗台上，玻璃被夕光擦得发亮。主角蹲在光影交界的地方，
望着屋外那条熟悉得不能再熟悉的小路，第一次觉得它像一条通往远方的河。

它原本以为，今天也会和过去的许多天一样安静过去：风吹动窗帘，屋里传来
杯盏轻碰的声音，墙上的钟慢慢走完一圈。可是那个念头偏偏在这时冒了出来：
如果一直待在原地，它永远不会知道路的尽头有什么。

门缝里钻进一阵凉风，也带来一点陌生的气味。那气味很轻，像雨前的泥土，
又像某个很久以前被忘在角落里的约定。主角站起来，心里有些害怕，却没有
后退。

“就去看一眼。”它对自己说。

这句话很小，小到几乎被钟声盖住。可就是从这一刻开始，故事真正离开了窗台。

## 后续章节摘要

{chapter_lines}
""",
            "state/revision-report.md": """# 修订审查

## 当前状态

- 初始小说草稿已创建
- 后续需要检查人物弧光、伏笔回收、叙事节奏和语言统一性

## 修订关注点

- 是否像小说，而不是剧本
- 章节之间是否连续
- 情绪是否有递进
- 结尾是否回应开头
""",
        }
        files["exports/novel-project.md"] = CreativeProjectService._aggregate_project_markdown(
            title, files
        )
        return files

    @staticmethod
    def _aggregate_project_markdown(title: str, files: dict[str, str]) -> str:
        """Build one reviewable Markdown document from all novel artifacts."""

        sections = (
            ("一、需求澄清", "state/creative-brief.md"),
            ("二、小说设定集", "canon/novel-bible.md"),
            ("三、章节大纲", "structure/chapter-outline.md"),
            ("四、情节节拍", "structure/plot-beats.md"),
            ("五、小说正文", "exports/novel.md"),
            ("六、修订审查", "state/revision-report.md"),
        )
        body = [
            f"# {title}｜小说项目总览",
            "",
            "> 本文件聚合小说项目的阶段产物，方便一次性检查。",
            "> 单项文件仍保留在各自目录，便于后续分阶段更新。",
            "",
        ]
        for heading, path in sections:
            content = CreativeProjectService._public_artifact_content(files[path])
            body.extend([
                f"## {heading}",
                "",
                content,
                "",
            ])
        return "\n".join(body).rstrip() + "\n"

    @staticmethod
    def _public_artifact_content(content: str) -> str:
        """Remove internal file path details from the public aggregate."""

        hidden_fragments = (
            "state/creative-brief.md",
            "canon/novel-bible.md",
            "structure/chapter-outline.md",
            "structure/plot-beats.md",
            "exports/novel.md",
            "exports/novel-project.md",
            "state/revision-report.md",
        )
        lines = []
        for line in content.strip().splitlines():
            if any(fragment in line for fragment in hidden_fragments):
                continue
            lines.append(line)
        return "\n".join(lines).strip()
