"""Convert Terraform JSON outputs to FQDN-only inventory and local SSH config."""
import argparse
import ipaddress
import json
from pathlib import Path
import re

ROLES = {"web": ["web-a", "web-b"], "monitoring": ["zabbix"],
         "elasticsearch": ["elasticsearch"], "kibana": ["kibana"], "bastion": ["bastion"]}


def render(outputs, identity_file, ssh_config, known_hosts=None):
    machines = outputs["machines"]["value"]
    user = outputs["ssh_user"]["value"]
    roles = outputs.get("inventory_groups", {}).get("value", ROLES)
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
        raise ValueError("Invalid SSH user")
    for role_keys in roles.values():
        for key in role_keys:
            if not re.fullmatch(r"[a-z0-9-]+\.ru-central1\.internal", machines[key]["fqdn"]):
                raise ValueError("Inventory requires internal FQDNs")
    bastion_key = roles["bastion"][0]
    bastion = machines[bastion_key]["fqdn"]
    public_ip = str(ipaddress.IPv4Address(machines[bastion_key]["public_ip"]))
    config_path = Path(ssh_config).resolve().as_posix()
    inventory = {"all": {"vars": {"ansible_user": user,
                 "ansible_ssh_common_args": f'-F "{config_path}"'}, "children": {}}}
    if "admin_cidr" in outputs:
        inventory["all"]["vars"]["admin_cidr"] = outputs["admin_cidr"]["value"]
    for role, keys in roles.items():
        inventory["all"]["children"][role] = {"hosts": {machines[k]["fqdn"]: {
            "cloud_public_ip": machines[k].get('public_ip',''),
            "cloud_private_ip": machines[k].get('private_ip','')
        } for k in keys}}
    identity = Path(identity_file).expanduser().resolve().as_posix()
    if any(c in identity + config_path for c in '\r\n"'):
        raise ValueError("Unsupported character in SSH config path")
    config = (f'Host {bastion}\n    HostName {public_ip}\n    HostKeyAlias {bastion}\n    User {user}\n'
              f'    IdentityFile "{identity}"\n    IdentitiesOnly yes\n\n')
    names = " ".join(dict.fromkeys(machines[k]["fqdn"] for keys in roles.values() for k in keys if k != bastion_key))
    config += (f'Host {names}\n    User {user}\n    IdentityFile "{identity}"\n'
               f'    IdentitiesOnly yes\n    ProxyCommand ssh -F "{config_path}" -W %h:%p {bastion}\n')
    if known_hosts:
        trusted_path = Path(known_hosts).expanduser().resolve().as_posix()
        if any(c in trusted_path for c in '\r\n"'):
            raise ValueError("Unsupported character in known_hosts path")
        config = f'Host *\n    UserKnownHostsFile "{trusted_path}"\n    StrictHostKeyChecking yes\n\n' + config
    # JSON is also valid YAML; no extra Python dependencies are needed.
    return json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outputs", type=Path)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--inventory", type=Path, default=Path("ansible/inventory/hosts.yml"))
    parser.add_argument("--ssh-config", type=Path, default=Path(".local/ssh_config"))
    parser.add_argument("--known-hosts", type=Path)
    args = parser.parse_args()
    outputs = json.loads(args.outputs.read_bytes())
    inventory, config = render(outputs, args.identity, args.ssh_config, args.known_hosts)
    for path, content in [(args.inventory, inventory), (args.ssh_config, config)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Created {args.inventory} and {args.ssh_config}; verify SSH host fingerprints before deployment.")


if __name__ == "__main__":
    main()
