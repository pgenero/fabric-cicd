"""Read DataHub-Test metadata and inventory. This script never deploys."""

import json
import os
import sys
from uuid import UUID

import requests
from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError
from azure.identity import ClientSecretCredential

from deploy_test import load_credentials


EXPECTED_NAME = "DataHub-Test"
API_ROOT = "https://api.fabric.microsoft.com/v1/workspaces"


def workspace_id_from_environment() -> str:
    raw = os.environ.get("FABRIC_TEST_WORKSPACE_ID", "").strip()
    try:
        workspace_id = UUID(raw)
        if workspace_id.int == 0:
            raise ValueError()
    except ValueError:
        raise ValueError(
            "Configure the Actions variable FABRIC_TEST_WORKSPACE_ID with the full TEST workspace UUID."
        ) from None
    return str(workspace_id)


def get_json(session, url: str, params=None) -> dict:
    response = session.get(url, params=params, timeout=(10, 30), allow_redirects=False)
    if response.status_code != 200:
        # Do not print response bodies or request headers containing credentials.
        raise ValueError(f"Fabric GET failed: HTTP {response.status_code}. No changes were made.")
    try:
        payload = response.json()
    except ValueError:
        raise ValueError("Fabric returned an invalid JSON response.") from None
    if not isinstance(payload, dict):
        raise ValueError("Fabric returned an unexpected response format.")
    return payload


def check_workspace(session, workspace_id: str) -> int:
    url = f"{API_ROOT}/{workspace_id}"
    workspace = get_json(session, url)
    if workspace.get("id", "").lower() != workspace_id.lower():
        raise ValueError("The returned workspace ID does not match the configured TEST ID.")
    name = workspace.get("displayName")
    print(f"Workspace name: {json.dumps(name, ensure_ascii=True)}")
    print(f"Workspace ID: {workspace_id}")
    if name != EXPECTED_NAME:
        raise ValueError("Expected DataHub-Test. Check FABRIC_TEST_WORKSPACE_ID before continuing.")
    print(f"Capacity ID (informational): {workspace.get('capacityId') or '(not returned)'}")

    items = []
    params = {"recursive": "true"}
    seen_tokens = set()
    while True:
        page = get_json(session, f"{url}/items", params=params)
        values = page.get("value")
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError("Fabric returned an unexpected items list.")
        items.extend(values)
        token = page.get("continuationToken")
        if not token:
            break
        if not isinstance(token, str) or token in seen_tokens:
            raise ValueError("Fabric returned an invalid or repeated pagination token.")
        seen_tokens.add(token)
        # Keep using the fixed Fabric endpoint, not a response-provided URL.
        params = {"recursive": "true", "continuationToken": token}

    print(f"Items found: {len(items)}")
    for item in items:
        summary = {key: item.get(key) for key in ("displayName", "type", "id")}
        print("  - " + json.dumps(summary, ensure_ascii=True))
    print("READ ACCESS OK: TEST metadata and inventory retrieved. Deployment permissions are NOT checked.")
    print("No deployment, deletion or data refresh was requested.")
    return len(items)


def main() -> int:
    try:
        # Validate the destination before requesting a token.
        workspace_id = workspace_id_from_environment()
        credentials = load_credentials()
        with ClientSecretCredential(
            tenant_id=credentials["tenantId"],
            client_id=credentials["clientId"],
            client_secret=credentials["clientSecret"],
        ) as credential:
            token = credential.get_token("https://api.fabric.microsoft.com/.default")
            with requests.Session() as session:
                session.headers.update({"Authorization": f"Bearer {token.token}"})
                check_workspace(session, workspace_id)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ClientAuthenticationError:
        print("ERROR: Authentication failed. Check AZURE_CREDENTIALS and secret expiration.", file=sys.stderr)
        return 1
    except (ServiceRequestError, requests.RequestException):
        print("ERROR: Cannot reach Entra or Fabric. Check network connectivity and retry manually.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
