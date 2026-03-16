from __future__ import annotations

"""通用工具函数，提供路径写入、文本清洗、标题推断和占位内容判断。"""

import json
import re
from pathlib import Path


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "generated-skill"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def infer_title_from_markdown(text: str, fallback: str) -> str:
    ignored_titles = {
        "about this digital edition",
        "about this edition",
        "digital edition",
        "about this ebook",
    }
    heading_candidates: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if match:
            title = match.group(1).strip()
            if title:
                heading_candidates.append(title)
    for title in heading_candidates:
        if title.lower() not in ignored_titles:
            return title
    if heading_candidates:
        return heading_candidates[0]
    return fallback


def strip_list_markers(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    cleaned = [re.sub(r"^[-*]\s+", "", line) for line in lines]
    return " ".join(cleaned).strip()


def compact_bullets(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return "- 未提供\n"
    return "\n".join(line if line.startswith(("-", "*")) else f"- {line}" for line in lines) + "\n"


def to_paragraph(value: str, fallback: str = "未提供。") -> str:
    text = strip_list_markers(value)
    return text or fallback


def is_placeholder_text(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return True
    if normalized in {"-", "*", "TODO", "TBD", "未提供", "N/A"}:
        return True
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    return bool(lines) and all(line in {"-", "*", "- 未提供", "* 未提供"} for line in lines)
