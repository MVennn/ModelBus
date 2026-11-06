# memories/ —— 本仓记忆快照

> **一句话**：这里放**只靠读代码和文档读不出来的事实** —— 踩过的坑、根因、实测结论；
> 它是 dsh-mnemon 中「项目记忆：ModelBus」Document 的**随 git 版本化快照**，可 diff、可回溯。

## 正本与路由

- 长期记忆正本在 `~/.mnemon`（dsh-mnemon Documents，一篇一仓、按项目归篇）；全局共享教训归 `_shared` 篇。
- 路由表与按需加载口径见 `~/.dsh/skills/on-demand/DOCUMENTS-ROUTING.md`；热条目只留「结论 + 指针」。
- 记忆与代码/实测冲突时**以代码为准**，并回写记忆；改完跑 `node ~/.dsh/tools/check-memory-hygiene.mjs`。

## 约定

- 一条一件事，一个文件，文件名 kebab-case；开头写**结论**，不写流水账。
- 敏感值一律 `<REDACTED-...>` / `<REPLACE-...>` 占位符；真值在设备或环境变量里。
- 新增后同步更新 [MEMORY.md](MEMORY.md) 索引；跨仓共用的事实不要在本仓复制，写进 `_shared`。

## 本仓记忆

见 [MEMORY.md](MEMORY.md)。

> 仓库可见性：**公开** —— 理由见根 [README.md](../README.md) 的「可见性」段。
