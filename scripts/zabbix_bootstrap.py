"""Register active agents and HTTP checks using a manually issued Zabbix API token."""
import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


class Zabbix:
    def __init__(self, url, token):
        if urlsplit(url).scheme not in ("http", "https"):
            raise ValueError("ZABBIX_URL must be an HTTP(S) URL")
        self.url = url.rstrip("/") + "/api_jsonrpc.php"
        self.token = token

    def call(self, method, params):
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        request = Request(self.url, data=payload, headers={
            "Content-Type": "application/json-rpc", "Authorization": "Bearer " + self.token})
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        if "error" in result:
            # Do not print request bodies or authentication headers.
            detail = '' if method.startswith('user.') else ': '+str(result['error'].get('data',''))
            raise RuntimeError(f"Zabbix API rejected {method}: {result['error'].get('message')}"+detail)
        return result["result"]


def bootstrap(api, inventory):
    group = api.call("hostgroup.get", {"filter": {"name": ["Irina infrastructure"]}})
    group_id = group[0]["groupid"] if group else api.call(
        "hostgroup.create", {"name": "Irina infrastructure"})["groupids"][0]
    templates = api.call("template.get", {"filter": {"host": ["Linux by Zabbix agent active"]}})
    if len(templates) != 1:
        raise RuntimeError("Expected bundled template: Linux by Zabbix agent active")
    template_id = templates[0]["templateid"]
    for role, group in inventory["all"]["children"].items():
        for fqdn in group["hosts"]:
            hosts = api.call("host.get", {"filter": {"host": [fqdn]}})
            if hosts:
                host_id = hosts[0]["hostid"]
            else:
                host_id = api.call("host.create", {
                    "host": fqdn, "groups": [{"groupid": group_id}],
                    "templates": [{"templateid": template_id}],
                    "interfaces": [{"type": 1, "main": 1, "useip": 0, "ip": "",
                                    "dns": fqdn, "port": "10050"}],
                })["hostids"][0]
            if role == "web":
                checks = api.call("httptest.get", {"hostids": [host_id], "filter": {"name": ["Homepage"]}})
                if not checks:
                    api.call("httptest.create", {
                        "name": "Homepage", "hostid": host_id, "delay": "30s",
                        "steps": [{"name": "GET /", "url": f"http://{fqdn}/", "no": 1,
                                   "required": "ДИПЛОМНЫЙ ПРОЕКТ", "status_codes": "200", "timeout": "5s"}],
                    })
            print(f"Registered/kept {fqdn} ({role})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("ansible/inventory/hosts.yml"))
    args = parser.parse_args()
    url, token = os.environ.get("ZABBIX_URL"), os.environ.get("ZABBIX_API_TOKEN")
    if not url or not token:
        parser.error("Set ZABBIX_URL and ZABBIX_API_TOKEN; use an SSH tunnel or HTTPS")
    bootstrap(Zabbix(url, token), json.loads(args.inventory.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
