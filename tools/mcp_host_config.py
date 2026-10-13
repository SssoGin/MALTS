"""Preserving editors for the installer-owned `malts` Host entry only."""
import copy
import json
import re
from mcp_config_check import _document,_entries,ConfigError

BEGIN='# MALTS-MCP:BEGIN'
END='# MALTS-MCP:END'

def fingerprint(value):
    import hashlib
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest().upper()

def owned_entry(host,document):
    if host=='claude':
        # Project-specific Claude entries are not this global installer's property.
        return document.get('mcpServers',{}).get('malts')
    rows=[entry for name,entry in _entries(host,document) if name=='malts']
    if len(rows)>1:raise ConfigError('MANAGED_MCP_ENTRY_AMBIGUOUS')
    return rows[0] if rows else None

def document(host,raw):
    if not raw:return [] if host=='deepseek-harness' else {}
    try:return _document(host,raw)
    except ConfigError:raise
    except Exception:
        # YAML parser diagnostics may echo the offending line, including secrets.
        raise ConfigError('HOST_CONFIGURATION_PARSE_FAILED') from None

def _json_form(text):
    return re.sub(r'(?m)^[\t ]*#[^\r\n]*','',text).lstrip().startswith('[')

def _mask_comments(text):
    strings=r'"(?:\\.|[^"\\])*"'
    text=re.sub(r'(?m)^[\t ]*#[^\r\n]*',lambda m:' '*len(m.group()),text)
    return re.sub(strings+r'|//[^\r\n]*|/\*[\s\S]*?\*/',lambda m:m.group() if m.group().startswith('"') else ' '*len(m.group()),text)

def owned_bytes(host,raw):
    data=document(host,raw)
    if owned_entry(host,data) is None:return b''
    text=raw.decode('utf-8-sig')
    if host=='codex' or (host=='deepseek-harness' and not _json_form(text)):
        if text.count(BEGIN)!=1 or text.count(END)!=1:raise ConfigError('MANAGED_MCP_MARKER_INVALID')
        return text[text.index(BEGIN):text.index(END)+len(END)].encode('utf-8')
    spans=_json_spans(text)
    if host=='deepseek-harness':
        for i,node in enumerate(data):
            if not isinstance(node,dict):continue
            for j,row in enumerate(node.get('insert',[])):
                if isinstance(row,dict) and row.get('name')=='@deepseek-ai/dsh-mcp-client' and row.get('config',{}).get('serverName')=='malts':
                    start,end=spans[(i,'insert',j)];return text[start:end].encode('utf-8')
    else:
        key={'claude':'mcpServers','opencode':'mcp'}[host]
        start,end=spans[(key,'malts')];return text[start:end].encode('utf-8')
    raise ConfigError('MANAGED_MCP_ENTRY_AMBIGUOUS')

def _json_spans(text):
    # Keep byte-independent character offsets while masking JSONC comments/commas.
    strings=r'"(?:\\.|[^"\\])*"'
    clean=_mask_comments(text)
    clean=re.sub(strings+r'|,(?=\s*[}\]])',lambda m:m.group(0) if m.group().startswith('"') else ' ',clean)
    decoder=json.JSONDecoder();spans={}
    def skip(i):
        while i<len(clean) and clean[i].isspace():i+=1
        return i
    def value(i,path,depth=0):
        if depth>32:raise ConfigError('CONFIGURATION_DEPTH_BUDGET')
        i=skip(i);start=i
        if clean[i] in '{[':
            is_map=clean[i]=='{';close='}' if is_map else ']';i=skip(i+1);index=0
            while clean[i]!=close:
                if is_map:
                    key,i=decoder.raw_decode(clean,i);i=skip(i)
                    if clean[i]!=':':raise ConfigError('INVALID_JSON_STRUCTURE')
                    i+=1
                else:key=index;index+=1
                i=value(i,(*path,key),depth+1);i=skip(i)
                if clean[i]==',':i=skip(i+1)
                elif clean[i]!=close:raise ConfigError('INVALID_JSON_STRUCTURE')
            i+=1
        else:_,i=decoder.raw_decode(clean,i)
        spans[path]=(start,i);return i
    value(0,());return spans

