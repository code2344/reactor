import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .state import ReactorCoreState


class HeliosServer(ThreadingHTTPServer):
    def __init__(self, server_address, request_handler_class):
        super().__init__(server_address, request_handler_class)
        self.reactor_state = ReactorCoreState()


class HeliosRequestHandler(BaseHTTPRequestHandler):
    server: HeliosServer

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw_body.decode("utf-8"))

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"ok": True, "service": "helios-core"})
            return

        if self.path == "/state":
            self._send_json(
                {
                    "ok": True,
                    "control_rod_levels": self.server.reactor_state.control_rod_levels,
                    "alarm_state": self.server.reactor_state.alarm_state,
                    "custom_text": self.server.reactor_state.custom_text,
                }
            )
            return

        self._send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self):
        if self.path == "/rod-update":
            payload = self._read_json()
            rod = int(payload["rod"])
            insertion = int(payload["insertion"])
            self.server.reactor_state.set_rod_insertion(rod, insertion)
            self._send_json(
                {
                    "ok": True,
                    "echo": {
                        "rod": rod,
                        "insertion": insertion,
                    },
                }
            )
            return

        if self.path == "/command":
            payload = self._read_json()
            result = self.server.reactor_state.apply_command(payload.get("command", ""))
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        self._send_json({"ok": False, "error": "not found"}, status=404)


def create_server(host: str = "127.0.0.1", port: int = 8000):
    return HeliosServer((host, port), HeliosRequestHandler)


def serve(host: str = "127.0.0.1", port: int = 8000):
    server = create_server(host=host, port=port)
    print(f"helios-core server listening on http://{host}:{port}")
    server.serve_forever()
