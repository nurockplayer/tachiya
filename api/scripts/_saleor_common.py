import json
import sys
from typing import Any

import requests


ENDPOINT = "http://localhost:8000/graphql/"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin"
TIMEOUT = 30


class SaleorError(RuntimeError):
    pass


def print_error_and_exit(message: str, details: Any | None = None) -> None:
    print(message, file=sys.stderr)
    if details is not None:
        if isinstance(details, str):
            print(details, file=sys.stderr)
        else:
            print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
    raise SystemExit(1)


def execute_graphql(
    session: requests.Session,
    query: str,
    variables: dict[str, Any] | None = None,
    token: str | None = None,
    *,
    allow_top_level_errors: bool = False,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = session.post(
        ENDPOINT,
        json={"query": query, "variables": variables or {}},
        headers=headers,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    errors = payload.get("errors") or []
    if errors and not allow_top_level_errors:
        raise SaleorError(json.dumps(errors, ensure_ascii=False, indent=2))

    return payload


def get_admin_token(session: requests.Session) -> str:
    query = """
    mutation TokenCreate($email: String!, $password: String!) {
      tokenCreate(email: $email, password: $password) {
        token
        errors {
          field
          message
          code
        }
      }
    }
    """
    payload = execute_graphql(
        session,
        query,
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    result = payload["data"]["tokenCreate"]
    ensure_mutation_ok("tokenCreate", result)

    token = result.get("token")
    if not token:
        raise SaleorError("tokenCreate succeeded but no token was returned.")
    return token


def ensure_mutation_ok(name: str, result: dict[str, Any]) -> None:
    errors = result.get("errors") or []
    if errors:
        raise SaleorError(
            f"{name} returned errors:\n{json.dumps(errors, ensure_ascii=False, indent=2)}"
        )


def first_node(connection: dict[str, Any]) -> dict[str, Any] | None:
    edges = connection.get("edges") or []
    if not edges:
        return None
    return edges[0]["node"]


def match_node_by_slug(connection: dict[str, Any], slug: str) -> dict[str, Any] | None:
    for edge in connection.get("edges") or []:
        node = edge["node"]
        if node.get("slug") == slug:
            return node
    return None


def match_node_by_name(connection: dict[str, Any], name: str) -> dict[str, Any] | None:
    for edge in connection.get("edges") or []:
        node = edge["node"]
        if node.get("name") == name:
            return node
    return None


def attempt_mutations(
    session: requests.Session,
    token: str,
    attempts: list[tuple[str, str, str, dict[str, Any]]],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []

    for label, mutation_name, query, variables in attempts:
        payload = execute_graphql(
            session,
            query,
            variables,
            token,
            allow_top_level_errors=True,
        )
        top_level_errors = payload.get("errors") or []
        if top_level_errors:
            failures.append({"attempt": label, "errors": top_level_errors})
            continue

        result = payload["data"][mutation_name]
        mutation_errors = result.get("errors") or []
        if mutation_errors:
            failures.append({"attempt": label, "errors": mutation_errors})
            continue

        return result

    raise SaleorError(
        "All mutation attempts failed:\n"
        + json.dumps(failures, ensure_ascii=False, indent=2)
    )
