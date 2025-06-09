###     ###
# 导入 #
###     ###

import datetime, os, plistlib, struct, sys, itertools, binascii
from io import BytesIO

if sys.version_info < (3,0):
    # 强制使用 StringIO 而不是 cStringIO，因为后者在处理 Unicode 字符串时有问题
    from StringIO import StringIO
else:
    from io import StringIO

try:
    basestring  # Python 2
    unicode
except NameError:
    basestring = str  # Python 3
    unicode = str

try:
    FMT_XML = plistlib.FMT_XML
    FMT_BINARY = plistlib.FMT_BINARY
except AttributeError:
    FMT_XML = "FMT_XML"
    FMT_BINARY = "FMT_BINARY"

###            ###
# 辅助方法 #
###            ###

def wrap_data(value):
    if not _check_py3(): return plistlib.Data(value)
    return value

def extract_data(value):
    if not _check_py3() and isinstance(value,plistlib.Data): return value.data
    return value

def _check_py3():
    return sys.version_info >= (3, 0)

def _is_binary(fp):
    if isinstance(fp, basestring):
        return fp.startswith(b"bplist00")
    header = fp.read(32)
    fp.seek(0)
    return header[:8] == b'bplist00'

###                             ###
# 已弃用函数 - 重映射 #
###                             ###

def readPlist(pathOrFile):
    if not isinstance(pathOrFile, basestring):
        return load(pathOrFile)
    with open(pathOrFile, "rb") as f:
        return load(f)

def writePlist(value, pathOrFile):
    if not isinstance(pathOrFile, basestring):
        return dump(value, pathOrFile, fmt=FMT_XML, sort_keys=True, skipkeys=False)
    with open(pathOrFile, "wb") as f:
        return dump(value, f, fmt=FMT_XML, sort_keys=True, skipkeys=False)

###                ###
# 重映射函数 #
###                ###

def load(fp, fmt=None, use_builtin_types=None, dict_type=dict):
    if _is_binary(fp):
        use_builtin_types = False if use_builtin_types is None else use_builtin_types
        try:
            p = _BinaryPlistParser(use_builtin_types=use_builtin_types, dict_type=dict_type)
        except:
            # Python 3.9 移除了 use_builtin_types
            p = _BinaryPlistParser(dict_type=dict_type)
        return p.parse(fp)
    elif _check_py3():
        use_builtin_types = True if use_builtin_types is None else use_builtin_types
        # 我们需要修补此函数以支持十六进制整数 - 代码修改自:
        # https://github.com/python/cpython/blob/3.8/Lib/plistlib.py
        if fmt is None:
            header = fp.read(32)
            fp.seek(0)
            for info in plistlib._FORMATS.values():
                if info['detect'](header):
                    P = info['parser']
                    break
            else:
                raise plistlib.InvalidFileException("无效文件")
        else:
            P = plistlib._FORMATS[fmt]['parser']
        try:
            p = P(use_builtin_types=use_builtin_types, dict_type=dict_type)
        except:
            # Python 3.9 移除了 use_builtin_types
            p = P(dict_type=dict_type)
        if isinstance(p,plistlib._PlistParser):
            # 修补函数!
            def end_integer():
                d = p.get_data()
                value = int(d,16) if d.lower().startswith("0x") else int(d)
                if -1 << 63 <= value < 1 << 64:
                    p.add_object(value)
                else:
                    raise OverflowError(f"整数溢出，行号 {p.parser.CurrentLineNumber}")
            def end_data():
                try:
                    p.add_object(plistlib._decode_base64(p.get_data()))
                except Exception as e:
                    raise Exception(f"数据错误，行号 {p.parser.CurrentLineNumber}: {e}")
            p.end_integer = end_integer
            p.end_data = end_data
        return p.parse(fp)
    else:
        # 不是二进制 - 假定为字符串 - 并尝试加载
        # 避免使用 readPlistFromString() 因为它使用 cStringIO 并在检测到 Unicode 字符串时会失败
        # 不要子类化 - 保持解析器本地化
        from xml.parsers.expat import ParserCreate
        # 创建新的 PlistParser 对象 - 然后需要设置值并解析
        p = plistlib.PlistParser()
        parser = ParserCreate()
        parser.StartElementHandler = p.handleBeginElement
        parser.EndElementHandler = p.handleEndElement
        parser.CharacterDataHandler = p.handleData
        # 还需要修补此函数以支持其他 dict_types、十六进制整数支持、数据错误的正确行输出和 Unicode 字符串解码
        def begin_dict(attrs):
            d = dict_type()
            p.addObject(d)
            p.stack.append(d)
        def end_integer():
            d = p.getData()
            value = int(d,16) if d.lower().startswith("0x") else int(d)
            if -1 << 63 <= value < 1 << 64:
                p.addObject(value)
            else:
                raise OverflowError(f"整数溢出，行号 {parser.CurrentLineNumber}")
        def end_data():
            try:
                p.addObject(plistlib.Data.fromBase64(p.getData()))
            except Exception as e:
                raise Exception(f"数据错误，行号 {parser.CurrentLineNumber}: {e}")
        def end_string():
            d = p.getData()
            if isinstance(d,unicode):
                d = d.encode("utf-8")
            p.addObject(d)
        p.begin_dict = begin_dict
        p.end_integer = end_integer
        p.end_data = end_data
        p.end_string = end_string
        if isinstance(fp, unicode):
            # 编码 unicode -> string; 为安全使用 utf-8
            fp = fp.encode("utf-8")
        if isinstance(fp, basestring):
            # 是字符串 - 包装起来
            fp = StringIO(fp)
        # 解析
        parser.ParseFile(fp)
        return p.root

