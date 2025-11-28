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
    root_dir = "2025-11-27-223528"
    keyword = "qcbldekt.bit.edu.cn"
    matched_files = find_capture_files(root_dir, keyword)
    for file_path in matched_files:
        if file_path.endswith("basic"):
            dir_path = os.path.dirname(file_path)
            response_body_path = os.path.join(dir_path, "response_body")
            if os.path.exists(response_body_path):
                print(f"解包: {response_body_path}")
                process_file(response_body_path)