def _insert_member(text,span,key,value):
    start,end=span;body=text[start+1:end-1]
    # A trailing JSONC comma already separates the added member.
    masked=_mask_comments(body)
    separator='' if not masked.strip() or masked.rstrip().endswith(',') else ','
    fragment=separator+'\n'+json.dumps(key)+': '+json.dumps(value,ensure_ascii=False)+'\n'
    return text[:end-1]+fragment+text[end-1:]

def _patch_json(host,text,data,entry):
    spans=_json_spans(text)
    if host=='deepseek-harness':
        row={'id':'malts-default','name':'@deepseek-ai/dsh-mcp-client','config':entry}
        selected=[]
        for i,patch in enumerate(data):
            if not isinstance(patch,dict):continue
            for j,node in enumerate(patch.get('insert',[])):
                if isinstance(node,dict) and node.get('name')=='@deepseek-ai/dsh-mcp-client' and node.get('config',{}).get('serverName')=='malts':selected.append((i,'insert',j))
        if selected:
            if len(selected)!=1:raise ConfigError('MANAGED_MCP_ENTRY_AMBIGUOUS')
            start,end=spans[selected[0]]
            return text[:start]+json.dumps(row,ensure_ascii=False)+text[end:]
        start,end=spans[()];body=text[start+1:end-1]
        separator=',' if data and not _mask_comments(body).rstrip().endswith(',') else ''
        return text[:end-1]+separator+'\n'+json.dumps({'insert':[row]},ensure_ascii=False)+'\n'+text[end-1:]
    key={'claude':'mcpServers','opencode':'mcp'}[host]
    if key not in data:return _insert_member(text,spans[()],key,{'malts':entry})
    if 'malts' not in data[key]:return _insert_member(text,spans[(key,)],'malts',entry)
    start,end=spans[(key,'malts')]
    return text[:start]+json.dumps(entry,ensure_ascii=False)+text[end:]

def patch(host,raw,entry):
    data=document(host,raw);before=copy.deepcopy(data)
    if host=='deepseek-harness':
        for node in data:
            if not isinstance(node,dict):continue
            for row in node.get('insert',[]):
                if isinstance(row,dict) and row.get('id')=='malts-default' and not (
                    row.get('name')=='@deepseek-ai/dsh-mcp-client' and row.get('config',{}).get('serverName')=='malts'):
                    raise ConfigError('CORDIS_PLUGIN_ID_CONFLICT')
    bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text=raw.decode('utf-8-sig');newline='\r\n' if '\r\n' in text else '\n'
    if host=='codex':
        block=BEGIN+'\n[mcp_servers.malts]\ncommand = '+json.dumps(entry['command'])+'\nargs = '+json.dumps(entry['args'])+'\nstartup_timeout_sec = 30.0\n'+END+'\n'
        if BEGIN in text or END in text:
            if text.count(BEGIN)!=1 or text.count(END)!=1:raise ConfigError('MANAGED_MCP_MARKER_INVALID')
            start=text.index(BEGIN);end=text.index(END,start)+len(END)
            if text[end:end+2]=='\r\n':end+=2
            elif text[end:end+1]=='\n':end+=1
            updated=text[:start]+block.replace('\n',newline)+text[end:]
        else:
            if owned_entry(host,data) is not None:raise ConfigError('UNOWNED_MCP_ENTRY_CONFLICT')
            updated=text+(newline if text and not text.endswith(('\n','\r')) else '')+newline+block.replace('\n',newline)
    elif host=='deepseek-harness' and text.lstrip() and not _json_form(text):
        row={'id':'malts-default','name':'@deepseek-ai/dsh-mcp-client','config':entry}
        # Flow JSON is valid YAML. Serialization needs no external parser and
        # preserves a stable after-image across supported safe parser versions.
        block=BEGIN+'\n- '+json.dumps({'insert':[row]},ensure_ascii=False)+'\n'+END+'\n'
        if BEGIN in text or END in text:
            if text.count(BEGIN)!=1 or text.count(END)!=1:raise ConfigError('MANAGED_MCP_MARKER_INVALID')
            start=text.index(BEGIN);end=text.index(END,start)+len(END)
            if text[end:end+2]=='\r\n':end+=2
            elif text[end:end+1]=='\n':end+=1
            updated=text[:start]+block.replace('\n',newline)+text[end:]
        else:
            if owned_entry(host,data) is not None:raise ConfigError('UNOWNED_MCP_ENTRY_CONFLICT')
            updated=text+(newline if text and not text.endswith(('\n','\r')) else '')+newline+block.replace('\n',newline)
    else:
        text=text or ('[]' if host=='deepseek-harness' else '{}')
        updated=_patch_json(host,text,data,entry)
    result=bom+updated.encode('utf-8');after=document(host,result)
    if owned_entry(host,after)!=entry:raise ConfigError('MANAGED_MCP_EDIT_VERIFICATION_FAILED')
    # Preserve all unrelated semantic settings as well as their original text spans.
    def without(value):
        value=copy.deepcopy(value)
        if host=='deepseek-harness':
            remaining=[]
            for node in value:
                if not isinstance(node,dict):remaining.append(node);continue
                if 'insert' not in node:remaining.append(node);continue
                node['insert']=[r for r in node['insert'] if not (isinstance(r,dict) and r.get('name')=='@deepseek-ai/dsh-mcp-client' and r.get('config',{}).get('serverName')=='malts')]
                if node['insert'] or set(node)!={'insert'}:remaining.append(node)
            return remaining
        key={'codex':'mcp_servers','claude':'mcpServers','opencode':'mcp'}[host]
        if key in value:
            value[key].pop('malts',None)
            if not value[key]:value.pop(key)
        return value
    if without(before)!=without(after):raise ConfigError('UNRELATED_CONFIGURATION_CHANGED')
    return result

