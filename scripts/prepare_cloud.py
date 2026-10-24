"""Prepare an isolated folder and tfvars; never bind billing or create paid resources."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.services.yandex_client import YandexClient


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--cloud-id", required=True)
    parser.add_argument("--network-id", required=True, help="Existing VPC outside this Terraform state")
    parser.add_argument("--folder-name", default="diplom-irina")
    args = parser.parse_args()
    load_env()
    client = YandexClient()
    cloud = client.request("resource-manager", f"resource-manager/v1/clouds/{args.cloud_id}")
    if cloud["organizationId"] != args.organization_id:
        raise RuntimeError("Cloud belongs to another organization; refusing to proceed")
    folders = client.request("resource-manager", f"resource-manager/v1/folders?cloudId={args.cloud_id}").get("folders", [])
    existing = [f for f in folders if f["name"] == args.folder_name]
    if existing:
        folder = existing[0]
    else:
        folder = client.wait(client.request("resource-manager", "resource-manager/v1/folders", method="POST", body={
            "cloudId": args.cloud_id, "name": args.folder_name,
            "description": "Irina diploma: Terraform and native Ansible services",
            "labels": {"project": "diplom-irina"},
        }))
    if folder.get("status") != "ACTIVE":
        raise RuntimeError("Folder is not ACTIVE")
    image = client.request("compute", "compute/v1/images:latestByFamily?folderId=standard-images&family=ubuntu-2204-lts")
    opener = build_opener(ProxyHandler({}))
    with opener.open("https://api.ipify.org", timeout=15) as response:
        admin_ip = str(ipaddress.IPv4Address(response.read().decode().strip()))
    key = ROOT / ".local/irina_ed25519"
    key.parent.mkdir(exist_ok=True)
    if not key.exists():
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(key), "-N", "", "-C", "diplom-irina"],
                       check=True, capture_output=True)
    values = {"cloud_id": args.cloud_id, "folder_id": folder["id"], "network_id": args.network_id,
              "admin_cidr": admin_ip + "/32", "image_id": image["id"],
              "ssh_public_key_path": key.with_suffix(".pub").as_posix(), "preemptible": False}
    path = ROOT / "terraform/terraform.tfvars"
    content = "".join(f"{k} = {json.dumps(v)}\n" for k, v in values.items())
    if path.exists():
        existing_values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key_name, value = line.split("=", 1)
                existing_values[key_name.strip()] = json.loads(value.strip())
        if existing_values != values:
            raise RuntimeError("tfvars already exists with different values; review before overwriting")
    path.write_text(content, encoding="utf-8")
    accounts = client.request("billing", "billing/v1/billingAccounts").get("billingAccounts", [])
    linked = []
    for account in accounts:
        bindings = client.request("billing", f"billing/v1/billingAccounts/{account['id']}/billableObjectBindings")
        if any(b["billableObject"]["id"] == args.cloud_id for b in bindings.get("billableObjectBindings", [])):
            linked.append({"id": account["id"], "active": account.get("active", False)})
    result = {"organization_id": args.organization_id, "cloud_id": args.cloud_id,
              "folder_id": folder["id"], "folder_name": folder["name"],
              "image_id": image["id"], "visible_billing_linked": linked,
              "visible_billing_ready": any(a["active"] for a in linked),
              "billing_visibility_note": "No visible binding does not rule out a billing account owned by another user",
              "paid_resources_created": False}
    (ROOT / ".local/preflight.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
