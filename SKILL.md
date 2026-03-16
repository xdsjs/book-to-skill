---
name: book2skill
description: 把一本书，锻造成一个可安装的技能。
---

# 拆书成 Skill

分两阶段把一本非虚构书转成可复用 skill：

1. 运行 `xray-book`：用 `ljg-xray-book` 协议拆书。
2. 运行 `skill-forge`：把 xray 结果转成标准 skill 包。

## Commands

发布安装后，优先使用已安装命令：

```bash
book2skill import <input> --out <dir>
book2skill xray <normalized-book> --out <dir>
book2skill xray <normalized-book> --out <dir> --report <filled-report>
book2skill forge <xray-result.json> --out <dir> --skill-name <name>
book2skill validate <skill-dir>
book2skill export --target claude-code <skill-dir> --out <dir>
```

## Development

在源码仓库内调试时，可使用内部模块入口。将 `{baseDir}` 解析为当前 `SKILL.md` 所在目录，然后使用 Python 3：

```bash
python3 -m book_to_skill --help
python3 {baseDir}/src/book_to_skill/cli.py import <input> --out <dir>
python3 {baseDir}/src/book_to_skill/cli.py xray <normalized-book> --out <dir>
python3 {baseDir}/src/book_to_skill/cli.py xray <normalized-book> --out <dir> --report <filled-report>
python3 {baseDir}/src/book_to_skill/cli.py forge <xray-result.json> --out <dir> --skill-name <name>
python3 {baseDir}/src/book_to_skill/cli.py validate <skill-dir>
python3 {baseDir}/src/book_to_skill/cli.py export --target claude-code <skill-dir> --out <dir>
```

## 工作流

### 1. 归一化输入书稿

对 markdown、`.md`、`.txt`、`.pdf` 或 `.epub` 使用 `import`。

PDF 导入默认分两级：

- 先用 `pypdf` 读取原始文本层。
- 如果文本覆盖率高且质量分足够，就直接采用 `pypdf` 结果。
- 如果有文本层但质量差，或几乎无可用文本，则用 PaddleOCR 的 `PP-StructureV3` 做 OCR 与版面还原。
- 如果 OCR 不可用或失败，只有在显式传入 `--allow-degraded-pdf-text` 时，才允许降级到 `fitz` / `PyMuPDF` 之类的非 OCR 提取器继续后续流程。

预期输出：

- `normalized-book.md`
- `import-manifest.json`

如果输入是 PDF 且 `pypdf` 无法提取文本，优先尝试 PaddleOCR。
如果本机没有安装 PaddleOCR，则明确提示用户安装 PaddlePaddle 3.x 与 `paddleocr`。
如果用户允许 degraded 流程，必须把降级信息写入 `import-manifest.json`，并在后续 xray 阶段显式提示低置信度风险，而不是伪装成 canonical 导入。

### 2. 执行 xray 阶段

必须遵循 `ljg-xray-book` 拆书协议。先读：

- `references/ljg-xray-book-protocol.md`

运行 `xray` 生成工作包：

- `xray-prompt.md`
- `xray-report-template.md`
- `xray-result.template.json`

然后按照协议填写报告。报告完成后，再运行 `xray ... --report ...`，生成 `xray-result.json`。

这些语义字段不能缺：

- core question
- core answer
- chapter skeleton
- argument chain
- key evidence
- hidden assumptions
- boundary conditions
- author blind spots
- cross-domain mappings
- knowledge connections
- action triggers
- napkin formula
- napkin diagram
- one-sentence summary

### 3. 锻造 skill 包

先读：

- `references/skill-forging.md`

运行 `forge`，从 `xray-result.json` 生成新的 skill 目录。

生成出的 skill 必须满足：

- keep `SKILL.md` concise
- push long content into `references/`
- include `agents/openai.yaml`
- avoid private environment assumptions
- remain usable as a public skill package

### 4. 校验与导出

对生成出的 skill 目录运行 `validate`。

如果要交付给 Claude Code，先读：

- `references/claude-code-export.md`

再运行 `export --target claude-code`，从 canonical skill 包导出 Claude Code 兼容包。

## 质量要求

- 将 xray 输出视为拆书阶段的唯一事实来源。
- 不要把整本书原样塞进 references。
- 如果一本书观点丰富但可执行方法弱，就生成偏参考型的轻量 skill，不要伪装成强执行型 skill。
- 对确定性的文件处理优先用稳定脚本；解释性判断保留在 agent 工作流里。