def loads(value, fmt=None, use_builtin_types=None, dict_type=dict):
    if _check_py3() and isinstance(value, basestring):
        # 如果是字符串 - 编码它
        value = value.encode()
    try:
        return load(BytesIO(value),fmt=fmt,use_builtin_types=use_builtin_types,dict_type=dict_type)
    except:
        # Python 3.9 移除了 use_builtin_types
        return load(BytesIO(value),fmt=fmt,dict_type=dict_type)

def dump(value, fp, fmt=FMT_XML, sort_keys=True, skipkeys=False):
    if fmt == FMT_BINARY:
        # 此时假定为二进制
        writer = _BinaryPlistWriter(fp, sort_keys=sort_keys, skipkeys=skipkeys)
        writer.write(value)
    elif fmt == FMT_XML:
        if _check_py3():
            plistlib.dump(value, fp, fmt=fmt, sort_keys=sort_keys, skipkeys=skipkeys)
        else:
            # 还需要修补一堆以避免键自动排序
            writer = plistlib.PlistWriter(fp)
            def writeDict(d):
                if d:
                    writer.beginElement("dict")
                    items = sorted(d.items()) if sort_keys else d.items()
                    for key, value in items:
                        if not isinstance(key, basestring):
                            if skipkeys:
                                continue
                            raise TypeError("键必须是字符串")
                        writer.simpleElement("key", key)
                        writer.writeValue(value)
                    writer.endElement("dict")
                else:
                    writer.simpleElement("dict")
            writer.writeDict = writeDict
            writer.writeln("<plist version=\"1.0\">")
            writer.writeValue(value)
            writer.writeln("</plist>")
    else:
        # 不是正确的格式
        raise ValueError("不支持的格式: {}".format(fmt))
    
def dumps(value, fmt=FMT_XML, skipkeys=False, sort_keys=True):
    # 避免使用 writePlistToString() 因为它使用 cStringIO 并在检测到 Unicode 字符串时会失败
    f = BytesIO() if _check_py3() else StringIO()
    dump(value, f, fmt=fmt, skipkeys=skipkeys, sort_keys=sort_keys)
    value = f.getvalue()
    if _check_py3():
        value = value.decode("utf-8")
    return value

###                        ###
# Python 2 的二进制 Plist 处理 #
###                        ###

# 来自 python 3 plistlib.py 源码: https://github.com/python/cpython/blob/3.11/Lib/plistlib.py
# 调整为可在 Python 2 和 3 上运行

class UID:
    def __init__(self, data):
        if not isinstance(data, int):
            raise TypeError("数据必须是整数")
        # 似乎 Apple 仅对 UID 使用 32 位无符号整数。尽管 CoreFoundation 的 CFBinaryPList.c 中详细说明二进制 plist 格式的注释理论上允许 64 位 UID，
        # 但同一文件中的大多数函数使用 32 位无符号整数，唯一暗示 64 位的函数似乎是内部复制和粘贴整数处理代码的遗留物，并且此代码自添加以来未更改。
        # （此外，处理 CF$UID 的 CFPropertyList.c 中的代码也使用 32 位无符号整数。）
        #
        # if data >= 1 << 64:
        #    raise ValueError("UID 不能 >= 2**64")
        if data >= 1 << 32:
            raise ValueError("UID 不能 >= 2**32 (4294967296)")
        if data < 0:
            raise ValueError("UID 必须是正数")
        self.data = data

    def __index__(self):
        return self.data

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.data))

    def __reduce__(self):
        return self.__class__, (self.data,)

    def __eq__(self, other):
        if not isinstance(other, UID):
            return NotImplemented
        return self.data == other.data

    def __hash__(self):
        return hash(self.data)

