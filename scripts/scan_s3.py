import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_reference(path: Path) -> Dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return {"buckets": []}
    return {"buckets": []}


def merge_discovered_buckets(
    existing_reference: Dict[str, Any],
    discovered_buckets: List[Dict[str, str]],
    now_iso: str,
) -> Dict[str, Any]:
    merged = dict(existing_reference)
    entries = list(existing_reference.get("buckets", []))
    by_name = {entry["name"]: index for index, entry in enumerate(entries) if "name" in entry}

    for bucket in discovered_buckets:
        name = bucket["name"]
        if name in by_name:
            entry = entries[by_name[name]]
            entry["last_seen_at"] = now_iso
            continue

        entries.append(
            {
                "name": name,
                "account_id": bucket["account_id"],
                "account_name": bucket["account_name"],
                "first_seen_at": now_iso,
                "last_seen_at": now_iso,
            }
        )
        by_name[name] = len(entries) - 1

    merged["buckets"] = entries
    merged["last_updated_at"] = now_iso
    return merged


def assume_role(account_id: str, role_name: str, region: str) -> Dict[str, str]:
    if boto3 is None:
        raise RuntimeError("boto3 is required")

    sts_client = boto3.client("sts", region_name=region)
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f"s3-scan-{account_id}",
    )
    credentials = response["Credentials"]
    return {
        "AccessKeyId": credentials["AccessKeyId"],
        "SecretAccessKey": credentials["SecretAccessKey"],
        "SessionToken": credentials["SessionToken"],
    }


def discover_buckets_for_account(
    account_id: str,
    account_name: str,
    role_name: str,
    region: str,
    assume_role_for_account: bool = True,
) -> List[Dict[str, str]]:
    if assume_role_for_account:
        credentials = assume_role(account_id, role_name, region)
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
    else:
        session = boto3.Session()

    s3_client = session.client("s3", region_name=region)
    response = s3_client.list_buckets()
    return [
        {
            "name": bucket["Name"],
            "account_id": account_id,
            "account_name": account_name,
        }
        for bucket in response.get("Buckets", [])
    ]


def list_accounts(region: str) -> List[Dict[str, str]]:
    org_client = boto3.client("organizations", region_name=region)
    paginator = org_client.get_paginator("list_accounts")
    accounts: List[Dict[str, str]] = []
    for page in paginator.paginate():
        for account in page.get("Accounts", []):
            if account.get("Status") == "ACTIVE":
                accounts.append(
                    {
                        "id": account["Id"],
                        "name": account.get("Name", account["Id"]),
                    }
                )
    return accounts


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover S3 buckets across AWS accounts")
    parser.add_argument("--reference-file", default="data/s3_reference.json")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--role-name", default=os.getenv("AWS_ASSUME_ROLE_NAME", "OrganizationAccountAccessRole"))
    args = parser.parse_args()

    if boto3 is None:
        print("boto3 is required. Install dependencies with pip install -r requirements.txt", file=sys.stderr)
        return 2

    reference_path = Path(args.reference_file)
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    existing_reference = load_reference(reference_path)

    sts_client = boto3.client("sts", region_name=args.region)
    caller_identity = sts_client.get_caller_identity()
    current_account_id = caller_identity["Account"]
    current_account_name = current_account_id

    discovered_buckets: List[Dict[str, str]] = []

    try:
        accounts = list_accounts(args.region)
    except Exception as exc:  # pragma: no cover - depends on AWS environment
        print(f"Organizations listing failed, falling back to current account: {exc}", file=sys.stderr)
        accounts = [{"id": current_account_id, "name": current_account_name}]

    if not accounts:
        accounts = [{"id": current_account_id, "name": current_account_name}]

    for account in accounts:
        account_id = account["id"]
        account_name = account.get("name", account_id)
        assume_role_for_account = account_id != current_account_id
        try:
            discovered_buckets.extend(
                discover_buckets_for_account(
                    account_id,
                    account_name,
                    args.role_name,
                    args.region,
                    assume_role_for_account=assume_role_for_account,
                )
            )
        except Exception as exc:  # pragma: no cover - depends on AWS environment
            print(f"Skipping account {account_id}: {exc}", file=sys.stderr)

    merged_reference = merge_discovered_buckets(existing_reference, discovered_buckets, utc_now())

    with reference_path.open("w", encoding="utf-8") as handle:
        json.dump(merged_reference, handle, indent=2)
        handle.write("\n")

    print(f"Wrote {len(merged_reference.get('buckets', []))} reference entries to {reference_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
