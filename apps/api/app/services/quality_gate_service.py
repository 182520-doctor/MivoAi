"""Deterministic quality gates for creative project artifacts.

The first version intentionally uses local, explainable checks. A model may
write prose, but it must not be the only source of truth for workflow validity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class QualityGateService:
    """Validate the minimum contract of a novel workspace."""

    def inspect(self, workspace: Path) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        required = {
            "creative_brief": workspace / "state/creative-brief.md",
            "novel_bible": workspace / "canon/novel-bible.md",
            "chapter_outline": workspace / "structure/chapter-outline.md",
            "plot_beats": workspace / "structure/plot-beats.md",
            "novel_draft": workspace / "exports/novel.md",
        }
        contents: dict[str, str] = {}
        for key, path in required.items():
            if not path.is_file():
                findings.append({"severity": "error", "code": "missing_artifact", "message": key})
                continue
            text = path.read_text(encoding="utf-8").strip()
            contents[key] = text
            if len(text) < 40:
                findings.append({"severity": "error", "code": "artifact_too_short", "message": key})

        draft = contents.get("novel_draft", "")
        if draft and not re.search(r"^##+\s+", draft, re.MULTILINE):
            findings.append(
                {
                    "severity": "warning",
                    "code": "missing_chapter_heading",
                    "message": "小说正文缺少章节标题",
                }
            )
        if draft and re.search(r"(镜头号|场景号|INT\.|EXT\.)", draft, re.IGNORECASE):
            findings.append(
                {
                    "severity": "warning",
                    "code": "screenplay_style_detected",
                    "message": "正文疑似混入剧本格式",
                }
            )

        bible = contents.get("novel_bible", "")
        outline = contents.get("chapter_outline", "")
        if bible and outline and "待命名" in outline and "待命名" not in bible:
            findings.append(
                {
                    "severity": "warning",
                    "code": "canon_mismatch",
                    "message": "章节大纲包含未定义人物",
                }
            )

        errors = [item for item in findings if item["severity"] == "error"]
        return {
            "passed": not errors,
            "status": "passed" if not errors else "failed",
            "findings": findings,
            "checkedFiles": list(contents),
        }

    def write_report(self, workspace: Path, result: dict[str, Any]) -> Path:
        report = workspace / "state/revision-report.md"
        lines = [
            "# 修订审查",
            "",
            "## 结果",
            "",
            "通过" if result["passed"] else "未通过",
            "",
            "## 检查项",
            "",
        ]
        if not result["findings"]:
            lines.append("未发现结构性问题。")
        else:
            lines.extend(
                f"- [{item['severity']}] {item['message']}"
                for item in result["findings"]
            )
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report

    @staticmethod
    def impact_analysis(changed_step: str) -> dict[str, Any]:
        downstream = {
            "intake": [
                "novel_bible",
                "chapter_outline",
                "plot_beats",
                "novel_draft",
                "revision_review",
            ],
            "novel_bible": ["chapter_outline", "plot_beats", "novel_draft", "revision_review"],
            "chapter_outline": ["plot_beats", "novel_draft", "revision_review"],
            "plot_beats": ["novel_draft", "revision_review"],
            "novel_draft": ["revision_review"],
            "revision_review": [],
        }
        return {"changedStep": changed_step, "affectedSteps": downstream.get(changed_step, [])}
