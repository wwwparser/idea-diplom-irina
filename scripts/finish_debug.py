"""Initialize the debug UIs through SSH tunnels; never print passwords or tokens."""
import base64
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from zabbix_bootstrap import Zabbix, bootstrap

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))


def request(url, body=None, method=None, user=None, password=None, headers=None):
    headers = dict(headers or {})
    if user:
        value = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Authorization"] = "Basic " + value
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=json.dumps(body).encode() if body is not None else None,
                  headers=headers, method=method or ("POST" if body is not None else "GET"))
    try:
        with OPENER.open(req, timeout=20) as response:
            data=response.read()
            return json.loads(data) if data else {}
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} at {url.split('?')[0]}") from None


def zabbix_login(password, url="http://127.0.0.1:18080"):
    result = request(url+"/api_jsonrpc.php", {
        "jsonrpc": "2.0", "id": 1, "method": "user.login",
        "params": {"username": "Admin", "password": password}})
    if "error" in result:
        raise RuntimeError("Zabbix login failed")
    return result["result"]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,default=ROOT/'ansible/inventory/hosts-debug.yml')
    parser.add_argument('--evidence',type=Path,default=ROOT/'evidence/debug-services.json')
    args=parser.parse_args()
    secrets = json.loads((ROOT / ".local/service-credentials.json").read_text(encoding="utf-8"))
    try:
        session = zabbix_login(secrets["zabbix_admin_password"])
    except RuntimeError:
        session = zabbix_login("zabbix")
        api = Zabbix("http://127.0.0.1:18080", session)
        admin = api.call("user.get", {"filter": {"username": ["Admin"]}, "output": ["userid"]})
        api.call("user.update", {"userid": admin[0]["userid"], "passwd": secrets["zabbix_admin_password"],
                                 "current_passwd": "zabbix"})
        session = zabbix_login(secrets["zabbix_admin_password"])
    print("Zabbix default password replaced/verified; secret omitted.", flush=True)
    api = Zabbix("http://127.0.0.1:18080", session)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    bootstrap(api, inventory)
    for default_host in api.call("host.get", {"filter": {"host": ["Zabbix server"]}, "output": ["hostid"]}):
        api.call("host.update", {"hostid": default_host["hostid"], "status": 1})
    hostnames=sorted({h for group in inventory['all']['children'].values() for h in group['hosts']})
    hosts = api.call("host.get", {"filter": {"host": hostnames},
                                  "output": ["hostid", "host", "status"]})

    auth = {"user": "elastic", "password": secrets["elastic_password"]}
    request("http://127.0.0.1:19200/_index_template/irina-nginx", method="PUT", body={
        "index_patterns": ["nginx-*"], "template": {"settings": {"number_of_replicas": 0}}}, **auth)
    request("http://127.0.0.1:19200/nginx-*/_settings", method="PUT",
            body={"index": {"number_of_replicas": 0}}, **auth)
    health = request("http://127.0.0.1:19200/_cluster/health", **auth)
    print("Elasticsearch authenticated; cluster status:", health["status"], flush=True)

    kibana = "http://127.0.0.1:15601"
    for attempt in range(30):
        try:
            views = request(kibana + "/api/data_views", **auth)
            break
        except (RuntimeError, URLError) as exc:
            if isinstance(exc, RuntimeError) and not str(exc).startswith("HTTP 503"):
                raise
            if attempt == 29:
                raise
            time.sleep(3)
    found = [view for view in views.get("data_view", []) if view.get("title") == "nginx-*"]
    if not found:
        request(kibana + "/api/data_views/data_view", body={
            "data_view": {"title": "nginx-*", "name": "Nginx diploma logs", "timeFieldName": "@timestamp"}},
                headers={"kbn-xsrf": "true"}, **auth)
    print("Kibana nginx-* data view ready.", flush=True)

    query = {"size": 0, "aggs": {
        "hosts": {"terms": {"field": "host.name.keyword"}},
        "types": {"terms": {"field": "log_type.keyword"}}}}
    logs = request("http://127.0.0.1:19200/nginx-*/_search", body=query, **auth)
    metrics = api.call("item.get", {"hostids": [h["hostid"] for h in hosts],
        "filter": {"key_": ["system.cpu.util", "vm.memory.size[available]"]},
        "output": ["hostid", "key_", "lastvalue", "lastclock", "state", "error"]})
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "profile": "full-six-vms" if len(hostnames)==6 else "debug-two-vms",
              "zabbix_hosts": hosts, "sample_metrics": metrics,
              "elasticsearch_health": health, "nginx_logs": logs,
              "kibana_data_view": "nginx-*", "passwords": "stored locally; omitted from report"}
    args.evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    api.call("user.logout", [])
    print(f"Service check saved to {args.evidence}; no credentials printed.")


if __name__ == "__main__":
    main()