class InvalidFileException (ValueError):
    def __init__(self, message="无效文件"):
        ValueError.__init__(self, message)

_BINARY_FORMAT = {1: 'B', 2: 'H', 4: 'L', 8: 'Q'}

_undefined = object()

class _BinaryPlistParser:
    """
    读写二进制 plist 文件，遵循二进制格式描述。
    出错时引发 InvalidFileException，否则返回根对象。
    另见: http://opensource.apple.com/source/CF/CF-744.18/CFBinaryPList.c
    """
    def __init__(self, use_builtin_types, dict_type):
        self._use_builtin_types = use_builtin_types
        self._dict_type = dict_type

    def parse(self, fp):
        try:
            # 基本文件格式:
            # 头部
            # 对象...
            # refid->偏移量...
            # 尾部
            self._fp = fp
            self._fp.seek(-32, os.SEEK_END)
            trailer = self._fp.read(32)
            if len(trailer) != 32:
                raise InvalidFileException("文件尾部长度无效")
            (
                offset_size, self._ref_size, num_objects, top_object,
                offset_table_offset
            ) = struct.unpack('>6xBBQQQ', trailer)
            self._fp.seek(offset_table_offset)
            self._object_offsets = self._read_ints(num_objects, offset_size)
            self._objects = [_undefined] * num_objects
            return self._read_object(top_object)

        except (OSError, IndexError, struct.error, OverflowError,
                UnicodeDecodeError):
            raise InvalidFileException("解析文件时出错")

    def _get_size(self, tokenL):
        """返回下一个对象的大小"""
        if tokenL == 0xF:
            m = self._fp.read(1)[0]
            if not _check_py3():
                m = ord(m)
            m = m & 0x3
            s = 1 << m
            f = '>' + _BINARY_FORMAT[s]
            return struct.unpack(f, self._fp.read(s))[0]

        return tokenL

    def _read_ints(self, n, size):
        data = self._fp.read(size * n)
        if size in _BINARY_FORMAT:
            return struct.unpack('>' + _BINARY_FORMAT[size] * n, data)
        else:
            if not size or len(data) != size * n:
                raise InvalidFileException("读取整数时出错")
            return tuple(int(binascii.hexlify(data[i: i + size]),16)
                         for i in range(0, size * n, size))

    def _read_refs(self, n):
        return self._read_ints(n, self._ref_size)

    def _read_object(self, ref):
        """
        按引用读取对象。
        可能递归读取子对象（数组/字典/集合的内容）
        """
        result = self._objects[ref]
        if result is not _undefined:
            return result

        offset = self._object_offsets[ref]
        self._fp.seek(offset)
        token = self._fp.read(1)[0]
        if not _check_py3():
            token = ord(token)
        tokenH, tokenL = token & 0xF0, token & 0x0F

        if token == 0x00: # \x00 或 0x00
            result = None

        elif token == 0x08: # \x08 或 0x08
            result = False

        elif token == 0x09: # \x09 或 0x09
            result = True

        # 参考的源代码还提到了 URL (0x0c, 0x0d) 和 UUID (0x0e)，但两者都不能使用 Cocoa 库生成。

        elif token == 0x0f: # \x0f 或 0x0f
            result = b''

        elif tokenH == 0x10:  # 整数
            result = int(binascii.hexlify(self._fp.read(1 << tokenL)),16)
            if tokenL >= 3: # 有符号 - 调整
                result = result-((result & 0x8000000000000000) << 1)

        elif token == 0x22: # 实数
            result = struct.unpack('>f', self._fp.read(4))[0]

        elif token == 0x23: # 实数
            result = struct.unpack('>d', self._fp.read(8))[0]

        elif token == 0x33:  # 日期
            f = struct.unpack('>d', self._fp.read(8))[0]
            # 二进制 plist 的时间戳 0 对应于 2001-1-1 (Mac OS X 10.0 年份)，而不是 1970-1-1。
            result = (datetime.datetime(2001, 1, 1) +
                      datetime.timedelta(seconds=f))

        elif tokenH == 0x40:  # 数据
            s = self._get_size(tokenL)
            if self._use_builtin_types or not hasattr(plistlib, "Data"):
                result = self._fp.read(s)
            else:
                result = plistlib.Data(self._fp.read(s))

        elif tokenH == 0x50:  # ASCII 字符串
            s = self._get_size(tokenL)
            result =  self._fp.read(s).decode('ascii')
            result = result

        elif tokenH == 0x60:  # Unicode 字符串
            s = self._get_size(tokenL)
            result = self._fp.read(s * 2).decode('utf-16be')

        elif tokenH == 0x80:  # UID
            # 被 Key-Archiver plist 文件使用
            result = UID(int(binascii.hexlify(self._fp.read(1 + tokenL)),16))

        elif tokenH == 0xA0:  # 数组
            s = self._get_size(tokenL)
            obj_refs = self._read_refs(s)
            result = []
            self._objects[ref] = result
            result.extend(self._read_object(x) for x in obj_refs)

        # tokenH == 0xB0 被记录为 'ordset'，但未在 Apple 参考代码中实际实现。

        # tokenH == 0xC0 被记录为 'set'，但集合不能在 plist 中使用。

        elif tokenH == 0xD0:  # 字典
            s = self._get_size(tokenL)
            key_refs = self._read_refs(s)
            obj_refs = self._read_refs(s)
            result = self._dict_type()
            self._objects[ref] = result
            for k, o in zip(key_refs, obj_refs):
                key = self._read_object(k)
                if hasattr(plistlib, "Data") and isinstance(key, plistlib.Data):
                    key = key.data
                result[key] = self._read_object(o)

        else:
            raise InvalidFileException("未知的对象类型标记")

        self._objects[ref] = result
        return result

