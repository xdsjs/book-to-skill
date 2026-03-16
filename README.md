# book2skill

把一本书，锻造成一个可安装的技能

`book2skill` 面向的是“把书里的方法、框架、判断规则沉淀为可复用能力”这件事，而不是只做一次性的摘要。它把整件事拆成一条清晰流水线：

`import -> xray -> forge -> validate -> export`

生成结果是一个结构化 skill 包，通常包含：

- `SKILL.md`
- `agents/openai.yaml`
- `references/`
- `skill-spec.json`

目前支持从 Markdown、TXT、EPUB 和 PDF 导入；支持将 canonical skill 包导出为 Claude Code 兼容包。

## 目录

- [为什么有这个项目](#为什么有这个项目)
- [核心特性](#核心特性)
- [整体流程](#整体流程)
- [安装](#安装)
- [快速开始](#快速开始)
- [详细流水线说明](#详细流水线说明)
- [输出结构](#输出结构)
- [设计原则](#设计原则)
- [常见问题](#常见问题)
- [开发与测试](#开发与测试)
- [发布到 PyPI](#发布到-pypi)
- [仓库结构](#仓库结构)
- [许可证](#许可证)

## 为什么有这个项目

很多“拆书”流程最后只得到一篇总结，难以复用。`book2skill` 的目标不是把一本书压成短摘要，而是把其中稳定、可迁移的知识封装成一个 skill，使另一个 agent 在未来面对相似任务时能够：

- 知道何时触发这个 skill
- 知道先读哪些上下文
- 知道按什么工作流执行
- 知道什么边界内可用、什么边界外应当收手

换句话说，它试图把“读过一本书”变成“多次可复用的能力单元”。

## 核心特性

- 标准化流水线：从原始书稿到 skill 包，每一步都有明确输入和输出。
- PDF 分层导入：优先使用文本层，必要时切换到 PaddleOCR 做结构化 OCR。
- 协议化拆书：xray 阶段强制遵循 `ljg-xray-book` 协议，避免随意总结。
- Skill 封装：自动生成 `SKILL.md`、`references/`、`agents/openai.yaml` 和 `skill-spec.json`。
- 质量校验：不仅检查文件是否存在，也检查占位内容、明显的拼接痕迹和关键元数据有效性。
- 平台导出：支持导出 Claude Code 兼容包，且不污染 canonical skill。
- 参考型降级：当原书更偏思想、民俗、史料、文化解释或分类索引时，会优先输出参考型 skill，而不是硬包装成执行型工具。

## 整体流程

```text
原始输入
  |
  v
import
  -> normalized-book.md
  -> import-manifest.json
  |
  v
xray
  -> xray-prompt.md
  -> xray-report-template.md
  -> xray-result.template.json
  -> xray-result.json
  |
  v
forge
  -> SKILL.md
  -> agents/openai.yaml
  -> references/*
  -> skill-spec.json
  |
  v
validate
  -> valid / errors
  |
  v
export
  -> Claude Code bundle
```

## 安装

### 环境要求

- Python `>= 3.9`

### 基础安装

默认安装已经包含：

- `pypdf`
- `PyMuPDF`

因此基础安装后就具备：

- Markdown / TXT / EPUB 导入
- 常规文本型 PDF 导入
- `fitz` / `PyMuPDF` 文本层兜底能力

安装方式：

```bash
pip install -e .
```

如果你是通过 skill 包方式安装，例如：

```bash
tnpm install -g @antskill/book2skill
```

当前 npm 包的 `postinstall` 也会自动尝试安装 Python 基础依赖：

- `pypdf`
- `PyMuPDF`

这样在 Claude Code / skill 安装场景下，文本型 PDF 通常不需要再手工补这两个依赖。

### 可选依赖

仓库已经在 [`pyproject.toml`](/Users/wenqi/Documents/book-to-skill/pyproject.toml) 中定义了可选依赖组：

- `pdf`：占位兼容组，当前默认依赖已包含文本型 PDF 支持
- `pdf-degraded`：占位兼容组，当前默认依赖已包含 `PyMuPDF`
- `pdf-ocr`：安装 `paddleocr`
- `pdf-full`：安装 `paddleocr`

例如：

```bash
pip install -e ".[pdf-full]"
```

如果要处理扫描版 PDF，仍需额外安装 `paddleocr`，并确保本机有可用的 PaddlePaddle 3.x 环境。npm `postinstall` 目前不会自动安装 OCR 依赖。

如果你在中国大陆环境使用 PaddleOCR，建议把“Python 包安装源”和“模型下载源”分开配置：

1. `pip` 安装 `paddleocr` / `paddlex` / 相关依赖时，优先使用清华 PyPI 镜像。
2. 首次运行 `PP-StructureV3` 下载模型时，优先把 PaddleX 模型源切到 `bos` 或 `modelscope`，避免默认源拉取过慢或失败。

可直接参考下面的配置方式。

### 中国大陆环境推荐配置

#### 1. 使用清华 PyPI 镜像安装 Python 依赖

临时使用：

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[pdf-full]"
```

设为默认：

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

如果只想补装 OCR 相关依赖，也可以：

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple paddleocr
```

#### 2. 将 PaddleX 模型下载源切到国内可用源

推荐在运行前设置：

```bash
export PADDLE_PDX_MODEL_SOURCE=bos
```

或者：

```bash
export PADDLE_PDX_MODEL_SOURCE=modelscope
```

然后再执行 `book2skill import ...`。

例如：

```bash
export PADDLE_PDX_MODEL_SOURCE=bos
python3 src/book_to_skill/cli.py import ./book.pdf --out output/book-demo
```

如果希望每次 shell 启动都生效，可以把上面的 `export` 写入 `~/.zshrc` 或 `~/.bashrc`。

## 快速开始

下面是最短可跑通的一条流水线：

```bash
python3 src/book_to_skill/cli.py import ./book.pdf --out output/book-demo
python3 src/book_to_skill/cli.py xray output/book-demo/normalized-book.md --out output/book-demo/xray
# 按协议填写 output/book-demo/xray/xray-report.md
python3 src/book_to_skill/cli.py xray output/book-demo/normalized-book.md --out output/book-demo/xray --report output/book-demo/xray/xray-report.md
python3 src/book_to_skill/cli.py forge output/book-demo/xray/xray-result.json --out output/book-demo/forged --skill-name book-demo-skill
python3 src/book_to_skill/cli.py validate output/book-demo/forged/book-demo-skill
python3 src/book_to_skill/cli.py export --target claude-code output/book-demo/forged/book-demo-skill --out output/book-demo/export
```

安装为命令行工具后，也可以直接使用：

```bash
book2skill --help
book2skill --version
python3 -m book_to_skill --help
```

如果是在 Claude Code 或其他直接执行脚本路径的环境中，也支持：

```bash
python3 /path/to/src/book_to_skill/cli.py --help
```

## 发布到 PyPI

如果你希望别人不拿源码、直接通过 `pip install book2skill` 安装，就需要把它发布到 PyPI。

先在本地构建发布包：

```bash
python3 -m pip install --upgrade build twine
python3 -m build
python3 -m twine check dist/*
```

构建成功后会生成：

- `dist/*.tar.gz`
- `dist/*.whl`

上传到正式 PyPI：

```bash
python3 -m twine upload dist/*
```

如果你想先试发到 TestPyPI：

```bash
python3 -m twine upload --repository testpypi dist/*
```

发布后，其他人就可以直接安装：

```bash
pip install book2skill
```

发布前建议至少检查这几项：

- 包名 `book2skill` 在 PyPI 上尚未被占用
- `README.md` 在 `twine check` 下能正常渲染
- `book2skill --help` 和 `python3 -m book_to_skill --help` 都可用
- 测试通过

## 详细流水线说明

### 1. `import`

作用：把原始输入统一转换为后续可分析的规范化书稿。

支持输入：

- `.md`
- `.markdown`
- `.txt`
- `.pdf`
- `.epub`

基本用法：

```bash
python3 src/book_to_skill/cli.py import <input> --out <workdir>
```

输出文件：

- `normalized-book.md`
- `import-manifest.json`

#### PDF 导入策略

PDF 不是简单“一把梭”提文本，而是按置信度分层：

1. 先尝试 `pypdf` 提取文本层。
2. 如果 `pypdf` 不可用或没有拿到可用结果，再尝试 `fitz` / `PyMuPDF`。
3. 对文本提取结果做质量评估。
4. 如果文本层质量足够高，直接进入 canonical 流程。
5. 如果文本层很差，或几乎没有可用文本，切到 PaddleOCR `PP-StructureV3` 做 OCR 和版面还原。
6. 如果 OCR 不可用或失败，默认报错退出。
7. 只有显式传入 `--allow-degraded-pdf-text` 时，才允许降级到非 OCR 文本提取继续后续流程。

示例：

```bash
python3 src/book_to_skill/cli.py import ./scan.pdf --out output/scan-book --allow-degraded-pdf-text
```

降级模式的关键点：

- 这是“低置信度继续”，不是正常成功路径。
- 风险会写入 `import-manifest.json`。
- 后续 xray 阶段必须显式保留不确定性，而不是假装输入可靠。

### 2. `xray`

作用：生成拆书工作包，并把分析结果收敛到统一语义结构。

第一步先生成工作包：

```bash
python3 src/book_to_skill/cli.py xray <workdir>/normalized-book.md --out <workdir>/xray
```

会生成：

- `xray-prompt.md`
- `xray-report-template.md`
- `xray-result.template.json`

然后按协议填写一份完整报告。这里有一个重要约束：

- 不要直接把 `xray-report-template.md` 当最终报告文件回传
- 请将填写后的结果另存为独立文件，例如 `xray-report.md`

原因是模板文件属于工作包输出，`--report` 需要消费的是“最终填写版报告”，而不是模板本身。

再执行：

```bash
python3 src/book_to_skill/cli.py xray <workdir>/normalized-book.md --out <workdir>/xray --report <workdir>/xray/xray-report.md
```

如果报告里仍有 `-`、`TODO`、`未提供` 一类占位内容，CLI 会直接拒绝生成 `xray-result.json`。

最终生成：

- `xray-result.json`

#### xray 协议来源

拆书语义必须遵循：

- [`references/ljg-xray-book-protocol.md`](/Users/wenqi/Documents/book-to-skill/references/ljg-xray-book-protocol.md)

必填字段包括：

- `core_question`
- `core_answer`
- `chapter_skeleton`
- `argument_chain`
- `key_evidence`
- `hidden_assumptions`
- `boundary_conditions`
- `author_blind_spots`
- `cross_domain_mappings`
- `knowledge_connections`
- `action_triggers`
- `napkin_formula`
- `napkin_diagram_ascii`
- `one_sentence_summary`

#### 为什么 xray 不能省

`xray-result.json` 是后续 `forge` 的唯一事实来源。也就是说：

- `forge` 不应该重新总结原书
- `forge` 只是把 xray 结果封装成 skill
- 如果 xray 写偏了，后面的 skill 也会整体偏掉

### 3. `forge`

作用：把 `xray-result.json` 锻造成标准 skill 包。

用法：

```bash
python3 src/book_to_skill/cli.py forge <workdir>/xray/xray-result.json --out <workdir>/forged --skill-name <skill-name>
```

输出目录通常为：

- `<workdir>/forged/<skill-name>`

典型产物：

- `SKILL.md`
- `agents/openai.yaml`
- `references/core-method.md`
- `references/decision-rules.md`
- `references/patterns.md`
- `skill-spec.json`

锻造规则参考：

- [`references/skill-forging.md`](/Users/wenqi/Documents/book-to-skill/references/skill-forging.md)

#### forge 阶段的重点

- `SKILL.md` 保持简洁，负责告诉 agent 如何使用 skill
- 长内容进入 `references/`
- 不把私有路径、私有服务、个人工作流假设写入公开 skill
- 如果原书执行性弱，就输出参考型 skill，而不是强行输出执行型 skill
- 生成 prose 时会清洗 xray 中的列表标记，避免 `description` 和工作流里出现机械拼接痕迹

### 4. `validate`

作用：对生成结果做最小结构检查。

用法：

```bash
python3 src/book_to_skill/cli.py validate <workdir>/forged/<skill-name>
```

当前会检查：

- 是否存在 `SKILL.md`
- `SKILL.md` frontmatter 是否有 `name`
- `SKILL.md` frontmatter 是否有 `description`
- 是否存在 `agents/openai.yaml`
- 是否存在三份核心 references
- `SKILL.md` / `references` / `skill-spec.json` 是否仍残留占位内容
- `SKILL.md` 是否存在明显的列表标记拼接痕迹
- `skill-spec.json` 的 `mode` 与基础字段是否合法

如果校验失败，会返回错误列表，便于快速定位。

### 5. `export`

作用：将 canonical skill 包导出为目标平台兼容格式。

当前支持：

- `claude-code`

用法：

```bash
python3 src/book_to_skill/cli.py export --target claude-code <workdir>/forged/<skill-name> --out <workdir>/export
```

输出目录通常为：

- `<workdir>/export/claude-code/<skill-name>`

会包含：

- `CLAUDE.md`
- `manifest.json`
- `skills/<skill-name>/...`

导出规则参考：

- [`references/claude-code-export.md`](/Users/wenqi/Documents/book-to-skill/references/claude-code-export.md)

一个关键原则是：导出是 adapter，不修改 canonical source skill。

## 输出结构

一条完整流水线跑完后，工作目录通常类似：

```text
output/book-demo/
├── import-manifest.json
├── normalized-book.md
├── xray/
│   ├── xray-prompt.md
│   ├── xray-report-template.md
│   ├── xray-report.md
│   ├── xray-result.template.json
│   └── xray-result.json
├── forged/
│   └── book-demo-skill/
│       ├── SKILL.md
│       ├── skill-spec.json
│       ├── agents/
│       │   └── openai.yaml
│       └── references/
│           ├── core-method.md
│           ├── decision-rules.md
│           └── patterns.md
└── export/
    └── claude-code/
        └── book-demo-skill/
            ├── CLAUDE.md
            ├── manifest.json
            └── skills/
                └── book-demo-skill/
```

## 设计原则

- xray 优先：`xray-result.json` 是唯一事实来源。
- 封装优先：`SKILL.md` 负责触发和工作流，长内容下沉到 `references/`。
- 公共可移植：输出 skill 不应依赖个人环境。
- 不伪装执行性：思想型、文化型、史料型输入可以产出参考型 skill。
- 显式不确定性：OCR 或 degraded 输入必须把置信度问题带到后续阶段。
- 模板和最终报告分离：模板用来起草，最终报告用独立文件提交给 `--report`。
- 参考型优先于过度包装：当材料本质不是“可执行方法书”时，宁可保守降级，也不输出误导性 operational skill。

## 常见问题

### 为什么不直接从书稿生成 `SKILL.md`？

因为这样很容易把摘要误当方法。`book2skill` 强制加入 `xray` 阶段，就是为了把“观点”“证据”“假设”“边界”“触发器”拆开，避免后续 skill 漂移。

### 什么书适合这个项目？

更适合：

- 非虚构书
- 方法论文档
- 结构化知识手册
- 有清晰框架、判断规则、迁移模式的材料

不太适合：

- 纯小说
- 强依赖文学体验的文本
- 完全没有稳定方法结构的材料

### OCR 成功了，是否就说明文本完全可靠？

不是。OCR 只是让流程能继续，不代表文本没有错字、断句错误、章节误拼接。高风险判断仍然应该在 xray 阶段保留不确定性。

### 什么时候应该输出参考型 skill？

当原书：

- 洞见很多，但步骤不稳定
- 更像思想史或文化解释
- 主要提供分类、视角、判断框架，而不是可重复执行的流程

这时应该明确把 skill 定位成“分析与指导型”或“文化参考型”。

### 为什么生成的 `agents/openai.yaml` 还保留？

因为它承担的是平台适配元数据，而不是知识本体。真正定义 skill 行为的是：

- `SKILL.md`
- `references/*`

而 `agents/openai.yaml` 主要补充：

- 展示名
- 简短描述
- 默认调用提示
- 隐式触发策略

在这个项目里，它仍然属于 canonical skill 结构的一部分，因此 `validate` 会检查它是否存在且格式没有明显退化。

## 开发与测试

查看 CLI 帮助：

```bash
python3 src/book_to_skill/cli.py --help
```

运行测试：

```bash
python3 -m unittest discover -s tests
```

当前测试覆盖了若干关键路径，包括：

- PDF 文本层缺失时切到 PaddleOCR
- OCR 失败时 degraded 模式继续
- Markdown 输入的端到端流程
- `forge / validate / export` 基本行为

测试文件见：

- [`tests/test_cli.py`](/Users/wenqi/Documents/book-to-skill/tests/test_cli.py)

## 仓库结构

```text
.
├── SKILL.md
├── README.md
├── pyproject.toml
├── src/
│   └── book_to_skill/
│       ├── cli.py
│       ├── common.py
│       ├── importers.py
│       ├── xray.py
│       ├── forge.py
│       ├── validate.py
│       └── exporters.py
├── references/
│   ├── ljg-xray-book-protocol.md
│   ├── skill-forging.md
│   └── claude-code-export.md
├── tests/
│   └── test_cli.py
└── output/
```

关键文件：

- [`SKILL.md`](/Users/wenqi/Documents/book-to-skill/SKILL.md)：skill 本体指令
- [`src/book_to_skill/cli.py`](/Users/wenqi/Documents/book-to-skill/src/book_to_skill/cli.py)：CLI 入口与命令装配
- [`src/book_to_skill/importers.py`](/Users/wenqi/Documents/book-to-skill/src/book_to_skill/importers.py)：导入与 PDF/OCR 流程
- [`src/book_to_skill/xray.py`](/Users/wenqi/Documents/book-to-skill/src/book_to_skill/xray.py)：xray 工作包与报告解析
- [`src/book_to_skill/forge.py`](/Users/wenqi/Documents/book-to-skill/src/book_to_skill/forge.py)：skill 锻造逻辑
- [`src/book_to_skill/validate.py`](/Users/wenqi/Documents/book-to-skill/src/book_to_skill/validate.py)：结构与内容校验
- [`src/book_to_skill/exporters.py`](/Users/wenqi/Documents/book-to-skill/src/book_to_skill/exporters.py)：导出适配层
- [`references/ljg-xray-book-protocol.md`](/Users/wenqi/Documents/book-to-skill/references/ljg-xray-book-protocol.md)：拆书协议
- [`references/skill-forging.md`](/Users/wenqi/Documents/book-to-skill/references/skill-forging.md)：锻造规则
- [`references/claude-code-export.md`](/Users/wenqi/Documents/book-to-skill/references/claude-code-export.md)：导出规则

## 许可证

本仓库使用 MIT License，见 [`LICENSE`](/Users/wenqi/Documents/book-to-skill/LICENSE)。
