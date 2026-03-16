from __future__ import annotations

"""输入导入阶段，负责处理 markdown、txt、pdf、epub 和 PDF OCR 回退流程。"""

import argparse
import ast
import importlib
import json
import re
import statistics
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .common import infer_title_from_markdown, write_json, write_text, ensure_dir


class HtmlToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack.append(tag)
        if tag in {"p", "div", "section", "article"}:
            self.parts.append("\n\n")
        elif tag in {"h1", "h2", "h3", "h4"}:
            level = int(tag[1])
            self.parts.append(f"\n\n{'#' * level} ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        if tag in {"p", "div", "section", "article", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.parts.append(text)

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


@dataclass
class PdfTextCandidate:
    method: str
    text: str
    total_pages: int
    pages_with_text: int
    median_chars: float
    quality_score: float
    warnings: list[str]


@dataclass
class PdfImportDecision:
    text: str
    extraction_method: str
    classification: str
    quality_score: float
    text_layer_detected: bool
    degraded: bool
    warnings: list[str]


def extract_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assess_pdf_text_quality(page_texts: list[str]) -> tuple[float, list[str], int, float]:
    total_pages = len(page_texts)
    if total_pages == 0:
        return 0.0, ["PDF 没有可读取页面。"], 0, 0.0

    non_empty_pages = 0
    non_empty_lengths: list[int] = []
    single_char_lines = 0
    total_lines = 0
    repeated_line_counts: dict[str, int] = {}

    for page in page_texts:
        text = page.strip()
        if text:
            non_empty_pages += 1
            non_empty_lengths.append(len(text))
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        total_lines += len(lines)
        for line in lines:
            if len(line) == 1:
                single_char_lines += 1
            repeated_line_counts[line] = repeated_line_counts.get(line, 0) + 1

    coverage = non_empty_pages / total_pages
    median_chars = float(statistics.median(non_empty_lengths)) if non_empty_lengths else 0.0
    single_char_ratio = (single_char_lines / total_lines) if total_lines else 0.0
    repeated_lines = sum(1 for count in repeated_line_counts.values() if count >= max(3, total_pages // 2))
    repeated_line_ratio = (repeated_lines / len(repeated_line_counts)) if repeated_line_counts else 0.0

    score = min(coverage, 1.0) * 0.45 + min(median_chars / 800.0, 1.0) * 0.45
    score -= min(single_char_ratio, 0.4) * 0.35
    score -= min(repeated_line_ratio, 0.5) * 0.2
    score = max(0.0, min(score, 1.0))

    warnings: list[str] = []
    if coverage < 0.8:
        warnings.append(f"文本覆盖率偏低：{non_empty_pages}/{total_pages} 页包含可提取文本。")
    if median_chars < 200:
        warnings.append(f"每页可提取字符中位数偏低：{int(median_chars)}。")
    if single_char_ratio > 0.2:
        warnings.append("文本中单字断行偏多，可能存在提取顺序或布局问题。")
    if repeated_line_ratio > 0.2:
        warnings.append("重复页眉页脚或噪声文本偏多。")

    return score, warnings, non_empty_pages, median_chars


def extract_pdf_text_with_pypdf(path: Path) -> PdfTextCandidate | None:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError:
        return None

    reader = pypdf.PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    score, warnings, pages_with_text, median_chars = assess_pdf_text_quality(pages)
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    return PdfTextCandidate(
        method="pypdf",
        text=text.strip() + "\n" if text.strip() else "",
        total_pages=len(pages),
        pages_with_text=pages_with_text,
        median_chars=median_chars,
        quality_score=score,
        warnings=warnings,
    )


def extract_pdf_text_with_fitz(path: Path) -> PdfTextCandidate | None:
    try:
        fitz = importlib.import_module("fitz")
    except ImportError:
        return None

    doc = fitz.open(str(path))
    try:
        pages = [page.get_text("text") or "" for page in doc]
    finally:
        doc.close()
    score, warnings, pages_with_text, median_chars = assess_pdf_text_quality(pages)
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    return PdfTextCandidate(
        method="fitz",
        text=text.strip() + "\n" if text.strip() else "",
        total_pages=len(pages),
        pages_with_text=pages_with_text,
        median_chars=median_chars,
        quality_score=score,
        warnings=warnings,
    )


def normalize_ocr_markdown_text(markdown_text: str) -> str:
    text = markdown_text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text + "\n" if text else ""


def extract_markdown_text_fragment(value: object) -> str:
    if isinstance(value, dict):
        text = value.get("markdown_texts", "")
        return text.strip() if isinstance(text, str) else ""

    if isinstance(value, tuple) and value:
        return extract_markdown_text_fragment(value[0])

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text.startswith("{") and "markdown_texts" in text:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return text
            return extract_markdown_text_fragment(parsed)
        return text

    return ""


def merge_markdown_pages(markdown_pages: list[dict[str, object]], pipeline: object) -> str:
    if hasattr(pipeline, "concatenate_markdown_pages"):
        merged = pipeline.concatenate_markdown_pages(markdown_pages)  # type: ignore[attr-defined]
        return normalize_ocr_markdown_text(extract_markdown_text_fragment(merged))

    fragments: list[str] = []
    for item in markdown_pages:
        text = extract_markdown_text_fragment(item)
        if text:
            fragments.append(text)
    return normalize_ocr_markdown_text("\n\n".join(fragments))


def extract_pdf_with_paddleocr(path: Path) -> str:
    try:
        paddleocr = importlib.import_module("paddleocr")
    except ImportError as exc:
        raise RuntimeError(
            "PDF 中没有可提取文本，且未安装 PaddleOCR。"
            "请先安装 PaddlePaddle 3.x 和 paddleocr，再使用 PP-StructureV3 做 OCR 兜底。"
        ) from exc

    if not hasattr(paddleocr, "PPStructureV3"):
        raise RuntimeError("当前 paddleocr 安装中缺少 PPStructureV3，请确认使用的是 PaddleOCR 3.x。")

    pipeline = paddleocr.PPStructureV3()
    output = pipeline.predict(input=str(path))
    markdown_pages: list[dict[str, object]] = []
    for res in output:
        md_info = getattr(res, "markdown", None)
        if isinstance(md_info, dict):
            markdown_pages.append(md_info)

    merged = merge_markdown_pages(markdown_pages, pipeline)
    if not merged.strip():
        raise RuntimeError("PaddleOCR 未能从 PDF 生成可用 Markdown。")
    return merged


def classify_pdf_candidate(candidate: PdfTextCandidate | None) -> tuple[str, bool]:
    if candidate is None:
        return "SCAN_IMAGE", False
    if candidate.pages_with_text == 0 or candidate.quality_score < 0.2:
        return "SCAN_IMAGE", False
    if candidate.quality_score >= 0.7 and candidate.pages_with_text / max(candidate.total_pages, 1) >= 0.8:
        return "TEXT_NATIVE", True
    return "TEXT_POOR", True


def choose_degraded_candidate(path: Path, pypdf_candidate: PdfTextCandidate | None) -> PdfTextCandidate | None:
    candidates = [candidate for candidate in [pypdf_candidate, extract_pdf_text_with_fitz(path)] if candidate is not None]
    candidates = [candidate for candidate in candidates if candidate.text.strip()]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: (candidate.quality_score, len(candidate.text)))


def import_pdf(path: Path, allow_degraded_pdf_text: bool = False) -> PdfImportDecision:
    pypdf_candidate = extract_pdf_text_with_pypdf(path)
    fitz_candidate = extract_pdf_text_with_fitz(path)

    primary_candidate = pypdf_candidate
    primary_method = "pypdf"
    if primary_candidate is None and fitz_candidate is not None:
        primary_candidate = fitz_candidate
        primary_method = "fitz"

    classification, text_layer_detected = classify_pdf_candidate(primary_candidate)

    if classification == "TEXT_NATIVE" and primary_candidate is not None:
        return PdfImportDecision(
            text=primary_candidate.text,
            extraction_method=primary_method,
            classification=classification,
            quality_score=primary_candidate.quality_score,
            text_layer_detected=text_layer_detected,
            degraded=False,
            warnings=primary_candidate.warnings,
        )

    warnings = list(primary_candidate.warnings) if primary_candidate is not None else ["未安装 pypdf 或 PyMuPDF，无法优先检查 PDF 文本层。"]
    try:
        text = extract_pdf_with_paddleocr(path)
        warnings.append("已使用 PaddleOCR 作为正式慢路径恢复 PDF 内容。")
        return PdfImportDecision(
            text=text,
            extraction_method="paddleocr",
            classification=classification,
            quality_score=1.0,
            text_layer_detected=text_layer_detected,
            degraded=False,
            warnings=warnings,
        )
    except RuntimeError as exc:
        warnings.append(str(exc))
        if not allow_degraded_pdf_text:
            raise RuntimeError(
                f"{exc} 如需继续，可显式传入 --allow-degraded-pdf-text 允许降级到非 OCR 文本提取。"
            ) from exc

    degraded_candidate = choose_degraded_candidate(path, pypdf_candidate)
    if degraded_candidate is None:
        raise RuntimeError("OCR 不可用或失败，且当前环境没有可用的非 OCR 降级提取器。")

    warnings.append(f"已降级到 {degraded_candidate.method}，后续 xray/forge 需要显式处理低置信度文本。")
    warnings.extend(item for item in degraded_candidate.warnings if item not in warnings)
    return PdfImportDecision(
        text=degraded_candidate.text,
        extraction_method=degraded_candidate.method,
        classification="DEGRADED_ONLY",
        quality_score=degraded_candidate.quality_score,
        text_layer_detected=text_layer_detected,
        degraded=True,
        warnings=warnings,
    )


def _resolve_epub_opf(zf: zipfile.ZipFile) -> str:
    container = ET.fromstring(zf.read("META-INF/container.xml"))
    rootfile = container.find(".//{*}rootfile")
    if rootfile is None:
        raise RuntimeError("EPUB 的 container.xml 没有定义 rootfile。")
    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise RuntimeError("EPUB rootfile 缺少 full-path。")
    return full_path


def extract_epub(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        opf_path = _resolve_epub_opf(zf)
        opf_root = ET.fromstring(zf.read(opf_path))
        ns = {"opf": opf_root.tag.split("}")[0].strip("{")}
        manifest = {
            item.attrib["id"]: item.attrib["href"]
            for item in opf_root.findall(".//opf:item", ns)
            if "id" in item.attrib and "href" in item.attrib
        }
        spine = [item.attrib["idref"] for item in opf_root.findall(".//opf:itemref", ns) if "idref" in item.attrib]
        base = Path(opf_path).parent
        chunks: list[str] = []
        for item_id in spine:
            href = manifest.get(item_id)
            if not href:
                continue
            raw = zf.read(str((base / href).as_posix()))
            parser = HtmlToMarkdown()
            parser.feed(raw.decode("utf-8", errors="ignore"))
            markdown = parser.markdown().strip()
            if markdown:
                chunks.append(markdown)
        if not chunks:
            raise RuntimeError("EPUB spine 中没有可读取的 XHTML 内容。")
        return "\n\n".join(chunks).strip() + "\n"


def normalize_book_text(text: str, title: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("# "):
        stripped = f"# {title}\n\n{stripped}"
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.rstrip() + "\n"


def command_import(args: argparse.Namespace) -> int:
    source = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    ensure_dir(out_dir)

    suffix = source.suffix.lower()
    if suffix in {".md", ".markdown"}:
        source_type = "markdown"
        raw = extract_markdown(source)
    elif suffix == ".txt":
        source_type = "text"
        raw = extract_text(source)
    elif suffix == ".pdf":
        source_type = "pdf"
        pdf_import = import_pdf(source, allow_degraded_pdf_text=getattr(args, "allow_degraded_pdf_text", False))
        raw = pdf_import.text
    elif suffix == ".epub":
        source_type = "epub"
        raw = extract_epub(source)
    else:
        raise RuntimeError(f"暂不支持的输入类型：{suffix or 'unknown'}")

    title = infer_title_from_markdown(raw, source.stem.replace("-", " ").replace("_", " ").title())
    normalized = normalize_book_text(raw, title)

    normalized_path = out_dir / "normalized-book.md"
    manifest_path = out_dir / "import-manifest.json"

    write_text(normalized_path, normalized)
    manifest_data = {
        "source": str(source),
        "source_type": source_type,
        "title": title,
        "normalized_book": str(normalized_path),
    }
    if suffix == ".pdf":
        manifest_data.update(
            {
                "extraction_method": pdf_import.extraction_method,
                "classification": pdf_import.classification,
                "quality_score": round(pdf_import.quality_score, 4),
                "text_layer_detected": pdf_import.text_layer_detected,
                "ocr_used": pdf_import.extraction_method == "paddleocr",
                "degraded": pdf_import.degraded,
                "recommended_for_xray": True,
                "warnings": pdf_import.warnings,
            }
        )
    write_json(manifest_path, manifest_data)
    print(json.dumps({"normalized_book": str(normalized_path), "manifest": str(manifest_path)}, ensure_ascii=False))
    return 0