def _count_to_size(count):
    if count < 1 << 8:
        return 1

    elif count < 1 << 16:
        return 2

    elif count < 1 << 32:
        return 4

    else:
        return 8

_scalars = (str, int, float, datetime.datetime, bytes)

class _BinaryPlistWriter (object):
    def __init__(self, fp, sort_keys, skipkeys):
        self._fp = fp
        self._sort_keys = sort_keys
        self._skipkeys = skipkeys

    def write(self, value):

        # 扁平化的对象列表:
        self._objlist = []

        # 对象到对象ID的映射
        # 第一个字典的键为 (type(object), object)，
        # 当对象不可哈希时使用第二个字典，键为 id(object)
        self._objtable = {}
        self._objidtable = {}

        # 创建 plist 中所有对象的列表
        self._flatten(value)

        # 序列化容器中对象引用的大小取决于 plist 中的对象数量
        num_objects = len(self._objlist)
        self._object_offsets = [0]*num_objects
        self._ref_size = _count_to_size(num_objects)

        self._ref_format = _BINARY_FORMAT[self._ref_size]

        # 写入文件头
        self._fp.write(b'bplist00')

        # 写入对象列表
        for obj in self._objlist:
            self._write_object(obj)

        # 写入 refnum->对象偏移量表
        top_object = self._getrefnum(value)
        offset_table_offset = self._fp.tell()
        offset_size = _count_to_size(offset_table_offset)
        offset_format = '>' + _BINARY_FORMAT[offset_size] * num_objects
        self._fp.write(struct.pack(offset_format, *self._object_offsets))

        # 写入尾部
        sort_version = 0
        trailer = (
            sort_version, offset_size, self._ref_size, num_objects,
            top_object, offset_table_offset
        )
        self._fp.write(struct.pack('>5xBBBQQQ', *trailer))

    def _flatten(self, value):
        # 首先检查对象是否在对象表中，容器不使用此检查以确保具有相同内容的两个子容器将被序列化为不同的值
        if isinstance(value, _scalars):
            if (type(value), value) in self._objtable:
                return

        elif hasattr(plistlib, "Data") and isinstance(value, plistlib.Data):
            if (type(value.data), value.data) in self._objtable:
                return

        elif id(value) in self._objidtable:
            return

        # 添加到对象引用映射
        refnum = len(self._objlist)
        self._objlist.append(value)
        if isinstance(value, _scalars):
            self._objtable[(type(value), value)] = refnum
        elif hasattr(plistlib, "Data") and isinstance(value, plistlib.Data):
            self._objtable[(type(value.data), value.data)] = refnum
        else:
            self._objidtable[id(value)] = refnum

        # 最后递归到容器中
        if isinstance(value, dict):
            keys = []
            values = []
            items = value.items()
            if self._sort_keys:
                items = sorted(items)

            for k, v in items:
                if not isinstance(k, basestring):
                    if self._skipkeys:
                        continue
                    raise TypeError("键必须是字符串")
                keys.append(k)
                values.append(v)

            for o in itertools.chain(keys, values):
                self._flatten(o)

        elif isinstance(value, (list, tuple)):
            for o in value:
                self._flatten(o)

    def _getrefnum(self, value):
        if isinstance(value, _scalars):
            return self._objtable[(type(value), value)]
        elif hasattr(plistlib, "Data") and isinstance(value, plistlib.Data):
            return self._objtable[(type(value.data), value.data)]
        else:
            return self._objidtable[id(value)]

    def _write_size(self, token, size):
        if size < 15:
            self._fp.write(struct.pack('>B', token | size))

        elif size < 1 << 8:
            self._fp.write(struct.pack('>BBB', token | 0xF, 0x10, size))

        elif size < 1 << 16:
            self._fp.write(struct.pack('>BBH', token | 0xF, 0x11, size))

        elif size < 1 << 32:
            self._fp.write(struct.pack('>BBL', token | 0xF, 0x12, size))

        else:
            self._fp.write(struct.pack('>BBQ', token | 0xF, 0x13, size))

    def _write_object(self, value):
        ref = self._getrefnum(value)
        self._object_offsets[ref] = self._fp.tell()
        if value is None:
            self._fp.write(b'\x00')

        elif value is False:
            self._fp.write(b'\x08')

        elif value is True:
            self._fp.write(b'\x09')

        elif isinstance(value, int):
            if value < 0:
                try:
                    self._fp.write(struct.pack('>Bq', 0x13, value))
                except struct.error:
                    raise OverflowError(value) # from None
            elif value < 1 << 8:
                self._fp.write(struct.pack('>BB', 0x10, value))
            elif value < 1 << 16:
                self._fp.write(struct.pack('>BH', 0x11, value))
            elif value < 1 << 32:
                self._fp.write(struct.pack('>BL', 0x12, value))
            elif value < 1 << 63:
                self._fp.write(struct.pack('>BQ', 0x13, value))
            elif value < 1 << 64:
                self._fp.write(b'\x14' + value.to_bytes(16, 'big', signed=True))
            else:
                raise OverflowError(value)

        elif isinstance(value, float):
            self._fp.write(struct.pack('>Bd', 0x23, value))

        elif isinstance(value, datetime.datetime):
            f = (value - datetime.datetime(2001, 1, 1)).total_seconds()
            self._fp.write(struct.pack('>Bd', 0x33, f))

        elif (_check_py3() and isinstance(value, (bytes, bytearray))) or (hasattr(plistlib, "Data") and isinstance(value, plistlib.Data)):
            if not isinstance(value, (bytes, bytearray)):
                value = value.data # 解包
            self._write_size(0x40, len(value))
            self._fp.write(value)

        elif isinstance(value, basestring):
            try:
                t = value.encode('ascii')
                self._write_size(0x50, len(value))
            except UnicodeEncodeError:
                t = value.encode('utf-16be')
                self._write_size(0x60, len(t) // 2)
            self._fp.write(t)

        elif isinstance(value, UID) or (hasattr(plistlib,"UID") and isinstance(value, plistlib.UID)):
            if value.data < 0:
                raise ValueError("UID 必须是正数")
            elif value.data < 1 << 8:
                self._fp.write(struct.pack('>BB', 0x80, value))
            elif value.data < 1 << 16:
                self._fp.write(struct.pack('>BH', 0x81, value))
            elif value.data < 1 << 32:
                self._fp.write(struct.pack('>BL', 0x83, value))
            # elif value.data < 1 << 64:
            #    self._fp.write(struct.pack('>BQ', 0x87, value))
            else:
                raise OverflowError(value)

        elif isinstance(value, (list, tuple)):
            refs = [self._getrefnum(o) for o in value]
            s = len(refs)
            self._write_size(0xA0, s)
            self._fp.write(struct.pack('>' + self._ref_format * s, *refs))

        elif isinstance(value, dict):
            keyRefs, valRefs = [], []

            if self._sort_keys:
                rootItems = sorted(value.items())
            else:
                rootItems = value.items()

            for k, v in rootItems:
                if not isinstance(k, basestring):
                    if self._skipkeys:
                        continue
                    raise TypeError("键必须是字符串")
                keyRefs.append(self._getrefnum(k))
                valRefs.append(self._getrefnum(v))

            s = len(keyRefs)
            self._write_size(0xD0, s)
            self._fp.write(struct.pack('>' + self._ref_format * s, *keyRefs))
            self._fp.write(struct.pack('>' + self._ref_format * s, *valRefs))

        else:
            raise TypeError(f"不支持的类型: {type(value)}")