from __future__ import annotations

"""导出阶段，负责把 canonical skill 包转换成目标平台兼容产物。"""

import argparse
import json
import shutil
import textwrap
from pathlib import Path

from .common import ensure_dir, write_json, write_text
from .validate import validate_skill


def command_export(args: argparse.Namespace) -> int:
    if args.target != "claude-code":
        raise RuntimeError(f"暂不支持的导出目标：{args.target}")

    skill_dir = Path(args.skill_dir).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    errors = validate_skill(skill_dir)
    if errors:
        raise RuntimeError(f"导出前校验失败：{'；'.join(errors)}")

    bundle_root = out_dir / "claude-code" / skill_dir.name
    copied_skill = bundle_root / "skills" / skill_dir.name
    ensure_dir(copied_skill.parent)
    if copied_skill.exists():
        shutil.rmtree(copied_skill)
    shutil.copytree(skill_dir, copied_skill)

    write_json(
        bundle_root / "manifest.json",
        {
            "target": "claude-code",
            "source_skill": skill_dir.name,
            "bundle_skill_path": str(Path("skills") / skill_dir.name),
        },
    )
    write_text(
        bundle_root / "CLAUDE.md",
        textwrap.dedent(
            f"""\
            # Claude Code 兼容包

            来源 skill：`{skill_dir.name}`

            将 `skills/{skill_dir.name}` 复制到你的 Claude Code skill 目录，或仓库级 skill 目录中。

            复制后的 `SKILL.md` 就是该 skill 的权威指令文件。
            """
        ),
    )
    print(json.dumps({"bundle_dir": str(bundle_root)}, ensure_ascii=False))
    return 0
