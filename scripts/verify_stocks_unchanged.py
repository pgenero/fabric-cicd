"""Snapshot and compare Stocks Index definitions in the confirmed TEST workspace."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID

import requests
from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError
from azure.identity import ClientSecretCredential

from check_test_workspace import workspace_id_from_environment
from deploy_test import TEST_WORKSPACE_ID, load_credentials

API = "https://api.fabric.microsoft.com/v1"


def request(session, method, path, accepted=(200,), **kwargs):
    response = session.request(method, API + path, timeout=(10, 60), allow_redirects=False, **kwargs)
    if response.status_code not in accepted:
        raise ValueError(f"Definition check failed: HTTP {response.status_code}. No definition comparison completed.")
    return response


def get_definition(session, workspace_id, item_id):
    # Despite POST, getDefinition reads an item; it does not update the item.
    item_id = str(UUID(item_id))
    response = request(session, "POST", f"/workspaces/{workspace_id}/items/{item_id}/getDefinition", (200, 202))
    if response.status_code == 200:
        return response.json()
    operation_id = str(UUID(response.headers.get("x-ms-operation-id", "")))
    operation_path = f"/operations/{operation_id}"
    deadline = time.monotonic() + 300
    while True:
        delay = max(1, int(response.headers.get("Retry-After", "5")))
        if time.monotonic() + delay >= deadline:
            raise ValueError("Timed out reading a definition; comparison is inconclusive.")
        # Limit individual sleeps while honoring the total requested delay.
        while delay:
            pause = min(delay, 30)
            time.sleep(pause)
            delay -= pause
        response = request(session, "GET", operation_path)
        state = response.json().get("status")
        if state == "Succeeded":
            return request(session, "GET", operation_path + "/result").json()
        if state not in ("NotStarted", "Running"):
            raise ValueError("Definition export failed or returned an unknown operation state.")


def part_hashes(definition):
    parts = definition["definition"]["parts"]
    if not isinstance(parts, list) or not parts:
        raise ValueError("Empty or invalid definition parts; cannot establish a baseline.")
    hashes = {}
    for part in parts:
        path = part["path"]
        if not isinstance(path, str) or not path or path in hashes:
            raise ValueError("Invalid or duplicate definition path.")
        if part.get("payloadType") != "InlineBase64":
            raise ValueError("Unsupported definition payload type.")
        payload = base64.b64decode(part["payload"], validate=True)
        hashes[path] = hashlib.sha256(payload).hexdigest()
    return dict(sorted(hashes.items()))


def snapshot(session, workspace_id):
    items = []
    params = {"recursive": "true"}
    seen = set()
    while True:
        page = request(session, "GET", f"/workspaces/{workspace_id}/items", params=params).json()
        if not isinstance(page.get("value"), list):
            raise ValueError("Invalid workspace inventory.")
        items.extend(page["value"])
        token = page.get("continuationToken")
        if not token:
            break
        if not isinstance(token, str) or token in seen:
            raise ValueError("Invalid inventory pagination token.")
        seen.add(token)
        params = {"recursive": "true", "continuationToken": token}
    result = {}
    for item_type in ("SemanticModel", "Report"):
        matches = [item for item in items if item.get("displayName") == "Stocks Index" and item.get("type") == item_type]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one Stocks Index {item_type} in TEST; comparison cannot proceed.")
        item = matches[0]
        result[item_type] = {
            "id": item["id"],
            "displayName": item["displayName"],
            "description": item.get("description", ""),
            "folderId": item.get("folderId"),
            "parts": part_hashes(get_definition(session, workspace_id, item["id"])),
        }
        print(f"Captured Stocks Index {item_type}: {len(result[item_type]['parts'])} definition parts.")
    return result


def differences(before, after):
    changes = []
    for item_type in sorted(set(before) | set(after)):
        left, right = before.get(item_type), after.get(item_type)
        if not isinstance(left, dict) or not isinstance(right, dict):
            changes.append(f"{item_type}: item missing")
            continue
        for field in ("id", "displayName", "description", "folderId"):
            if left.get(field) != right.get(field):
                changes.append(f"{item_type}: {field} changed")
        for path in sorted(set(left["parts"]) | set(right["parts"])):
            if left["parts"].get(path) != right["parts"].get(path):
                changes.append(f"{item_type}: definition part changed: {path}")
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "after"))
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    try:
        workspace_id = workspace_id_from_environment()
        if workspace_id != TEST_WORKSPACE_ID:
            raise ValueError("Only the confirmed DataHub-Test workspace is allowed.")
        baseline = None
        if args.phase == "after":
            baseline = json.loads((args.directory / "before.json").read_text(encoding="utf-8"))
            if baseline["workspaceId"] != workspace_id or baseline["sourceSha"] != os.environ.get("GITHUB_SHA", "local"):
                raise ValueError("Baseline workspace or source commit does not match this execution.")
            if set(baseline["items"]) != {"Report", "SemanticModel"}:
                raise ValueError("Incomplete baseline.")
        credentials = load_credentials()
        with ClientSecretCredential(tenant_id=credentials["tenantId"], client_id=credentials["clientId"], client_secret=credentials["clientSecret"]) as credential:
            token = credential.get_token("https://api.fabric.microsoft.com/.default")
            with requests.Session() as session:
                session.headers.update({"Authorization": f"Bearer {token.token}"})
                current = snapshot(session, workspace_id)
        evidence = {"workspaceId": workspace_id, "sourceSha": os.environ.get("GITHUB_SHA", "local"), "items": current}
        args.directory.mkdir(parents=True, exist_ok=True)
        (args.directory / f"{args.phase}.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if baseline is None:
            print("BASELINE OK: Stocks Index report and model definitions captured.")
        else:
            changed = differences(baseline["items"], current)
            if changed:
                for change in changed:
                    print("DIFFERENCE: " + json.dumps(change, ensure_ascii=True))
                raise ValueError("Stocks Index changed; selective-deployment verification failed. No rollback was attempted.")
            print("SELECTIVITY OK: Stocks Index IDs, metadata and exported definition bytes are unchanged.")
            print("This comparison does not cover imported data, ownership, permissions or cloud connections.")
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
    except (ClientAuthenticationError, ServiceRequestError, requests.RequestException):
        print("ERROR: Authentication or network failure while reading definitions.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