def remove(host,raw):
    """Remove only the owned entry; retain other settings, comments and BOM."""
    data=document(host,raw)
    if owned_entry(host,data) is None:return raw
    text=raw.decode('utf-8-sig');bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    if host=='codex' or (host=='deepseek-harness' and not _json_form(text)):
        if text.count(BEGIN)!=1 or text.count(END)!=1:raise ConfigError('MANAGED_MCP_MARKER_INVALID')
        start=text.index(BEGIN);end=text.index(END,start)+len(END)
        if text[end:end+2]=='\r\n':end+=2
        elif text[end:end+1]=='\n':end+=1
    else:
        spans=_json_spans(text)
        if host=='deepseek-harness':
            selected=[]
            for i,node in enumerate(data):
                if not isinstance(node,dict):continue
                for j,row in enumerate(node.get('insert',[])):
                    if isinstance(row,dict) and row.get('name')=='@deepseek-ai/dsh-mcp-client' and row.get('config',{}).get('serverName')=='malts':
                        selected.append((i,) if set(node)=={'insert'} and len(node['insert'])==1 else (i,'insert',j))
            if len(selected)!=1:raise ConfigError('MANAGED_MCP_ENTRY_AMBIGUOUS')
            start,end=spans[selected[0]]
        else:
            key={'claude':'mcpServers','opencode':'mcp'}[host];value_start,end=spans[(key,'malts')]
            # This prefix is inside a parsed map; find its exact field token.
            matches=list(re.finditer(r'"malts"\s*:\s*$',text[:value_start]))
            if len(matches)!=1:raise ConfigError('MANAGED_MCP_REMOVE_FORMAT_UNSUPPORTED')
            start=matches[0].start()
        tail=end
        while tail<len(text) and text[tail].isspace():tail+=1
        if text[tail:tail+1]==',':end=tail+1
        else:
            prefix=start
            while prefix>0 and text[prefix-1].isspace():prefix-=1
            if text[prefix-1:prefix]==',':start=prefix-1
    result=bom+(text[:start]+text[end:]).encode('utf-8')
    if owned_entry(host,document(host,result)) is not None:raise ConfigError('MANAGED_MCP_REMOVE_VERIFY_FAILED')
    return result
