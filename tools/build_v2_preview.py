"""Build an uninstalled local v2 preview with explicit code/schema/reference closure."""
import argparse,ast,hashlib,json,stat,sys
from pathlib import Path
from v2_evidence import _regular_path

ROOT=Path(__file__).resolve().parent.parent


def collect_inputs(root):
    root=Path(root);tools=root/'tools';available={p.stem:p for p in tools.glob('*.py')}
    collected={};todo=['malts_v2','v2_mcp','v2_host_execution','v2_windows_job','v2_process_host','v2_codex_profile']
    def read(path):
        _regular_path(path)
        key=path.relative_to(root).as_posix()
        if key not in collected:collected[key]=path.read_bytes()
        return collected[key]
    while todo:
        module=todo.pop();path=available[module]
        if path.relative_to(root).as_posix() in collected:continue
        for node in ast.walk(ast.parse(read(path).decode('utf-8-sig'))):
            names=([x.name.split('.')[0] for x in node.names] if isinstance(node,ast.Import) else
                   [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
            unknown=set(names)-set(available)-sys.stdlib_module_names-{'mcp','anyio','jsonschema'}
            if unknown:raise ValueError('Unclassified import dependencies: '+', '.join(sorted(unknown)))
            todo.extend(name for name in names if name in available and 'tools/'+name+'.py' not in collected)
    tree=ast.parse(collected['tools/malts_user_contracts.py'].decode('utf-8-sig'))
    constants={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in {'USER_CONTRACTS','LIFECYCLE_INVARIANTS_FILE'}:
                    constants[target.id]=ast.literal_eval(node.value)
    pending=list(constants['USER_CONTRACTS'].values())+[constants['LIFECYCLE_INVARIANTS_FILE']]
    while pending:
        name=pending.pop();path=tools/name
        if Path(name).is_absolute() or '..' in Path(name).parts or ':' in name:raise ValueError('Invalid package schema path')
        if path.relative_to(root).as_posix() in collected:continue
        value=json.loads(read(path).decode('utf-8-sig'))
        nodes=[value]
        while nodes:
            current=nodes.pop()
            if isinstance(current,dict):
                ref=current.get('$ref','')
                if ref and not ref.startswith('#'):
                    if '://' in ref:raise ValueError('External schema reference requires explicit qualification')
                    relative=(Path(name).parent/ref.split('#',1)[0])
                    if relative.is_absolute() or '..' in relative.parts:raise ValueError('Schema reference escapes tools')
                    pending.append(relative.as_posix())
                nodes.extend(current.values())
            elif isinstance(current,list):nodes.extend(current)
    for relative in ('docs/V2_PREVIEW_USAGE.md','docs/zh-CN/V2_PREVIEW_USAGE.md','docs/V2_STATE_CONTRACT.md',
                     'docs/zh-CN/V2_STATE_CONTRACT.md','skills/v2/malts-v2-task-workflow/SKILL.md',
                     'skills/v2/malts-v2-task-workflow/references/task-execution.md',
                     'skills/malts-long-project-workspace-init/references/v2-phase.md',
                     'skills/malts-long-project-workspace-init/references/v2-artifact.md',
                     'skills/malts-long-project-workspace-init/references/v2-recovery.md',
                     'tools/v2_mcp_requirements.txt'):
        read(root/relative)
    if 'tools/v2_compatibility.py' in collected:
        read(root/'runtime/v2_runtime_contract.json')
    return dict(sorted(collected.items()))


def verify_preview(root):
    root=Path(root);_regular_path(root)
    _regular_path(root/'preview-manifest.json')
    manifest=json.loads((root/'preview-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('kind')!='MALTS_V2_MAINTENANCE_PREVIEW' or manifest.get('installable') is not False:
        raise ValueError('Not an uninstalled maintenance preview')
    expected=manifest['files']
    if not {'tools/malts_v2.py','tools/v2_mcp.py','tools/v2_host_execution.py','skills/v2/malts-v2-task-workflow/SKILL.md'}.issubset(expected):raise ValueError('Preview entry points are missing')
    actual=set();pending=[root]
    while pending:
        directory=pending.pop()
        for entry in directory.iterdir():
            info=entry.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Preview cannot contain links or reparse points')
            if stat.S_ISDIR(info.st_mode):pending.append(entry)
            elif stat.S_ISREG(info.st_mode):actual.add(entry.relative_to(root).as_posix())
            else:raise ValueError('Preview contains a non-regular file')
    if actual!={'preview-manifest.json',*expected}:
        raise ValueError('Preview file set differs')
    for relative,record in expected.items():
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts or ':' in relative:raise ValueError('Invalid manifest path')
        target=root/path;_regular_path(target);data=target.read_bytes()
        if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Preview content changed')
    # A self-consistent manifest can still omit a required schema or module.
    # Re-derive the static closure from packaged source; never import its code.
    try:required=collect_inputs(root)
    except (OSError,KeyError,SyntaxError,ValueError) as error:
        raise ValueError('Preview dependency closure is incomplete') from error
    if set(required)!=set(expected):raise ValueError('Preview manifest differs from its required dependency closure')
    checked='tools/v2_compatibility.py' in required
    if checked:
        from v2_compatibility import inspect_contract
        inspect_contract(root)
    return {'result':'PASS','files':len(expected),'installable':False,'dependency_closure_checked':True,'format_contract_checked':checked}


def build_preview(root,destination):
    root=Path(root).absolute();destination=Path(destination).absolute()
    _regular_path(root);_regular_path(destination)
    root=root.resolve()
    if destination.is_relative_to(root) or root.is_relative_to(destination):raise ValueError('Preview and maintenance roots must be separate')
    inputs=collect_inputs(root);destination.mkdir()
    for relative,data in inputs.items():
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as output:output.write(data)
    if any((root/name).read_bytes()!=data for name,data in inputs.items()):raise ValueError('Source changed during capture; retain partial preview')
    manifest={'kind':'MALTS_V2_MAINTENANCE_PREVIEW','installable':False,'published':False,
              'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in inputs.items()},
              'qualification':'Closure capture only; run relocated behavior checks before claiming support'}
    with (destination/'preview-manifest.json').open('x',encoding='utf-8') as output:json.dump(manifest,output,indent=2)
    return verify_preview(destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(build_preview(ROOT,args.destination) if args.apply else
        {'decision':'NOT_APPLIED','files':len(collect_inputs(ROOT)),'installable':False,'writes_performed':False}))
