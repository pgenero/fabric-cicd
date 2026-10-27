"""Preview a report/model pair; publish only with --deploy and a TEST workspace ID."""

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID


REPOSITORY_DIRECTORY = Path(__file__).resolve().parents[1] / "DataHub"
SOLUTIONS = {
    "interest-rates": "Interest Rates",
    "stocks-index": "Stocks Index",
}


def load_credentials() -> dict[str, str]:
    """Read the existing GitHub JSON secret without logging its contents."""
    raw = os.environ.get("AZURE_CREDENTIALS")
    if raw is not None:
        try:
            values = json.loads(raw)
        except (ValueError, TypeError):
            raise ValueError("AZURE_CREDENTIALS must contain valid JSON.") from None
        if not isinstance(values, dict):
            raise ValueError("AZURE_CREDENTIALS must be a JSON object.")
    else:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise ValueError("Configure the repository Actions secret AZURE_CREDENTIALS.")
        # Compatibility with local sessions; GitHub uses the single JSON secret.
        values = {
            "tenantId": os.environ.get("AZURE_TENANT_ID"),
            "clientId": os.environ.get("AZURE_CLIENT_ID"),
            "clientSecret": os.environ.get("AZURE_CLIENT_SECRET"),
        }

    required = ("tenantId", "clientId", "clientSecret")
    for key in required:
        if not isinstance(values.get(key), str) or not values[key].strip():
            raise ValueError(f"Missing or invalid credential field: {key}")

    # GitHub may not automatically mask the individual fields of a JSON secret.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for key in required:
            escaped = values[key].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::add-mask::{escaped}", flush=True)

    for key in ("tenantId", "clientId"):
        try:
            if UUID(values[key]).int == 0:
                raise ValueError()
        except ValueError:
            raise ValueError(f"{key} must be a real, nonzero UUID, not example text.") from None
    if values["clientSecret"] == "TU_CLIENT_SECRET_AQUI":
        raise ValueError("Replace the example clientSecret with the actual secret value.")
    return {key: values[key] for key in required}


def selected_items(solution: str) -> list[str]:
    """Validate the local pair. This does not check Fabric or data credentials."""
    name = SOLUTIONS[solution]
    items = [f"{name}.SemanticModel", f"{name}.Report"]
    logical_ids = set()
    for item in items:
        item_directory = REPOSITORY_DIRECTORY / item
        with (item_directory / ".platform").open(encoding="utf-8") as stream:
            platform = json.load(stream)
        item_type = item.rsplit(".", 1)[1]
        metadata = platform["metadata"]
        if metadata["type"] != item_type or metadata["displayName"] != name:
            raise ValueError(f"Metadata does not match folder: {item}")
        logical_id = UUID(platform["config"]["logicalId"])
        if logical_id.int == 0 or logical_id in logical_ids:
            raise ValueError(f"Missing or duplicated logical ID: {item}")
        logical_ids.add(logical_id)

    model = REPOSITORY_DIRECTORY / items[0]
    for required_file in ("definition.pbism", "definition/model.tmdl"):
        if not (model / required_file).is_file():
            raise ValueError(f"Missing model file: {items[0]}/{required_file}")

    report = REPOSITORY_DIRECTORY / items[1]
    with (report / "definition.pbir").open(encoding="utf-8") as stream:
        definition = json.load(stream)
    model_reference = definition["datasetReference"]["byPath"]["path"]
    if (report / model_reference).resolve() != model.resolve():
        raise ValueError(f"The report does not reference its selected model: {items[1]}")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", required=True, choices=SOLUTIONS)
    parser.add_argument("--workspace-id", help="ID of the laboratory TEST workspace.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--deploy", action="store_true", help="Publish using a service principal.")
    action.add_argument("--check-auth", action="store_true", help="Request an Entra token only; do not access a workspace.")
    args = parser.parse_args()

    try:
        items = selected_items(args.solution)
        if args.workspace_id and UUID(args.workspace_id).int == 0:
            raise ValueError("The workspace ID cannot be an all-zero UUID.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Local source: {REPOSITORY_DIRECTORY}")
    print(f"Target workspace ID: {args.workspace_id or '(not configured)'}")
    print("Selected items:")
    for item in items:
        print(f"  - {item}")
    print("Deletion: disabled. Data refresh: not included.")

    if not args.deploy and not args.check_auth:
        print("PREVIEW ONLY: local pair checked; no authentication or Fabric calls.")
        return 0
    if args.deploy and not args.workspace_id:
        parser.error("--deploy requires --workspace-id with the TEST workspace ID.")

    try:
        credentials = load_credentials()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Imports stay here so preview works without credentials or the library.
    try:
        from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError
        from azure.identity import ClientSecretCredential
    except ImportError:
        print("Install requirements.txt in the virtual environment before deploying.", file=sys.stderr)
        return 1

    with ClientSecretCredential(
        tenant_id=credentials["tenantId"],
        client_id=credentials["clientId"],
        client_secret=credentials["clientSecret"],
    ) as credential:
        if args.check_auth:
            try:
                credential.get_token("https://api.fabric.microsoft.com/.default")
            except ClientAuthenticationError:
                print("Authentication failed. Check tenant ID, client ID and secret value/expiration.", file=sys.stderr)
                return 1
            except ServiceRequestError:
                print("Cannot reach Microsoft Entra. Check network/proxy connectivity.", file=sys.stderr)
                return 1
            print("AUTH OK: Entra issued a token. Workspace access and deployment are NOT checked.")
            return 0

        from fabric_cicd import FabricWorkspace, append_feature_flag, publish_all_items

        append_feature_flag("enable_experimental_features")
        append_feature_flag("enable_items_to_include")
        workspace = FabricWorkspace(
            workspace_id=args.workspace_id,
            repository_directory=str(REPOSITORY_DIRECTORY),
            environment="TEST",
            item_type_in_scope=["SemanticModel", "Report"],
            token_credential=credential,
        )
        # The library publishes the selected model and binds its report in the target.
        # Do not call unpublish_all_orphan_items for this selective exercise.
        publish_all_items(workspace, items_to_include=items)
    print("Publication completed. Verify the binding and data refresh in TEST.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
