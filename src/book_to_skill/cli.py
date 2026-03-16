from __future__ import annotations

"""命令行入口，负责参数解析、子命令装配和兼容性导出。"""

import argparse
import importlib
import sys
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    # Support direct execution like: python3 path/to/cli.py ...
    # In that mode relative imports fail, so add the src parent to sys.path
    # and fall back to absolute package imports.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from book_to_skill.common import infer_title_from_markdown
    from book_to_skill import __version__
    from book_to_skill.exporters import command_export
    from book_to_skill.forge import command_forge
    from book_to_skill.importers import command_import, import_pdf, merge_markdown_pages
    from book_to_skill.validate import command_validate
    from book_to_skill.xray import command_xray
else:
    from . import __version__
    from .common import infer_title_from_markdown
    from .exporters import command_export
    from .forge import command_forge
    from .importers import command_import, import_pdf, merge_markdown_pages
    from .validate import command_validate
    from .xray import command_xray


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book2skill",
        description="Turn nonfiction books into installable skills through a structured CLI pipeline.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="将书稿输入归一化为 markdown。")
    import_parser.add_argument("input")
    import_parser.add_argument("--out", required=True)
    import_parser.add_argument(
        "--allow-degraded-pdf-text",
        action="store_true",
        help="当 OCR 不可用或失败时，允许降级到非 OCR 文本提取并继续后续流程。",
    )
    import_parser.set_defaults(func=command_import)

    xray_parser = subparsers.add_parser("xray", help="创建或落盘 xray 拆书产物。")
    xray_parser.add_argument("normalized_book")
    xray_parser.add_argument("--out", required=True)
    xray_parser.add_argument("--report", help="待解析的已填写 xray markdown 报告。")
    xray_parser.set_defaults(func=command_xray)

    forge_parser = subparsers.add_parser("forge", help="从 xray-result.json 锻造 skill。")
    forge_parser.add_argument("xray_result")
    forge_parser.add_argument("--out", required=True)
    forge_parser.add_argument("--skill-name")
    forge_parser.set_defaults(func=command_forge)

    validate_parser = subparsers.add_parser("validate", help="校验生成出的 skill。")
    validate_parser.add_argument("skill_dir")
    validate_parser.set_defaults(func=command_validate)

    export_parser = subparsers.add_parser("export", help="将生成 skill 导出为目标兼容包。")
    export_parser.add_argument("--target", required=True)
    export_parser.add_argument("skill_dir")
    export_parser.add_argument("--out", required=True)
    export_parser.set_defaults(func=command_export)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
