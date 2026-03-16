from __future__ import annotations

"""校验阶段，负责检查 skill 结构完整性和关键内容是否仍是占位符。"""

import argparse
import json
import re
from pathlib import Path

from .common import is_placeholder_text


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        raise RuntimeError("缺少 YAML frontmatter。")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    refs = [
        skill_dir / "references" / "core-method.md",
        skill_dir / "references" / "decision-rules.md",
        skill_dir / "references" / "patterns.md",
    ]

    if not skill_md.exists():
        errors.append("缺少 SKILL.md")
    else:
        try:
            skill_text = skill_md.read_text(encoding="utf-8")
            frontmatter = parse_frontmatter(skill_md)
            if "name" not in frontmatter:
                errors.append("SKILL.md frontmatter 缺少 'name'")
            if "description" not in frontmatter:
                errors.append("SKILL.md frontmatter 缺少 'description'")
            extra = sorted(set(frontmatter) - {"name", "description"})
            if extra:
                errors.append(f"SKILL.md frontmatter 含有非标准字段: {', '.join(extra)}")
            if is_placeholder_text(frontmatter.get("name", "")):
                errors.append("SKILL.md frontmatter 的 'name' 仍是占位内容")
            if is_placeholder_text(frontmatter.get("description", "")):
                errors.append("SKILL.md frontmatter 的 'description' 仍是占位内容")
            if "围绕“-" in skill_text or "核心问题“-" in skill_text or "核心答案“-" in skill_text:
                errors.append("SKILL.md 含有未清洗的列表标记拼接痕迹")
        except RuntimeError as exc:
            errors.append(str(exc))

    if not openai_yaml.exists():
        errors.append("缺少 agents/openai.yaml")
    else:
        yaml_text = openai_yaml.read_text(encoding="utf-8")
        if "default_prompt:" not in yaml_text:
            errors.append("agents/openai.yaml 缺少 default_prompt")
    for ref in refs:
        if not ref.exists():
            errors.append(f"缺少 {ref.relative_to(skill_dir)}")
        else:
            ref_text = ref.read_text(encoding="utf-8")
            if is_placeholder_text(ref_text):
                errors.append(f"{ref.relative_to(skill_dir)} 仍是占位内容")

    skill_spec = skill_dir / "skill-spec.json"
    if skill_spec.exists():
        try:
            data = json.loads(skill_spec.read_text(encoding="utf-8"))
            if is_placeholder_text(str(data.get("source_book", {}).get("title", ""))):
                errors.append("skill-spec.json 的 source_book.title 仍是占位内容")
            for phrase in data.get("trigger_phrases", []):
                if isinstance(phrase, str) and is_placeholder_text(phrase):
                    errors.append("skill-spec.json 的 trigger_phrases 含占位内容")
                    break
            mode = data.get("mode")
            if mode not in {"reference", "operational"}:
                errors.append("skill-spec.json 的 mode 非法")
        except json.JSONDecodeError:
            errors.append("skill-spec.json 不是合法 JSON")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    errors = validate_skill(skill_dir)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0
