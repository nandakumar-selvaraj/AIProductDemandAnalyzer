"""Regression: unquoted commas in flow-style YAML can become invalid Docker mounts."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

source = Path(__file__).resolve().parents[3] / "deploy" / "validate_docker.py"
spec = importlib.util.spec_from_file_location("production_docker_validation", source)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def configuration():
    return {
        "services": {
            name: {
                "tmpfs": mounts,
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
            }
            for name, mounts in {
                "backend": ["/tmp:size=64m,mode=1777"],
                "migrate": ["/tmp:size=64m,mode=1777"],
                "frontend": ["/tmp:size=16m"],
            }.items()
        }
    }


def test_quoted_tmpfs_preserves_mode_and_hardening():
    validator.validate_compose_config(configuration())


@pytest.mark.parametrize("service", ["backend", "migrate"])
def test_original_yaml_comma_split_is_rejected(service):
    config = configuration()
    config["services"][service]["tmpfs"] = ["/tmp:size=64m", "mode=1777"]
    with pytest.raises(ValueError, match="single quoted absolute mount"):
        validator.validate_compose_config(config)


@pytest.mark.parametrize(
    "field,value",
    [
        ("read_only", False),
        ("cap_drop", []),
        ("security_opt", []),
    ],
)
def test_mount_fix_cannot_remove_container_safeguards(field, value):
    config = deepcopy(configuration())
    config["services"]["backend"][field] = value
    with pytest.raises(ValueError, match="safeguards are required"):
        validator.validate_compose_config(config)
