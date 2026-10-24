"""Run Terraform with the local IAM token and save actual API errors to a log."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

from prepare_cloud import load_env, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "apply", "output"])
    parser.add_argument("--directory", choices=["terraform", "terraform-debug"], default="terraform")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_env()
    if not os.environ.get("YC_TOKEN"):
        parser.error("YC_TOKEN is missing; save a fresh IAM token in ignored .env")
    env = os.environ.copy()
    for name in list(env):
        if name.lower() in ("http_proxy", "https_proxy", "all_proxy") or name.startswith("TF_LOG"):
            env.pop(name, None)
    windows_tf = ROOT / ".tools/terraform.exe"
    binary = str(windows_tf) if os.name == "nt" and windows_tf.exists() else "terraform"
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = local / f"{args.directory}-{args.action}-{stamp}.log"
    plan_name = "debug.tfplan" if args.directory == "terraform-debug" else "irina.tfplan"

    def run(arguments):
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen([binary, "-chdir=" + str(ROOT / args.directory), *arguments],
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8")
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            return process.wait()

    if args.action == "output":
        code = run(["output", "-json", "-no-color"])
    else:
        # Always refresh the plan before apply, including after partial failures.
        code = run(["plan", "-input=false", "-no-color", "-out=" + plan_name])
        if code == 0 and args.action == "apply":
            code = run(["apply", "-input=false", "-no-color", plan_name])
    print(f"Terraform exit: {code}; log: {log_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
