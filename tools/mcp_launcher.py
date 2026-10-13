"""Stable installed MCP launcher. Resolve the active generation on every start."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

def ordinary(path):
    path=Path(path)
    if not path.is_absolute() or str(path).startswith(('\\\\','//')):
        raise ValueError('LOCAL_ABSOLUTE_PATH_REQUIRED')
    for part in (path,*path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.lstat(),'st_file_attributes',0)&0x400):
            raise ValueError('REPARSE_PATH_REJECTED')
    return path

def active_root(tool_root):
    tool_root=ordinary(tool_root)
    raw=(tool_root/'MALTS_BOOT.md').read_bytes()
    if len(raw)>1048576:raise ValueError('BOOT_BYTE_BUDGET')
    roots=re.findall(r'(?m)^MALTS_ROOT:\s*(.+?)\s*$',raw.decode('utf-8-sig'))
    if len(roots)!=1:raise ValueError('BOOT_IDENTITY_AMBIGUOUS')
    generation=ordinary(roots[0]);lifecycle=generation.parent.parent
    if generation.parent.name!='generations':raise ValueError('GENERATION_LAYOUT_INVALID')
    registry=json.loads((ordinary(lifecycle/'registry/installation_registry.json')).read_text('utf-8-sig'))
    pointer=json.loads((ordinary(lifecycle/'registry/active_generation.json')).read_text('utf-8-sig'))
    rows=[r for r in registry['generations'] if r['state']=='active']
    if (registry['lifecycle_state']!='stable' or len(rows)!=1 or
            registry['active_generation_id']!=generation.name or pointer['generation_id']!=generation.name):
        raise ValueError('ACTIVE_IDENTITY_CONFLICT')
    version=(ordinary(generation/'VERSION')).read_text('utf-8-sig').strip()
    for row in (rows[0],pointer):
        if (os.path.normcase(os.path.abspath(row['root']))!=os.path.normcase(str(generation)) or
                row['version']!=version or row['artifact_sha256']!=rows[0]['artifact_sha256']):
            raise ValueError('ACTIVE_IDENTITY_CONFLICT')
    return generation

def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self,message):
            self.exit(2,json.dumps({'decision':'ERROR','error_code':'CLI_ARGUMENTS'})+'\n')
    parser=SafeParser(add_help=False)
    parser.add_argument('--tool-root',required=True);parser.add_argument('--probe',action='store_true')
    try:
        args=parser.parse_args()
        root=active_root(args.tool_root)
        ordinary(root/'tools/mcp_entry.py')
        sys.path.insert(0,str(root/'tools'))
        from malts_lifecycle import resolve_discovery,verify_installed_generation_envelope
        discovery=resolve_discovery(args.tool_root)
        verify_installed_generation_envelope(root)
        from mcp_entry import run
        return run(args.tool_root,discovery,probe=args.probe)
    except Exception:
        # Neither command arguments, configuration bytes nor private paths enter stderr.
        print(json.dumps({'decision':'ERROR','error_code':'MCP_STARTUP_FAILED'}),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
