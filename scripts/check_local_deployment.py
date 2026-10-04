"""Check rendered Compose defaults without starting containers or touching data."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


def rendered_services(*options: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.pop("COMPOSE_PROFILES", None)
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", os.devnull,
            "-f", str(root / "docker-compose.yml"),
            *options, "config", "--format", "json",
        ],
        cwd=root, env=environment, check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)["services"]


def check_port(service: dict, port: int) -> None:
    publications = service["ports"]
    assert len(publications) == 1, "Expected exactly one host publication"
    publication = publications[0]
    assert publication["host_ip"] == "127.0.0.1", "Publication must use host loopback"
    assert publication["target"] == port
    assert str(publication["published"]) == str(port)
    assert publication["protocol"] == "tcp"


def main() -> None:
    default = rendered_services()
    assert set(default) == {"api"}, "Default Compose must start only the API"
    check_port(default["api"], 8000)
    assert default["api"]["environment"]["API_HOST"] == "0.0.0.0"
    optional = rendered_services("--profile", "qdrant-server")
    assert set(optional) == {"api", "qdrant"}
    check_port(optional["api"], 8000)
    check_port(optional["qdrant"], 6333)
    print("Compose defaults: API only; API and optional Qdrant publish on loopback.")


if __name__ == "__main__":
    main()
