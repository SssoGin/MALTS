"""Static format/interface declarations; never installation or write authority."""
import ast,hashlib,json
from pathlib import Path
from v2_state_store import SCHEMA_VERSION,APPLICATION_ID
from v2_legacy_reader import read_source_bytes

CLI_INTERFACE_VERSION=1
MCP_APPLICATION_INTERFACE_VERSION=7
CONTRACT_PATH='runtime/v2_runtime_contract.json'


def current_contract():
    return {'format':'malts.runtime-compatibility','version':1,'core_application_id':APPLICATION_ID,
        'read_schemas':[SCHEMA_VERSION],'write_schemas':[SCHEMA_VERSION],
        'cli_interface_version':CLI_INTERFACE_VERSION,'mcp_application_interface_version':MCP_APPLICATION_INTERFACE_VERSION,
        'assurance':'DECLARATION_NOT_RUNTIME_QUALIFICATION'}


def _constant(data,name):
    try:
        tree=ast.parse(data.decode('utf-8-sig'))
        values=[ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and
            any(isinstance(target,ast.Name) and target.id==name for target in node.targets)]
        if len(values)!=1 or type(values[0]) is not int:raise ValueError()
        return values[0]
    except (SyntaxError,UnicodeError,ValueError,TypeError):raise ValueError('Unsupported compatibility constant declaration') from None


def inspect_contract(root):
    """Inspect declared inputs without importing or executing packaged code."""
    root=Path(root)
    record=read_source_bytes(root,CONTRACT_PATH,max_bytes=16384)
    inputs={CONTRACT_PATH:record}
    for path in ('tools/v2_state_store.py','tools/v2_compatibility.py'):
        inputs[path]=read_source_bytes(root,path,max_bytes=2097152)
    state_code=inputs['tools/v2_state_store.py']['raw_bytes']
    interface_code=inputs['tools/v2_compatibility.py']['raw_bytes']
    def unique(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate compatibility field')
            result[key]=value
        return result
    declared=json.loads(record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=unique)
    expected={'format':'malts.runtime-compatibility','version':1,
        'core_application_id':_constant(state_code,'APPLICATION_ID'),
        'read_schemas':[_constant(state_code,'SCHEMA_VERSION')],
        'write_schemas':[_constant(state_code,'SCHEMA_VERSION')],
        'cli_interface_version':_constant(interface_code,'CLI_INTERFACE_VERSION'),
        'mcp_application_interface_version':_constant(interface_code,'MCP_APPLICATION_INTERFACE_VERSION'),
        'assurance':'DECLARATION_NOT_RUNTIME_QUALIFICATION'}
    if (not isinstance(declared,dict) or declared!=expected or
            any(type(declared.get(k)) is not int for k in ('version','core_application_id','cli_interface_version','mcp_application_interface_version')) or
            any(not isinstance(declared.get(k),list) or any(type(v) is not int for v in declared[k]) for k in ('read_schemas','write_schemas'))):
        raise ValueError('Compatibility declaration differs from code or has an unsupported shape')
    for path,before in inputs.items():
        after=read_source_bytes(root,path,max_bytes=16384 if path==CONTRACT_PATH else 2097152)
        if after['sha256']!=before['sha256']:raise ValueError('Compatibility inputs changed during inspection')
    return {'decision':'DECLARATION_ALIGNED','contract':declared,'declaration_sha256':record['sha256'],
        'input_sha256':{path:value['sha256'] for path,value in inputs.items()},'atomic_snapshot':False,
        'alignment':'STATIC_CONSTANTS','packaged_code_executed':False,'runtime_behavior_verified':False,
        'installation_authorized':False,'writes_performed':False}
