import json
from urllib import request


class HeliosServerClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    def _post_json(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.server_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=2.0) as response:
            return json.loads(response.read().decode("utf-8"))

    def send_rod_update(self, rod: int, insertion: int):
        return self._post_json("/rod-update", {"rod": rod, "insertion": insertion})

    def send_command(self, command: str):
        return self._post_json("/command", {"command": command})
