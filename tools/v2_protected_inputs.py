"""Protected payload storage primitive, not a capture/authorization decision.

The trusted caller must approve capture and enforce owner/purpose access before
using this primitive. No plaintext fallback, global key file, or exported key.
Current implemented profile: Windows current-user DPAPI. Other Host profiles
must supply a qualified implementation rather than silently storing plaintext.
"""
import base64,ctypes,hashlib,json,os,re,uuid
from pathlib import Path
from v2_evidence import _regular_path

PROFILE='WINDOWS_DPAPI_CURRENT_USER'
MAX_BYTES=16*1024*1024
MAX_CIPHER_BYTES=32*1024*1024
CONTEXT_FIELDS={'owner','task_id','task_revision','operation_id','grant_id','actor'}
RECORD_FIELDS={'record_id','record_binding'}
CONTROL_FIELDS={'owner','record_type','record_id','record_revision','field','binding_sha256'}


class ProtectedInputError(ValueError):pass


def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def _context(value):
    if isinstance(value,dict) and set(value)==CONTROL_FIELDS:
        if type(value['record_revision']) is not int or value['record_revision']<0:raise ProtectedInputError('Invalid protected control revision')
        for key in CONTROL_FIELDS-{'record_revision'}:
            if not isinstance(value[key],str) or not value[key].strip() or len(value[key])>256:raise ProtectedInputError('Invalid protected control binding')
        return dict(value)
    if not isinstance(value,dict) or set(value) not in (CONTEXT_FIELDS,CONTEXT_FIELDS|RECORD_FIELDS):raise ProtectedInputError('Invalid protected input context')
    if type(value['task_revision']) is not int or value['task_revision']<1:raise ProtectedInputError('Invalid protected input revision')
    for key in set(value)-{'task_revision'}:
        if not isinstance(value[key],str) or not value[key].strip() or len(value[key])>256:raise ProtectedInputError('Invalid protected input binding')
    return dict(value)


def _dpapi(data,entropy,*,decrypt=False):
    if os.name!='nt':raise ProtectedInputError('No qualified protected input provider for this Host')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    raw=ctypes.create_string_buffer(data);binding=ctypes.create_string_buffer(entropy)
    source=Blob(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte)))
    extra=Blob(len(entropy),ctypes.cast(binding,ctypes.POINTER(ctypes.c_ubyte)));output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    try:
        # UI_FORBIDDEN only: deliberately do not use LOCAL_MACHINE or plaintext descriptions.
        if not fn(ctypes.byref(source),None,ctypes.byref(extra),None,None,1,ctypes.byref(output)):
            raise ProtectedInputError('Protected input provider rejected data or context')
        if output.size>MAX_CIPHER_BYTES:raise ProtectedInputError('Protected input provider output exceeds limit')
        return ctypes.string_at(output.data,output.size)
    finally:
        if output.data:kernel.LocalFree(output.data)
        ctypes.memset(raw,0,len(raw))
        # Python immutable byte copies are not guaranteed to be securely erased.


class ProtectedInputs:
    def __init__(self,root,*,readonly=False):
        self.root=Path(root).absolute();_regular_path(self.root);self.readonly=readonly

    def _path(self,identity):
        if not isinstance(identity,str) or re.fullmatch('[0-9a-f]{32}',identity) is None:
            raise ProtectedInputError('Invalid opaque input identity')
        path=self.root/(identity+'.bin');_regular_path(path);return path

    def capture(self,data,*,context):
        if self.readonly:raise PermissionError('Protected input store is read-only')
        reference,cipher=seal(data,context=context)
        self.root.mkdir(mode=0o700,exist_ok=True);_regular_path(self.root)
        path=self._path(reference['id'])
        with path.open('xb') as output:output.write(cipher);output.flush();os.fsync(output.fileno())
        if self.load(reference,context=context)!=data:raise ProtectedInputError('Protected input readback failed')
        return reference

    def load(self,reference,*,context):
        validate_reference(reference)
        with self._path(reference['id']).open('rb') as source:cipher=source.read(MAX_CIPHER_BYTES+1)
        return open_sealed(cipher,reference,context=context)


def seal(data,*,context):
    if not isinstance(data,bytes) or len(data)>MAX_BYTES:raise ProtectedInputError('Invalid protected input size')
    context=_context(context);identity=uuid.uuid4().hex
    entropy=_json({'purpose':'malts-operation-input-v1','id':identity,'context':context})
    # The plaintext checksum is itself encrypted, never exposed as a lookup key.
    envelope=_json({'context':context,'data':base64.b64encode(data).decode('ascii'),'sha256':hashlib.sha256(data).hexdigest()})
    cipher=_dpapi(envelope,entropy)
    reference={'format':1,'id':identity,'profile':PROFILE,'cipher_sha256':hashlib.sha256(cipher).hexdigest(),'cipher_bytes':len(cipher)}
    if open_sealed(cipher,reference,context=context)!=data:raise ProtectedInputError('Protected input readback failed')
    return reference,cipher


def validate_reference(reference):
    if not isinstance(reference,dict) or set(reference)!={'format','id','profile','cipher_sha256','cipher_bytes'}:
        raise ProtectedInputError('Invalid protected input reference')
    if type(reference['format']) is not int or reference['format']!=1 or reference['profile']!=PROFILE:
        raise ProtectedInputError('Unsupported protected input profile')
    if type(reference['cipher_bytes']) is not int or not 0<reference['cipher_bytes']<=MAX_CIPHER_BYTES:
        raise ProtectedInputError('Invalid ciphertext size')
    if not isinstance(reference['id'],str) or re.fullmatch('[0-9a-f]{32}',reference['id']) is None:
        raise ProtectedInputError('Invalid opaque input identity')
    if not isinstance(reference['cipher_sha256'],str) or re.fullmatch('[0-9a-f]{64}',reference['cipher_sha256']) is None:
        raise ProtectedInputError('Invalid ciphertext identity')


def open_sealed(cipher,reference,*,context):
    context=_context(context)
    validate_reference(reference)
    if len(cipher)!=reference['cipher_bytes'] or hashlib.sha256(cipher).hexdigest()!=reference['cipher_sha256']:
        raise ProtectedInputError('Protected input ciphertext changed')
    entropy=_json({'purpose':'malts-operation-input-v1','id':reference['id'],'context':context})
    raw=_dpapi(cipher,entropy,decrypt=True)
    try:
        envelope=json.loads(raw)
        if set(envelope)!={'context','data','sha256'} or envelope['context']!=context:raise ValueError()
        data=base64.b64decode(envelope['data'],validate=True)
        if len(data)>MAX_BYTES or hashlib.sha256(data).hexdigest()!=envelope['sha256']:raise ValueError()
        return data
    except (ValueError,TypeError,KeyError):raise ProtectedInputError('Protected input envelope is invalid') from None
