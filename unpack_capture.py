"""
脚本名称：抓包数据解压工具
描述：通用抓包解包工具，支持 gzip 和 chunked 编码。
用法：python unpack_capture.py <input_file> [output_file]
"""
import sys
import gzip
import zlib
import os

def dechunk(data: bytes) -> bytes:
    """Decode HTTP chunked transfer-encoding body.
    If parsing fails, return original data.
    """
    try:
        i = 0
        n = len(data)
        out = bytearray()
        while True:
            # find chunk-size line
            j = data.find(b"\r\n", i)
            if j == -1:
                break
            line = data[i:j]
            # strip chunk extensions
            if b";" in line:
                line = line.split(b";", 1)[0]
            line = line.strip()
            # empty line guard
            if not line:
                i = j + 2
                continue
            # parse hex size
            try:
                size = int(line, 16)
            except Exception:
                # not chunked
                return data
            i = j + 2
            if size == 0:
                # skip final CRLF and trailers if present
                break
            if i + size > n:
                # malformed
                return data
            out += data[i:i+size]
            i = i + size
            # skip CRLF after chunk
            if i + 2 <= n and data[i:i+2] == b"\r\n":
                i += 2
        return bytes(out) if out else data
    except Exception:
        return data

def decompress(data: bytes) -> bytes:
    # First, try to dechunk if needed
    data = dechunk(data)
    # Try gzip
    try:
        return gzip.decompress(data)
    except:
        pass
    
    # Try zlib (deflate)
    try:
        return zlib.decompress(data)
    except:
        pass
        
    # Try zlib with raw deflate (no header)
    try:
        return zlib.decompress(data, -15)
    except:
        pass

    return data

def main():
    if len(sys.argv) < 2:
        print("Usage: python unpack_capture.py <file_path>")
        return

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        decompressed = decompress(data)
        
        output_path = file_path + ".decoded.txt"
        try:
            # Try to decode as utf-8
            text = decompressed.decode('utf-8')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Successfully decompressed and decoded to {output_path}")
        except UnicodeDecodeError:
            # If not utf-8, save as binary
            output_path = file_path + ".decoded.bin"
            with open(output_path, 'wb') as f:
                f.write(decompressed)
            print(f"Successfully decompressed to binary file {output_path}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
