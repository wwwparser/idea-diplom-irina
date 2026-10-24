"""Small REST client for cloud bootstrap; tokens are never returned in logs."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener


class CloudError(RuntimeError):
    pass


class YandexClient:
    def __init__(self, token=None):
        self.token = token or os.environ.get("YC_TOKEN")
        if not self.token:
            raise CloudError("YC_TOKEN is missing. Obtain a fresh IAM token with yc iam create-token.")
        # This workstation's proxy fails TLS for cloud APIs. Use a direct connection.
        self.opener = build_opener(ProxyHandler({}))

    def request(self, service, path, method="GET", body=None):
        url = f"https://{service}.api.cloud.yandex.net/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(3):
            req = Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
            try:
                with self.opener.open(req, timeout=30) as response:
                    return json.load(response)
            except HTTPError as exc:
                if method == "GET" and exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                # Return the server's error message without headers, request bodies or IAM tokens.
                try:
                    error=json.loads(exc.read())
                    message=str(error.get('message','')).replace(self.token,'[redacted]')[:1500]
                except (ValueError, OSError):
                    message=''
                raise CloudError(f"Yandex {service}: HTTP {exc.code} for {method} {path.split('?')[0]}: {message}") from None
            except URLError:
                if method == "GET" and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise CloudError(f"Connection failed for {service}; request outcome may be unknown") from None

    def wait(self, operation):
        deadline = time.monotonic() + 120
        while not operation.get("done"):
            if time.monotonic() >= deadline:
                raise CloudError("Operation timed out; check cloud state before retrying")
            time.sleep(2)
            operation = self.request("operation", f"operations/{operation['id']}")
        if operation.get("error"):
            raise CloudError(f"Operation failed with code {operation['error'].get('code')}")
        return operation["response"]
