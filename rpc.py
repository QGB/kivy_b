import sys, io, urllib.parse, threading, traceback, struct
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

def get_bmp_bytes(rgb=None, size=(16, 16)):
    if not rgb: rgb = (255, 0, 0)
    if isinstance(size, int): size = [size, size]
    width, height = size
    r, g, b = (max(0, min(255, c)) for c in rgb)
    bgr_color = bytes([b, g, r])
    bytes_per_pixel = 3
    bytes_per_row = (width * bytes_per_pixel + 3) // 4 * 4
    pixel_data_size = bytes_per_row * height
    file_size = 14 + 40 + pixel_data_size
    bmp_header = struct.pack('<2sIII', b'BM', file_size, 0, 54)
    bmp_info = struct.pack('<IIIHHIIIIII', 40, width, height, 1, 24, 0, pixel_data_size, 3780, 3780, 0, 0)
    pixels = b''
    for _ in range(height):
        row = bgr_color * width
        padding = b'\x00' * (bytes_per_row - len(row))
        pixels += row + padding
    return bmp_header + bmp_info + pixels

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class RPCRequestHandler(BaseHTTPRequestHandler):
    server_version = "RPC/0.3"
    key = None
    globals_dict = None
    favicon_bytes = None
    def log_message(self, format, *args):
        print(f"[RPC] {self.address_string()} - {format % args}")
    def do_GET(self):
        if self.path == '/favicon.ico' and self.favicon_bytes:
            self.send_response(200)
            self.send_header('Content-Type', 'image/x-icon')
            self.send_header('Cache-Control', 'max-age=86400')
            self.send_header('Content-Length', str(len(self.favicon_bytes)))
            self.end_headers()
            self.wfile.write(self.favicon_bytes)
            return
        self.handle_rpc()
    def do_POST(self):
        self.handle_rpc()
    def handle_rpc(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.lstrip('/')
            query = urllib.parse.parse_qs(parsed.query)
            if self.key:
                if not (path.startswith(self.key + '/') or query.get('key') == [self.key]):
                    self.send_error(403, "Forbidden")
                    return
                if path.startswith(self.key + '/'):
                    code = path[len(self.key)+1:]
                else:
                    code = path
            else:
                code = path
            if 'code' in query:
                code = query['code'][0]
            if not code:
                self.send_error(400, "No code")
                return
            code = urllib.parse.unquote(code)
            print(f"[RPC] Execute: {code[:200]}")
            exec_globals = self.globals_dict.copy() if self.globals_dict else {}
            exec_globals['__name__'] = '__rpc_exec__'
            exec_globals['request'] = self
            exec_globals['q'] = self
            class ResponseWrapper:
                def __init__(self):
                    self.status = 200
                    self.headers = {}
                    self.data = None
                def set_data(self, data):
                    self.data = data
                def set_status(self, code):
                    self.status = code
                def set_header(self, key, value):
                    self.headers[key] = value
            resp = ResponseWrapper()
            exec_globals['response'] = resp
            exec_globals['p'] = resp
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                exec(code, exec_globals)
                output = sys.stdout.getvalue()
                if 'r' in exec_globals:
                    result = exec_globals['r']
                elif resp.data is not None:
                    result = resp.data
                elif output:
                    result = output
                else:
                    result = f"no 'r' variable, locals keys: {list(exec_globals.keys())}"
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
            except Exception as e:
                result = traceback.format_exc()
                self.send_response(500)
            finally:
                sys.stdout = old_stdout
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(str(result).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

def start_rpc_server(port=1133, key='', ip='0.0.0.0', globals_dict=None, daemon=True, favicon_rgb=None, favicon_size=16):
    if not key:key=''
    RPCRequestHandler.key = key
    RPCRequestHandler.globals_dict = globals_dict if globals_dict is not None else {}
    if not favicon_rgb:favicon_rgb=(port//100,port%100,0)
    RPCRequestHandler.favicon_bytes = get_bmp_bytes(rgb=favicon_rgb, size=favicon_size)
    server = ThreadedHTTPServer((ip, port), RPCRequestHandler)
    thread = threading.Thread(target=server.serve_forever, name='RPC_Server', daemon=daemon)
    thread.start()
    print(f"[RPC server] at http://{ip}:{port}/{key}")
    return server, thread

if __name__ == '__main__':
    start_rpc_server(port=1133, key=None, globals_dict=globals(),)
    input("Press Ctrl+C to stop\n")