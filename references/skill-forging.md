# Skill 锻造规则

将 `xray-result.json` 转成公开可分发的 skill 包。

## 映射规则

- `core_question` + `core_answer`：定义 skill 的核心使命与触发描述
- `chapter_skeleton`：决定 `references/core-method.md` 的主结构
- `argument_chain` + `key_evidence`：写入 `references/core-method.md`，作为方法背后的理由
- `hidden_assumptions` + `boundary_conditions`：进入 `references/decision-rules.md`
- `author_blind_spots` + `cross_domain_mappings` + `knowledge_connections`：进入 `references/patterns.md`
- `action_triggers`：转成 checklist、模板或输出要求
- 餐巾纸产物：作为生成 skill 的最短身份摘要

## 封装规则

- 控制 `SKILL.md` 篇幅，不要把整本书的笔记都塞进去。
- 较长内容放进 `references/`。
- `scripts/` 只用于生成 skill 后仍会反复用到的确定性文件操作。
- 保持生成 skill 的公开性与可移植性。
- 避免依赖私有文件系统、私有服务或个人工作流假设。
- 如果输入来自 OCR，优先保留结构化 Markdown，而不是退回到纯文本拼接。

## 何时降级

出现以下情况时，生成偏参考型的轻量 skill：

- 书有洞见，但方法并不成型
- action triggers 很模糊
- 论证主要是描述性或历史性
- 无法提炼出可交给另一个 agent 的稳定执行循环

此时，生成出的 `SKILL.md` 应该把 skill 定位成分析与指导型 skill，而不是重自动化的执行型 skill。
