"""Lexical edits of one selected native entry; unrelated data and bytes stay intact."""
import copy
import json
import re
from mcp_config_check import ConfigError
from mcp_host_config import document as _document
from mcp_host_config import _json_spans, _mask_comments, _json_form


def at(data,pointer):
    for key in pointer: data=data[key]
    return data


def replace(data,pointer,entry):
    parent=at(data,pointer[:-1]);key=pointer[-1]
    if entry is None:
        if isinstance(parent,list): parent.pop(key)
        else: parent.pop(key)
    else: parent[key]=entry


def json_edit(text,pointer,entry):
    spans=_json_spans(text);start,end=spans[tuple(pointer)]
    if entry is not None: return text[:start]+json.dumps(entry,ensure_ascii=False)+text[end:]
    clean=_mask_comments(text)
    if isinstance(pointer[-1],str):
        parent_start=spans[tuple(pointer[:-1])][0]
        match=re.search(r'"(?:\\.|[^"\\])*"\s*:\s*$',clean[parent_start+1:start])
        if not match: raise ConfigError('PROJECT_MEMBER_LAYOUT_UNSUPPORTED')
        start=parent_start+1+match.start()
    following=end
    while following<len(clean) and clean[following].isspace():following+=1
    if following<len(clean) and clean[following]==',':
        # Keep comment bytes between the value and its separator.
        return text[:start]+text[end:following]+text[following+1:]
    preceding=start-1
    while preceding>=0 and clean[preceding].isspace():preceding-=1
    if preceding>=0 and clean[preceding]==',': return text[:preceding]+text[preceding+1:start]+text[end:]
    return text[:start]+text[end:]


def yaml_edit(text,pointer,entry):
    import yaml
    node=yaml.compose(text,Loader=yaml.SafeLoader);parent=None
    for key in pointer:
        parent=node
        if isinstance(key,int):node=node.value[key]
        else:
            matches=[value for name,value in node.value if name.value==key]
            if len(matches)!=1:raise ConfigError('PROJECT_YAML_POINTER_AMBIGUOUS')
            node=matches[0]
    start,end=node.start_mark.index,node.end_mark.index
    if entry is not None:
        # A block mapping can safely be replaced by a flow mapping. Preserve
        # all bytes outside the selected value and its final line separator.
        newline='\r\n' if '\r\n' in text else '\n'
        suffix=newline+' '*node.end_mark.column if node.end_mark.line>node.start_mark.line else ''
        return text[:start]+json.dumps(entry,ensure_ascii=False)+suffix+text[end:]
    if isinstance(parent,yaml.nodes.SequenceNode) and len(parent.value)==1 and not parent.flow_style:
        start,end=parent.start_mark.index,parent.end_mark.index
        newline='\r\n' if '\r\n' in text else '\n'
        suffix=newline+' '*parent.end_mark.column if parent.end_mark.line>parent.start_mark.line else ''
        return text[:start]+'  []'+suffix+text[end:]
    line=text.rfind('\n',0,start)+1
    prefix=text[line:start]
    if not re.fullmatch(r'[ \t]*-[ \t]*',prefix):raise ConfigError('PROJECT_YAML_REMOVAL_LAYOUT_UNSUPPORTED')
    return text[:line]+text[end:]


def edit(host,raw,pointer,entry,*,remove_pointer=None):
    if host=='codex':
        from mcp_project import edit_entry
        return edit_entry(raw,pointer[-1],entry)
    before=_document(host,raw);expected=copy.deepcopy(before)
    selected=tuple(remove_pointer or pointer) if entry is None else tuple(pointer)
    replace(expected,selected,entry)
    text=raw.decode('utf-8-sig')
    if host=='deepseek-harness' and not _json_form(text):result=yaml_edit(text,selected,entry)
    else:result=json_edit(text,selected,entry)
    raw_after=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+result.encode('utf-8')
    if _document(host,raw_after)!=expected:raise ConfigError('UNRELATED_CONFIGURATION_CHANGED')
    return raw_after
