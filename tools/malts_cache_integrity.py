"""Bounded structural digest of CPython 3.11-3.13 marshal-v4 code data.

No marshal.loads, code object construction or execution of cache bytes. The
compiler-produced structure is the sole expected value. Reference numbering,
immutable-object sharing and frozenset order are serialization details; every
code field, bytecode, constant, name, filename and line/exception table is bound.
Unsupported, cyclic, mutable, truncated and trailing data are rejected.
Layout reference: CPython Python/marshal.c (3.11 and 3.13 branches).
"""
import hashlib,sys

def structural_digest(data):
    if sys.implementation.name!='cpython' or sys.version_info[:2] not in {(3,11),(3,12),(3,13)}:
        raise ValueError('Unqualified cache structure profile')
    if not isinstance(data,bytes) or len(data)>16*1024*1024:raise ValueError('Cache structure byte budget exceeded')
    offset=0;references=[];nodes=0
    def take(count):
        nonlocal offset
        if count<0 or offset+count>len(data):raise ValueError('Truncated cache structure')
        value=data[offset:offset+count];offset+=count;return value
    def integer():return int.from_bytes(take(4),'little',signed=True)
    def sized():return take(integer())
    def digest(tag,*parts):
        h=hashlib.sha256(tag)
        for part in parts:h.update(len(part).to_bytes(4,'little'));h.update(part)
        return h.digest()
    def read(depth=0):
        nonlocal nodes
        nodes+=1
        if depth>200 or nodes>1000000:raise ValueError('Cache structure complexity exceeded')
        raw=take(1)[0];tag=chr(raw&127);slot=None
        if raw&128:slot=len(references);references.append(None)
        if tag=='r':
            if slot is not None:raise ValueError('Invalid reference flag')
            index=integer()
            if not 0<=index<len(references) or references[index] is None:raise ValueError('Cyclic or invalid cache reference')
            return references[index]
        if tag in 'NFT.':value=digest(tag.encode('ascii'))
        elif tag=='i':value=digest(b'int',take(4))
        elif tag=='l':
            count=integer();payload=take(abs(count)*2)
            # Keep compiler integer representation, including sign and digits.
            if any(int.from_bytes(payload[i:i+2],'little')>=32768 for i in range(0,len(payload),2)):raise ValueError('Invalid long digit')
            value=digest(b'long',count.to_bytes(4,'little',signed=True),payload)
        elif tag in 'gy':value=digest(tag.encode('ascii'),take(8 if tag=='g' else 16))
        elif tag=='s':value=digest(b'bytes',sized())
        elif tag in 'utAaZz':
            payload=take(take(1)[0]) if tag in 'Zz' else sized()
            text=payload.decode('ascii' if tag in 'AaZz' else 'utf-8','strict')
            value=digest(b'text',text.encode('utf-8'))
        elif tag in '()>':
            count=take(1)[0] if tag==')' else integer()
            if count<0 or count>len(data)-offset:raise ValueError('Invalid immutable container size')
            items=[read(depth+1) for _ in range(count)]
            if tag=='>':items.sort()
            value=digest(b'frozen' if tag=='>' else b'tuple',*items)
        elif tag=='c':
            header=take(20)  # argcount, posonlyargcount, kwonlyargcount, stacksize, flags
            leading=[read(depth+1) for _ in range(8)]  # code, consts, names, locals names/kinds, filename, name, qualname
            first_line=take(4);trailing=[read(depth+1) for _ in range(2)]
            value=digest(b'code',header,*leading,first_line,*trailing)
        else:raise ValueError('Unsupported cache structure type')
        if slot is not None:references[slot]=value
        return value
    value=read()
    if offset!=len(data):raise ValueError('Trailing cache structure bytes')
    return value
