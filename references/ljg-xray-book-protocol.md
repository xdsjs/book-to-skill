# ljg-xray-book 协议

`book2skill` 使用 `ljg-xray-book` 作为拆书分析层。规范来源：

- https://github.com/lijigang/ljg-skill-xray-book/blob/master/skills/ljg-xray-book/SKILL.md

如果输入是扫描版 PDF，允许先使用 PaddleOCR 的 PP-StructureV3 将 PDF 转成结构化 Markdown，再进入本协议。

## 必需的分析轮次

### Round 1：骨架扫描

需要产出：

- Core question
- Core answer
- Chapter skeleton
- Argument structure or argument type

### Round 2：血肉解剖

需要产出：

- Argument chain
- Key evidence
- Hidden assumptions
- Boundary conditions

### Round 3：灵魂提取

需要产出：

- Author blind spots
- Cross-domain mappings
- Knowledge connections
- Action triggers

### 餐巾纸压缩

必须产出：

- Napkin formula
- Napkin diagram
- One-sentence summary

## 输出纪律

- 即使最终报告不是 `.org` 而是 markdown，也要完整保留语义字段。
- 每个字段都要控制长度，保证能被 skill 继续复用。
- 优先使用列表和紧凑段落，不要写成长篇散文。
- 将证据与解释分开。
- 当书中表述存在歧义时，明确标注不确定性。

## 这样做的原因

这个协议是认知压缩层。`book2skill` 不应该再发明另一套竞争性的总结方法，而应该把这份分析转译为：

- skill 触发条件
- 可执行工作流
- 决策规则
- 可复用 references
- 面向公开分发的封装元数据
