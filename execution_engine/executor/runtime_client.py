#execution_engine\executor\runtime_client.py

import requests

class RuntimeAgentClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def deploy(self, payload: dict):
        url = f"{self.base_url}/deploy"
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code != 200:
            raise RuntimeError(
                f"Runtime deploy failed [{response.status_code}]: {response.text}"
            )

        return response.json()
