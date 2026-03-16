from __future__ import annotations

"""锻造阶段，负责把 xray 结果转换成标准 skill 包及其元数据。"""

import argparse
import json
import textwrap
from pathlib import Path

from .common import compact_bullets, ensure_dir, slugify, to_paragraph, write_json, write_text


def build_generated_skill_description(name: str, xray: dict[str, str], mode: str) -> str:
    summary = to_paragraph(xray["one_sentence_summary"], xray["core_answer"])
    capability = "分析与指导能力" if mode == "reference" else "可执行方法能力"
    return (
        f"将书中的方法沉淀成可复用的{capability}。适用于用户需要围绕“{summary}”"
        f"来执行、分析或迁移方法，并希望获得紧凑工作流、决策规则和可复用 references。"
    )


def detect_skill_mode(xray: dict[str, str]) -> str:
    action_text = to_paragraph(xray["action_triggers"], "").lower()
    summary_text = to_paragraph(xray.get("one_sentence_summary", ""), "").lower()
    boundary_text = to_paragraph(xray.get("boundary_conditions", ""), "").lower()
    argument_type = to_paragraph(xray.get("argument_type", ""), "").lower()

    if not action_text or len(action_text) < 20:
        return "reference"

    reference_markers = [
        "传统文化",
        "文化参考",
        "民俗",
        "史料",
        "索引",
        "检索书",
        "分类断语",
        "不是现代科学",
        "不适合当成确定预测",
        "not modern science",
        "cultural reference",
        "reference",
        "index",
    ]
    if any(marker in text for marker in reference_markers for text in [summary_text, boundary_text, argument_type]):
        return "reference"

    vague_markers = ["reflect", "consider", "understand", "think about", "appreciate"]
    if sum(marker in action_text for marker in vague_markers) >= 2:
        return "reference"
    return "operational"


def build_generated_skill_markdown(skill_name: str, xray: dict[str, str], mode: str) -> str:
    answer = to_paragraph(xray["core_answer"])
    question = to_paragraph(xray["core_question"])
    summary = to_paragraph(xray["one_sentence_summary"], answer)
    prompt = "分析或应用" if mode == "reference" else "应用"
    return textwrap.dedent(
        f"""\
        ---
        name: {skill_name}
        description: 当用户希望{prompt}围绕“{summary}”提炼出的书中方法时使用此 skill。它帮助另一个 agent 从这本书的核心问题“{question}”和核心答案“{answer}”出发，结合紧凑工作流、决策规则和可复用 references 完成任务。
        ---

        # {skill_name}

        先读取最少必要上下文：

        - 阅读 `references/core-method.md`，获取方法与支撑论证。
        - 阅读 `references/decision-rules.md`，获取假设、边界和失效条件。
        - 阅读 `references/patterns.md`，获取迁移模式、盲点和行动触发器。

        ## 工作流

        1. 用核心问题和核心答案重述用户任务。
        2. 只从 `references/core-method.md` 中提取当前任务相关的部分。
        3. 在给出建议前，先检查 `references/decision-rules.md` 里的约束。
        4. 用 `references/patterns.md` 把方法迁移到邻近场景。
        5. 输出简洁可执行的步骤，而不是书摘摘要。

        ## 质量要求

        - 回答保持可执行、具体。
        - 当请求超出书中方法的有效边界时明确指出。
        - 优先使用书中的方法，不要退化成泛泛建议。
        - 不要大段逐字引用原书内容。
        """
    )


def build_core_method(xray: dict[str, str]) -> str:
    return textwrap.dedent(
        f"""\
        # 核心方法

        ## 核心问题
        {to_paragraph(xray["core_question"])}

        ## 核心答案
        {to_paragraph(xray["core_answer"])}

        ## 章节骨架
        {compact_bullets(xray["chapter_skeleton"])}
        ## 论证类型
        {to_paragraph(xray["argument_type"])}

        ## 论证链
        {compact_bullets(xray["argument_chain"])}
        ## 关键证据
        {compact_bullets(xray["key_evidence"])}
        """
    )


def build_decision_rules(xray: dict[str, str]) -> str:
    return textwrap.dedent(
        f"""\
        # 决策规则

        ## 隐形假设
        {compact_bullets(xray["hidden_assumptions"])}
        ## 边界条件
        {compact_bullets(xray["boundary_conditions"])}
        """
    )


def build_patterns(xray: dict[str, str]) -> str:
    return textwrap.dedent(
        f"""\
        # 模式与迁移

        ## 作者盲点
        {compact_bullets(xray["author_blind_spots"])}
        ## 跨域映射
        {compact_bullets(xray["cross_domain_mappings"])}
        ## 知识连接
        {compact_bullets(xray["knowledge_connections"])}
        ## 行动触发器
        {compact_bullets(xray["action_triggers"])}
        ## 餐巾纸公式
        {to_paragraph(xray["napkin_formula"])}

        ## 餐巾纸图
        ```text
        {to_paragraph(xray["napkin_diagram_ascii"])}
        ```

        ## 一句话总结
        {to_paragraph(xray["one_sentence_summary"])}
        """
    )


def build_openai_yaml(skill_name: str, mode: str) -> str:
    display_name = skill_name.replace("-", " ").title()
    short_description = f"基于书籍提炼的技能：{display_name}"[:64]
    intent = "分析或解释" if mode == "reference" else "应用"
    return textwrap.dedent(
        f"""\
        interface:
          display_name: "{display_name}"
          short_description: "{short_description}"
          default_prompt: "使用 ${skill_name} {intent}这本书提炼出的能力，并结合 references 回答我的任务。"

        policy:
          allow_implicit_invocation: true
        """
    )


def command_forge(args: argparse.Namespace) -> int:
    xray_path = Path(args.xray_result).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    xray = json.loads(xray_path.read_text(encoding="utf-8"))
    skill_name = slugify(args.skill_name or xray.get("book_title") or xray_path.stem)
    skill_dir = out_dir / skill_name
    ensure_dir(skill_dir / "references")
    ensure_dir(skill_dir / "agents")

    mode = detect_skill_mode(xray)
    write_text(skill_dir / "SKILL.md", build_generated_skill_markdown(skill_name, xray, mode))
    write_text(skill_dir / "references" / "core-method.md", build_core_method(xray))
    write_text(skill_dir / "references" / "decision-rules.md", build_decision_rules(xray))
    write_text(skill_dir / "references" / "patterns.md", build_patterns(xray))
    write_text(skill_dir / "agents" / "openai.yaml", build_openai_yaml(skill_name, mode))
    write_json(
        skill_dir / "skill-spec.json",
        {
            "source_book": {
                "title": xray.get("book_title", ""),
                "author": xray.get("book_author", ""),
            },
            "target_skill_name": skill_name,
            "mode": mode,
            "trigger_phrases": [
                to_paragraph(xray.get("core_question", "")),
                to_paragraph(xray.get("one_sentence_summary", "")),
            ],
            "workflow_steps": [
                "用核心问题和核心答案重述任务。",
                "从 core-method 提取相关方法。",
                "检查假设与边界条件。",
                "结合模式与行动触发器完成迁移。",
            ],
            "references_plan": [
                "references/core-method.md",
                "references/decision-rules.md",
                "references/patterns.md",
            ],
            "tool_adapters": ["claude-code"],
        },
    )
    print(json.dumps({"skill_dir": str(skill_dir), "mode": mode}, ensure_ascii=False))
    return 0
