"""Trust only host public keys obtained from authenticated cloud serial output."""
import argparse
from pathlib import Path
import re
import time

from prepare_cloud import load_env
from src.services.yandex_client import YandexClient
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outputs", type=Path)
    parser.add_argument("--known-hosts", type=Path, required=True)
    args = parser.parse_args()
    load_env()
    client = YandexClient()
    machines = json.loads(args.outputs.read_bytes())["machines"]["value"]
    lines = []
    for key, vm in machines.items():
        public_key = None
        for _ in range(30):
            contents = client.request("compute", f"compute/v1/instances/{vm['id']}:serialPortOutput?port=1").get("contents", "")
            if "IRINA_HOSTKEY_START" in contents and "IRINA_HOSTKEY_END" in contents:
                section = contents.rsplit("IRINA_HOSTKEY_START", 1)[1].split("IRINA_HOSTKEY_END", 1)[0]
                # Serial console may prefix each line with a cloud-init timestamp.
                found = re.search(r"\b(ssh-ed25519 [A-Za-z0-9+/=]+)", section)
                if found:
                    public_key = found.group(1)
                    break
            time.sleep(3)
        if not public_key:
            raise RuntimeError(f"No trusted host key in serial output for {key}; SSH verification remains enabled")
        names = [vm["fqdn"], vm.get("public_ip"), vm.get("private_ip")]
        lines.append(",".join(n for n in names if n) + " " + public_key)
        print(f"Verified cloud serial host key for {vm['fqdn']}", flush=True)
    args.known_hosts.parent.mkdir(parents=True, exist_ok=True)
    args.known_hosts.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
