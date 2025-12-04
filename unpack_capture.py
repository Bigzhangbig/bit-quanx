"""
脚本名称：抓包数据解包工具
作者：Gemini for User
描述：解压抓包工具（如 Proxyman/Charles）导出的请求/响应数据文件。
      支持 chunked 编码解析和 gzip/deflate/br 解压缩。

用法：
1. 单文件解包：
     python unpack_capture.py <root_dir>

2. 搜索指定域名的抓包并解包：
     python unpack_capture.py <root_dir> <keyword>
   示例：
     python unpack_capture.py 20251201_160758 qcbldekt.bit.edu.cn

3. 搜索指定域名和路径的抓包：
     python unpack_capture.py <root_dir> <keyword> <path_contains>
   示例：
     python unpack_capture.py 20251201_160758 qcbldekt.bit.edu.cn /api/course/cancelApply

参数说明：
- root_dir：抓包导出的根目录
- keyword：要搜索的域名或关键字（默认 qcbldekt.bit.edu.cn）
- path_contains：可选，过滤包含指定路径的请求

输出：
- 若响应为 JSON，保存为 .decoded.json
- 若响应为普通文本，保存为 .decoded.txt
- 若响应为二进制，保存为 .decoded.bin
"""

import sys
import gzip
import zlib
import os

def dechunk(data: bytes) -> bytes:
    try:
        i = 0
        n = len(data)
        out = bytearray()
        while True:
            j = data.find(b"\r\n", i)
            if j == -1:
                break
            line = data[i:j]
            if b";" in line:
                line = line.split(b";", 1)[0]
            line = line.strip()
            if not line:
                i = j + 2
                continue
            try:
                size = int(line, 16)
            except Exception:
                return data
            i = j + 2
            if size == 0:
                break
            if i + size > n:
                return data
            out += data[i:i+size]
            i = i + size
            if i + 2 <= n and data[i:i+2] == b"\r\n":
                i += 2
        return bytes(out) if out else data
    except Exception:
        return data

def decompress(data: bytes) -> bytes:
    data = dechunk(data)
    try:
        return gzip.decompress(data)
    except:
        pass
    try:
        return zlib.decompress(data)
    except:
        pass
    try:
        return zlib.decompress(data, -15)
    except:
        pass
    return data

def process_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        decompressed = decompress(data)
        output_json_path = file_path + ".decoded.json"
        output_txt_path = file_path + ".decoded.txt"
        output_bin_path = file_path + ".decoded.bin"
        try:
            text = decompressed.decode('utf-8')
            import json
            obj = json.loads(text)
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            print(f"Successfully decompressed and recognized as JSON: {output_json_path}")
            return
        except Exception:
            pass
        try:
            text = decompressed.decode('utf-8')
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Successfully decompressed and saved as text: {output_txt_path}")
            return
        except Exception:
            pass
        with open(output_bin_path, 'wb') as f:
            f.write(decompressed)
        print(f"Successfully decompressed to binary file {output_bin_path}")
    except Exception as e:
        print(f"Error: {e}")

def find_capture_files(root_dir, keyword="qcbldekt.bit.edu.cn"):
    matched_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if os.path.abspath(dirpath) == os.path.abspath(root_dir):
            continue
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                if keyword.encode() in content:
                    matched_files.append(file_path)
            except Exception:
                continue
    return matched_files

if __name__ == "__main__":
    # 用法:
    #   python unpack_capture.py <root_dir> [keyword] [path_contains]
    # 例如:
    #   python unpack_capture.py 20251201_160758 qcbldekt.bit.edu.cn /api/course/cancelApply
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "2025-11-27-223528"
    keyword = sys.argv[2] if len(sys.argv) > 2 else "qcbldekt.bit.edu.cn"
    path_contains = sys.argv[3] if len(sys.argv) > 3 else None

    matched_files = find_capture_files(root_dir, keyword)
    for file_path in matched_files:
        if not file_path.endswith("basic"):
            continue
        try:
            with open(file_path, 'rb') as f:
                basic = f.read().decode('utf-8', errors='ignore')
        except Exception:
            basic = ""
        if path_contains and path_contains not in basic:
            continue
        dir_path = os.path.dirname(file_path)
        response_body_path = os.path.join(dir_path, "response_body")
        if os.path.exists(response_body_path):
            print(f"解包: {response_body_path}")
            process_file(response_body_path)
