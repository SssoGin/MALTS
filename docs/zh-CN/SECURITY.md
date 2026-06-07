# 安全与发布卫生

语言：[English](../SECURITY.md) | [简体中文](SECURITY.md)

MALTS 是 workflow system，不应存储私有运行时 secrets。

## 不应提交

- API keys
- tokens
- cookies
- passwords
- credentials
- authorization headers
- local session logs
- memory dumps
- private tool configuration
- real project handoff records
- machine-specific absolute paths

## 发布前扫描

发布或 push 前应运行敏感信息扫描。

建议模式：

```powershell
rg -n "OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|token|secret|password|cookie|Authorization|Bearer|oauth|api_key" .
rg -n "<replace with local user or workspace path patterns before publishing>" .
```

## 允许的公开归属

```text
Copyright (c) 2026 Gin
```
