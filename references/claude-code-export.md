# Claude Code 导出

canonical source 始终是生成出的 skill 目录：

- `SKILL.md`
- `agents/openai.yaml`
- `references/`
- `scripts/`
- `assets/` if present

面向 Claude Code 时，`book2skill` 生成兼容包，而不是修改 canonical 包本身。

## 导出内容

- `skills/<skill-name>/` 下的一份 skill 副本
- 说明导出目标与来源 skill 的 `manifest.json`
- 简短安装与使用说明 `CLAUDE.md`

## 导出规则

- 不要修改 source skill。
- 将 Claude Code 导出视为一层 adapter。
- 说明保持简短、明确。
- 保留复制后 skill 目录中的相对路径结构。
