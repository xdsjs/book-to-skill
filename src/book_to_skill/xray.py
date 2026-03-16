from __future__ import annotations

"""xray 阶段，负责生成拆书工作包、解析报告并产出结构化 xray 结果。"""

import argparse
import json
import re
import textwrap
from pathlib import Path

from .common import ensure_dir, infer_title_from_markdown, is_placeholder_text, write_json, write_text


XRAY_FIELDS = {
    "book_title": "书名",
    "book_author": "作者",
    "core_question": "核心问题",
    "core_answer": "核心答案",
    "chapter_skeleton": "章节骨架",
    "argument_type": "论证类型",
    "argument_chain": "论证链",
    "key_evidence": "关键证据",
    "hidden_assumptions": "隐形假设",
    "boundary_conditions": "边界条件",
    "author_blind_spots": "作者盲点",
    "cross_domain_mappings": "跨域映射",
    "knowledge_connections": "知识连接",
    "action_triggers": "行动触发器",
    "napkin_formula": "餐巾纸公式",
    "napkin_diagram_ascii": "餐巾纸图",
    "one_sentence_summary": "一句话总结",
}


def build_xray_prompt(book_text: str, title: str, import_manifest: dict[str, object] | None = None) -> str:
    excerpt = "\n".join(book_text.splitlines()[:120]).strip()
    import_note = ""
    if import_manifest and import_manifest.get("degraded"):
        extraction_method = str(import_manifest.get("extraction_method", "unknown"))
        warnings = import_manifest.get("warnings", [])
        warning_lines = "\n".join(f"- {item}" for item in warnings[:5] if isinstance(item, str))
        import_note = textwrap.dedent(
            f"""\

            导入质量提示：

            - 当前书稿来自降级提取：`{extraction_method}`
            - 请在拆书报告中主动标记不确定性，警惕章节错序、缺字和段落断裂。
            {warning_lines}
            """
        ).rstrip()
    return textwrap.dedent(
        f"""\
        # Xray 拆书提示词

        请严格按照 `ljg-xray-book` 协议分析这份归一化后的书稿。

        必做轮次：

        1. 骨架扫描
        2. 血肉解剖
        3. 灵魂提取
        4. 餐巾纸压缩

        请先参考 `xray-report-template.md` 的字段结构，再将完整结果另存为独立报告文件，例如 `xray-report.md`。

        约束：

        - 语义字段必须完整保留。
        - 每个字段保持紧凑，便于后续锻造成 skill。
        - 证据和解释分开写。
        - 如果这本书的可执行性较弱，要明确指出。
        - 如果导入质量提示显示为 degraded，请在结论中显式写出你的不确定性。

        书名：{title}
        {import_note}

        书稿片段预览：

        ```markdown
        {excerpt}
        ```
        """
    )


def build_xray_report_template(title: str) -> str:
    parts = ["# Xray 拆书报告", "", f"## {XRAY_FIELDS['book_title']}", title, ""]
    for key, heading in XRAY_FIELDS.items():
        if key == "book_title":
            continue
        parts.extend([f"## {heading}", "- ", ""])
    return "\n".join(parts).rstrip() + "\n"


def parse_xray_report(report_text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", report_text, flags=re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        body = report_text[start:end].strip()
        sections[heading] = body

    result: dict[str, str] = {}
    missing: list[str] = []
    for field, heading in XRAY_FIELDS.items():
        value = sections.get(heading, "").strip()
        if not value:
            missing.append(heading)
        result[field] = value

    if missing:
        raise RuntimeError(f"缺少必需的 xray 章节：{', '.join(missing)}")
    return result


def command_xray(args: argparse.Namespace) -> int:
    normalized_book = Path(args.normalized_book).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    ensure_dir(out_dir)
    book_text = normalized_book.read_text(encoding="utf-8")
    title = infer_title_from_markdown(book_text, normalized_book.stem)
    manifest_path = normalized_book.parent / "import-manifest.json"
    import_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None

    prompt_path = out_dir / "xray-prompt.md"
    template_path = out_dir / "xray-report-template.md"
    template_json_path = out_dir / "xray-result.template.json"

    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        if report_path == template_path:
            raise RuntimeError(
                "--report 不能直接指向 xray-report-template.md。请将填写后的报告另存为独立文件，例如 xray-report.md。"
            )
        write_text(prompt_path, build_xray_prompt(book_text, title, import_manifest))
        if not template_path.exists():
            write_text(template_path, build_xray_report_template(title))
        if not template_json_path.exists():
            write_json(template_json_path, {field: "" for field in XRAY_FIELDS})
        parsed = parse_xray_report(report_path.read_text(encoding="utf-8"))
        placeholder_fields = [
            heading for field, heading in XRAY_FIELDS.items() if is_placeholder_text(parsed.get(field, ""))
        ]
        if placeholder_fields:
            raise RuntimeError(f"xray 报告仍含占位内容：{', '.join(placeholder_fields)}")
        xray_result_path = out_dir / "xray-result.json"
        write_json(xray_result_path, parsed)
        output = {
            "prompt": str(prompt_path),
            "report_template": str(template_path),
            "xray_template": str(template_json_path),
            "xray_result": str(xray_result_path),
        }
    else:
        write_text(prompt_path, build_xray_prompt(book_text, title, import_manifest))
        write_text(template_path, build_xray_report_template(title))
        write_json(template_json_path, {field: "" for field in XRAY_FIELDS})
        output = {
            "prompt": str(prompt_path),
            "report_template": str(template_path),
            "xray_template": str(template_json_path),
        }

    print(json.dumps(output, ensure_ascii=False))
    return 0
