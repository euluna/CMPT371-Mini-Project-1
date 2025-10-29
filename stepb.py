import datetime
import socket
import threading
import os
from email.utils import parsedate_to_datetime, formatdate
from datetime import datetime, timezone

PORT = 8000
DOCUMENT_ROOT = os.getcwd()

def print_response(status_code, msg):
    reason = {
        200: "OK",
        304: "Not Modified",
        400: "Bad Request", #added
        403: "Forbidden",
        404: "Not Found",
        505: "HTTP Version Not Supported"
    }

    body = {
        200: msg,
        304: "<h1>304 Not Modified</h1>",
        400: "<h1>400 Bad Request</h1>",
        403: "<h1>403 Forbidden</h1>",
        404: "<h1>404 Not Found</h1>",
        505: "<h1>505 HTTP Version Not Supported</h1>",
    }

    header = f"HTTP/1.1 {status_code} {reason[status_code]}\r\n"
    header += f"Date: {formatdate(usegmt=True)}\r\n" #use GMT
    header += "Server: Webserver\r\n"
    header += f"Content-Type: text/html\r\n"
    header += f"Content-Length: {len(body[status_code].encode())}\r\n"
    header += "Connection: close\r\n\r\n"
    return header + body[status_code]


def make_client_thread(sk, addr):
    print(f"[CONNECTED] {addr}")
    try:
        # while True:
            request = sk.recv(1024)
            if not request:
                print(f"[DISCONNECTED] {addr}")
                # break
            request_decoded = request.decode(errors='ignore')
            print(f"[REQUEST] from {addr}:\n{request_decoded}")

            lines = request_decoded.splitlines()
            if not lines:
                return

            parts = lines[0].split()
            if len(parts) != 3:
                sk.sendall(print_response(400, "").encode())
                return

            method = parts[0]
            path = parts[1]
            ver = parts[2]

            # Check HTTP Version
            if ver not in ["HTTP/1.0", "HTTP/1.1"]:
                sk.sendall(print_response(505, "").encode())
                return

            # Only handle GET requests
            if method != "GET":
                sk.sendall(print_response(403, "").encode())
                return

            filepath = os.path.join(DOCUMENT_ROOT, path.strip("/"))

            # 403 Forbidden
            if "/private" in path or path.startswith("/.") or path.endswith("/."):
                sk.sendall(print_response(403, "").encode())
                return

            # 404 Not Found
            if not os.path.exists(filepath):
                sk.sendall(print_response(404, "").encode())
                return

            # 304 Not Modified
            if_modified_since = None
            for line in lines[1:]:
                if line.lower().startswith("if-modified-since:"):
                    if_modified_since = line.split(":", 1)[1].strip()
                    break

            if if_modified_since:
                try:
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc)
                    client_time = parsedate_to_datetime(if_modified_since)
                    if file_mod_time <= client_time:
                        sk.sendall(print_response(304, "").encode())
                        return
                except Exception as e:
                    print(f"[WARNING] Invalid If-Modified-Since header: {e}")

            # 200 OK
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                sk.sendall(print_response(200, content).encode())
            except Exception as e:
                print(f"[ERROR] Cannot read file: {e}")
                sk.sendall(print_response(403, "").encode())

    except Exception as e:
        print(f"[ERROR] {addr}: {e}")
    finally:
        sk.close()


def main():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind(('localhost', PORT))
    serversocket.listen(5)
    print(f"Server listening on port {PORT}...")

    while True:
        clientsocket, address = serversocket.accept()
        thread = threading.Thread(target=make_client_thread, args=(clientsocket, address))
        thread.start()


if __name__ == "__main__":
    main()
