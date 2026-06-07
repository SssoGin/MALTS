# 更新 MALTS Release Repository

语言：[English](../UPDATE.md) | [简体中文](UPDATE.md)

更新流程：

1. 从 dry-run 开始。
2. 比较源 MALTS runtime assets 与 release repository。
3. 只同步已批准的公开发布内容。
4. 保持根级 `skills/` 作为唯一公开 skill 来源。
5. 不同步 local handoff output、private release-control state、internal design notes、trial runs、caches、sessions、真实 tool configs、local archives、generated migration packages 或 non-public companion project references。
6. 当本地全局 Agent 指令变化时，只把稳定的 MALTS-relevant public guidance 同步到 adapter examples。保留 public-safe confirmation 和 skill-recommendation rules；排除 personal language defaults、本机路径、private archive paths、private package rules 和 local-only wording。
7. 如果公开 guidance 受到上游项目启发或改写，保持 third-party attribution 当前有效。
8. 更新 `VERSION` 和 `CHANGELOG.md`。
9. 运行敏感内容扫描。
10. 运行 lint checks。
11. commit 前审阅 diff。
12. 使用 GitHub Desktop 或 Git CLI commit 和 push。

release repository 即使仍处于 private visibility，也应保持随时可公开。
