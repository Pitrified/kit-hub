"""Test that the environment variables are available."""

import os


def test_env_vars() -> None:
    """The environment var KIT_HUB_SAMPLE_ENV_VAR is available."""
    assert "KIT_HUB_SAMPLE_ENV_VAR" in os.environ
    assert os.environ["KIT_HUB_SAMPLE_ENV_VAR"] == "sample"
