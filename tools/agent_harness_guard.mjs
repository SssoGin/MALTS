// Per-process Cordis guard for the reviewed MALTS route. No credentials or I/O.
export const name = 'malts-agent-tool-boundary';
export const inject = ['tools'];
export function apply(ctx, config) {
  if (!Array.isArray(config.allowedNames) || config.allowedNames.some(x => typeof x !== 'string')) {
    throw new Error('MALTS requires an explicit tool allow list');
  }
  const names = new Set(config.allowedNames);
  ctx.tools.guard(exec => names.has(exec.name) ? undefined : 'MALTS_AGENT_TOOL_OUTSIDE_CONTRACT');
}
