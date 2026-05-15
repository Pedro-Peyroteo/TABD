import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.docker
def test_docker_compose_config_is_valid():
    root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "globalshop-app" in result.stdout
    assert "globalshop-mongodb" in result.stdout
