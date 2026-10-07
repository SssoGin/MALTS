# MALTS projection for DeepSeek Harness

Research baseline: prerelease `dsh-v0.2.0-rc.2`, commit
`639ed015397290b3745d163aafe02ffee4aa3f84`. This projection is not evidence of
Desktop or model qualification. See the maintained v2 usage guide and Host matrix.

Select the actual `DSH_HOME` as the lifecycle tool root. Its default is `.dsh`
under the user's home. MALTS installs its managed `AGENTS.md` block,
`MALTS_BOOT.md` discovery pointer and `skills/malts-*/SKILL.md` bridges there.
Preserve the user's instruction content outside the managed block.

Desktop's plugin profile is `DSH_HOME/profiles/desktop`. CLI and Web profiles
are distinct. Do not put OpenCode JSON or Codex TOML into this profile. Desktop
does not enable the MCP client by default in the pinned baseline. The controller
`mcp-config --host deepseek-harness` emits a Cordis patch fragment for
`@deepseek-ai/dsh-mcp-client`; review and merge it with the existing profile's
`cordis.patch.yml` under the appropriate authorization. Do not replace the user's
whole patch or assume a fragment installs its plugin dependency.

Project `.dsh/skills` and `.agents/skills` are separate search roots. Do not also
copy the same MALTS bridges there automatically. Verify actual Desktop discovery,
plugin resolution, tool execution and resumed task behavior before claiming this
Host is qualified. A Chrome-installed Web PWA is not the native Desktop product.
