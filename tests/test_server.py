import json
import threading
from urllib import request

from helios_core.server import create_server
from helios_core.state import ReactorCoreState


def _http_get_json(url: str):
    with request.urlopen(url, timeout=2.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=2.0) as response:
        return json.loads(response.read().decode("utf-8"))


def test_server_health_and_rod_echo():
    server = create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        base_url = f"http://{host}:{port}"

        health = _http_get_json(f"{base_url}/health")
        assert health["ok"] is True

        state = ReactorCoreState()
        control_rod = next(rod for rod, letter in state.rod_to_letter.items() if letter == "C")
        response = _http_post_json(
            f"{base_url}/rod-update",
            {"rod": control_rod, "insertion": 55},
        )
        assert response["ok"] is True
        assert response["echo"] == {"rod": control_rod, "insertion": 55}
    finally:
        server.shutdown()
        server.server_close()
