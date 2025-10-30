# CMPT 371 - Mini Project
# 29 Oct 2025
# Alfred Goh
# Euluna Gotami

import socket
import threading
from urllib.parse import urlparse

PORT = 8888
CACHE = {}

def read_until_double_crlf(sock): # makes sure get entire thing
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    if b'\r\n\r\n' in data:
        head, rest = data.split(b'\r\n\r\n', 1)
        return head.decode(), rest
    return data.decode(errors='replace'), b''

def parse_headers(header_text):
    lines = header_text.split('\r\n')
    request_line = lines[0] if lines else '' # first request line
    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        if ':' in line:
            name, value = line.split(':', 1)
            headers[name.strip().lower()] = value.strip()
    return request_line, headers

def strip_hop_by_hop(headers):
    out = {k: v for k, v in headers.items() 
           if k not in ('connection', 'keep-alive')}
    return out

def determine_target_and_path(request_line, headers):
    parts = request_line.split()
    if len(parts) != 3:
        return
    method, target, version = parts

    parsed = urlparse(target)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    path = parsed.path or '/'

    return method, host, port, path, version

def build_request(method, path, version, headers):
    lines = [f"{method} {path} {version}"] # request line
    for name, value in headers.items(): # each header
        lines.append(f"{name}: {value}")
    lines.append('')
    header_block = '\r\n'.join(lines)
    return header_block.encode()

def handle_client(client_sock, addr):
    try:
        header_text, rest = read_until_double_crlf(client_sock)
        if not header_text:
            client_sock.close()
            return
        
        # parse headers
        request_line, headers = parse_headers(header_text)
        print(f"[PROXY] {addr}: {request_line}")

        # determine target
        result = determine_target_and_path(request_line, headers)
        if result is None:
            print(f"[PROXY] Bad request from {addr}")
            client_sock.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 11\r\n\r\nBad Request")
            client_sock.close()
            return
        method, host, port, path, version = result

        # Check cache
        url = f"{host}:{port}{path}"
        if url in CACHE:
            print(f"[CACHE HIT] {url}")
            client_sock.sendall(CACHE[url])
            client_sock.close()
            return

        safe_headers = strip_hop_by_hop(headers)
        safe_headers['host'] = f"{host}:{port}" if port not in (80, 443) else host

        # add via header
        via_value = f"{version.split('/')[1]} localhost:{PORT}"
        if 'via' in safe_headers:
            safe_headers['via'] = safe_headers['via'] + ', ' + via_value
        else:
            safe_headers['via'] = via_value
        safe_headers['connection'] = 'close'

        # build request
        request_bytes = build_request(method, path, version, safe_headers)
        request_bytes += rest

        # connect to origin server and forward request
        try:
            print(f"[PROXY] Connecting to {host}:{port}")
            with socket.create_connection((host, port), timeout=10) as upstream:
                upstream.sendall(request_bytes) # send request to origin
                
                # Collect response and stream to client
                response_data = b''
                while True:
                    data = upstream.recv(4096)
                    if not data:
                        break
                    response_data += data
                    client_sock.sendall(data)
                
                # Store in cache
                CACHE[url] = response_data
                print(f"[CACHE STORED] {url}")
        except Exception as e:
            print(f"[PROXY] Upstream error for {host}:{port}: {e}")
            client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 11\r\n\r\nBad Gateway")
    except Exception as e:
        print(f"[PROXY] Error handling {addr}: {e}")
    finally:
        client_sock.close()

def main():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind(('localhost', PORT))
    serversocket.listen(5)
    print(f"Proxy listening on localhost:{PORT}")
    while True:
        client, addr = serversocket.accept()
        t = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()