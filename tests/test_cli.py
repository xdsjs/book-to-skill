from __future__ import annotations

"""CLI 与核心流水线的回归测试，覆盖导入、xray、锻造、校验和导出。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from book_to_skill.cli import (
    command_export,
    command_forge,
    command_import,
    command_validate,
    command_xray,
    infer_title_from_markdown,
    import_pdf,
    merge_markdown_pages,
)


class Namespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class BookToSkillTests(unittest.TestCase):
    def test_pdf_falls_back_to_paddleocr_when_no_text_layer(self) -> None:
        class FakePage:
            def extract_text(self) -> str:
                return ""

        class FakeReader:
            def __init__(self, _: str):
                self.pages = [FakePage()]

        class FakeResult:
            markdown = {"markdown_texts": "# OCR 结果\n\n扫描版正文"}

        class FakePipeline:
            def predict(self, input: str):
                self.input = input
                return [FakeResult()]

            def concatenate_markdown_pages(self, markdown_pages):
                return "\n\n".join(item["markdown_texts"] for item in markdown_pages)

        fake_pypdf = mock.Mock(PdfReader=FakeReader)
        fake_paddleocr = mock.Mock(PPStructureV3=lambda: FakePipeline())

        with mock.patch("book_to_skill.importers.importlib.import_module") as import_module:
            def side_effect(name: str):
                if name == "pypdf":
                    return fake_pypdf
                if name == "paddleocr":
                    return fake_paddleocr
                raise ImportError(name)

            import_module.side_effect = side_effect
            decision = import_pdf(Path("/tmp/fake.pdf"))

        self.assertEqual(decision.extraction_method, "paddleocr")
        self.assertFalse(decision.degraded)
        self.assertIn("OCR 结果", decision.text)
        self.assertIn("扫描版正文", decision.text)

    def test_degraded_pdf_import_continues_and_marks_manifest(self) -> None:
        class FakePage:
            def extract_text(self) -> str:
                return "零碎文本\n页码 1"

        class FakeReader:
            def __init__(self, _: str):
                self.pages = [FakePage(), FakePage()]

        class FakeDoc:
            def __iter__(self):
                return iter([self, self])

            def get_text(self, _: str) -> str:
                return "第一章 方法\n\n这里有一段可继续分析的降级文本。"

            def close(self) -> None:
                return None

        fake_pypdf = mock.Mock(PdfReader=FakeReader)
        fake_fitz = mock.Mock(open=lambda _: FakeDoc())

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "book.pdf"
            source.write_bytes(b"%PDF-1.4")
            imported = tmp_path / "imported"

            with mock.patch("book_to_skill.importers.importlib.import_module") as import_module:
                def side_effect(name: str):
                    if name == "pypdf":
                        return fake_pypdf
                    if name == "fitz":
                        return fake_fitz
                    if name == "paddleocr":
                        raise ImportError(name)
                    raise ImportError(name)

                import_module.side_effect = side_effect
                self.assertEqual(
                    command_import(
                        Namespace(
                            input=str(source),
                            out=str(imported),
                            allow_degraded_pdf_text=True,
                        )
                    ),
                    0,
                )

            manifest = json.loads((imported / "import-manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["degraded"])
            self.assertEqual(manifest["classification"], "DEGRADED_ONLY")
            self.assertEqual(manifest["extraction_method"], "fitz")
            self.assertTrue(manifest["recommended_for_xray"])

            xray_dir = tmp_path / "xray"
            self.assertEqual(
                command_xray(Namespace(normalized_book=str(imported / "normalized-book.md"), out=str(xray_dir), report=None)),
                0,
            )
            prompt = (xray_dir / "xray-prompt.md").read_text(encoding="utf-8")
            self.assertIn("降级提取", prompt)
            self.assertIn("fitz", prompt)

    def test_merge_markdown_pages_unwraps_stringified_markdown_dict(self) -> None:
        class FakePipeline:
            def concatenate_markdown_pages(self, markdown_pages):
                self.markdown_pages = markdown_pages
                return ({'markdown_texts': "# OCR 结果\n\n扫描版正文"},)

        text = merge_markdown_pages(
            [{"markdown_texts": "# Page 1"}],
            FakePipeline(),
        )

        self.assertEqual(text, "# OCR 结果\n\n扫描版正文\n")

    def test_end_to_end_markdown_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "book.md"
            source.write_text("# Test Book\n\nA practical method.\n", encoding="utf-8")

            imported = tmp_path / "imported"
            self.assertEqual(command_import(Namespace(input=str(source), out=str(imported))), 0)
            normalized = imported / "normalized-book.md"
            self.assertTrue(normalized.exists())

            xray_dir = tmp_path / "xray"
            self.assertEqual(command_xray(Namespace(normalized_book=str(normalized), out=str(xray_dir), report=None)), 0)
            report = xray_dir / "report.md"
            report.write_text(
                "\n".join(
                    [
                        "# Xray 拆书报告",
                        "",
                        "## 书名",
                        "Test Book",
                        "",
                        "## 作者",
                        "Author",
                        "",
                        "## 核心问题",
                        "How should teams work?",
                        "",
                        "## 核心答案",
                        "Use a simple repeatable loop.",
                        "",
                        "## 章节骨架",
                        "- Intro",
                        "- Method",
                        "",
                        "## 论证类型",
                        "Methodological",
                        "",
                        "## 论证链",
                        "- Observe",
                        "- Decide",
                        "- Act",
                        "",
                        "## 关键证据",
                        "- Case study",
                        "",
                        "## 隐形假设",
                        "- Stable environment",
                        "",
                        "## 边界条件",
                        "- Fails in crisis",
                        "",
                        "## 作者盲点",
                        "- Underweights incentives",
                        "",
                        "## 跨域映射",
                        "- Product to hiring",
                        "",
                        "## 知识连接",
                        "- OODA loop",
                        "",
                        "## 行动触发器",
                        "- When work is stuck, restate the loop.",
                        "",
                        "## 餐巾纸公式",
                        "Observe -> Decide -> Act",
                        "",
                        "## 餐巾纸图",
                        "[observe] -> [decide] -> [act]",
                        "",
                        "## 一句话总结",
                        "A loop for practical team decisions.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                command_xray(Namespace(normalized_book=str(normalized), out=str(xray_dir), report=str(report))), 0
            )
            xray_result = xray_dir / "xray-result.json"
            data = json.loads(xray_result.read_text(encoding="utf-8"))
            self.assertEqual(data["book_title"], "Test Book")

            forged = tmp_path / "forged"
            self.assertEqual(command_forge(Namespace(xray_result=str(xray_result), out=str(forged), skill_name=None)), 0)
            skill_dir = forged / "test-book"
            self.assertTrue((skill_dir / "SKILL.md").exists())

            self.assertEqual(command_validate(Namespace(skill_dir=str(skill_dir))), 0)

            exported = tmp_path / "exported"
            self.assertEqual(
                command_export(Namespace(target="claude-code", skill_dir=str(skill_dir), out=str(exported))), 0
            )
            self.assertTrue((exported / "claude-code" / "test-book" / "CLAUDE.md").exists())

    def test_xray_report_does_not_allow_template_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            normalized = tmp_path / "normalized-book.md"
            normalized.write_text("# Test Book\n\nBody\n", encoding="utf-8")
            xray_dir = tmp_path / "xray"
            self.assertEqual(command_xray(Namespace(normalized_book=str(normalized), out=str(xray_dir), report=None)), 0)
            with self.assertRaises(RuntimeError):
                command_xray(
                    Namespace(
                        normalized_book=str(normalized),
                        out=str(xray_dir),
                        report=str(xray_dir / "xray-report-template.md"),
                    )
                )

    def test_forge_cleans_bullet_markers_and_detects_reference_mode_for_chinese_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            xray_result = tmp_path / "xray-result.json"
            xray_result.write_text(
                json.dumps(
                    {
                        "book_title": "周公解夢",
                        "book_author": "- 周公旦",
                        "core_question": "- 如何按梦境意象查找传统断语？",
                        "core_answer": "- 先拆对象和动作。\n- 再检索对应类目。\n- 这是一种传统文化参考，不是现代科学预测。",
                        "chapter_skeleton": "- 总引\n- 分类索引",
                        "argument_type": "- 分类断语汇编，偏文化参考。",
                        "argument_chain": "- 拆梦\n- 检索\n- 给出 caveat",
                        "key_evidence": "- 全书是条目式映射",
                        "hidden_assumptions": "- 梦象可分类",
                        "boundary_conditions": "- 这是传统文化参考，不适合当成确定预测。",
                        "author_blind_spots": "- 缺乏现代心理学解释",
                        "cross_domain_mappings": "- 可用于创作",
                        "knowledge_connections": "- 民俗学",
                        "action_triggers": "- 当用户要查梦时，先拆对象、动作、场景。\n- 当用户把它当预测工具时，提醒这只是传统文化参考。",
                        "napkin_formula": "- 梦境拆象 -> 类目检索 -> 传统解释",
                        "napkin_diagram_ascii": "- 记梦\n- 拆象\n- 检索",
                        "one_sentence_summary": "- 一部传统文化参考型的梦兆分类检索书。",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            forged = tmp_path / "forged"
            self.assertEqual(command_forge(Namespace(xray_result=str(xray_result), out=str(forged), skill_name=None)), 0)
            skill_dir = forged / "generated-skill"
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            skill_spec = json.loads((skill_dir / "skill-spec.json").read_text(encoding="utf-8"))
            openai_yaml = (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")

            self.assertNotIn("围绕“-", skill_text)
            self.assertNotIn("核心问题“-", skill_text)
            self.assertEqual(skill_spec["mode"], "reference")
            self.assertIn("分析或解释", openai_yaml)

    def test_validate_rejects_placeholder_xray_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skill_dir = tmp_path / "bad-skill"
            (skill_dir / "agents").mkdir(parents=True)
            (skill_dir / "references").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo\ndescription: -\n---\n\n# demo\n",
                encoding="utf-8",
            )
            (skill_dir / "agents" / "openai.yaml").write_text(
                'interface:\n  default_prompt: "use ${demo}"\n',
                encoding="utf-8",
            )
            for ref_name in ["core-method.md", "decision-rules.md", "patterns.md"]:
                (skill_dir / "references" / ref_name).write_text("-\n", encoding="utf-8")
            (skill_dir / "skill-spec.json").write_text(
                json.dumps(
                    {
                        "source_book": {"title": "-"},
                        "mode": "reference",
                        "trigger_phrases": ["-"],
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(command_validate(Namespace(skill_dir=str(skill_dir))), 1)

    def test_infer_title_skips_digital_edition_boilerplate(self) -> None:
        text = "# About this digital edition\n\n## 周公解夢\n\nBody\n"
        self.assertEqual(infer_title_from_markdown(text, "fallback"), "周公解夢")

    def test_cli_supports_direct_script_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "book.md"
            source.write_text("# Direct Run\n\nBody\n", encoding="utf-8")
            out_dir = tmp_path / "out"
            cli_path = ROOT / "src" / "book_to_skill" / "cli.py"

            result = subprocess.run(
                [sys.executable, str(cli_path), "import", str(source), "--out", str(out_dir)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((out_dir / "normalized-book.md").exists())

    def test_cli_supports_module_execution(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "book_to_skill", "--help"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("book2skill", result.stdout)
        self.assertIn("import", result.stdout)

    def test_cli_reports_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "book_to_skill", "--version"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "book2skill 0.1.0")

    def test_pdf_uses_fitz_fast_path_when_pypdf_missing_but_text_quality_is_high(self) -> None:
        class FakeDoc:
            def __iter__(self):
                return iter([self, self])

            def get_text(self, _: str) -> str:
                return "第一章 方法\n\n" + ("这里有足够多的高质量文本。" * 80)

            def close(self) -> None:
                return None

        fake_fitz = mock.Mock(open=lambda _: FakeDoc())

        with mock.patch("book_to_skill.importers.importlib.import_module") as import_module:
            def side_effect(name: str):
                if name == "pypdf":
                    raise ImportError(name)
                if name == "fitz":
                    return fake_fitz
                if name == "paddleocr":
                    raise AssertionError("high-quality fitz path should not invoke OCR")
                raise ImportError(name)

            import_module.side_effect = side_effect
            decision = import_pdf(Path("/tmp/fake.pdf"))

        self.assertEqual(decision.extraction_method, "fitz")
        self.assertEqual(decision.classification, "TEXT_NATIVE")
        self.assertFalse(decision.degraded)


if __name__ == "__main__":
    unittest.main()
