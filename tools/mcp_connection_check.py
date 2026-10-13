"""Cold stdio connection proof for the lifecycle-owned MCP entry, not a Host reload."""
import asyncio
import json
import sys
from pathlib import Path

async def check(interpreter,launcher,tool_root,version):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    parameters=StdioServerParameters(command=interpreter,args=['-B',launcher,'--tool-root',tool_root],cwd=tool_root)
    async with stdio_client(parameters) as (reader,writer):
        async with ClientSession(reader,writer) as client:
            await client.initialize()
            names={tool.name for tool in (await client.list_tools()).tools}
            if not {'malts_installation','malts_workflow','malts_context','malts_entry_status','malts_verify_task','malts_actions'}.issubset(names) or 'malts_request' in names:
                raise ValueError('MCP tool contract mismatch')
            result=await client.call_tool('malts_installation',{})
            value=result.structuredContent
            if result.isError or value['decision']!='MCP_READY' or value['version']!=version or value['write_enabled']:
                raise ValueError('MCP installation identity mismatch')
            workflow=await client.call_tool('malts_workflow',{'topic':'phase'})
            if workflow.isError or workflow.structuredContent['topic']!='phase':raise ValueError('MCP workflow unavailable')
            return {'status':'PASS','version':version,'tools':sorted(names),'write_enabled':False,
                    'cold_connection_verified':True,'existing_host_reloaded':False}

def main():
    try:
        result=asyncio.run(asyncio.wait_for(check(*sys.argv[1:]),timeout=40))
        print(json.dumps(result));return 0
    except Exception:
        print(json.dumps({'status':'FAIL','error_code':'MCP_CONNECTION_CHECK_FAILED'}));return 2

if __name__=='__main__':raise SystemExit(main())
