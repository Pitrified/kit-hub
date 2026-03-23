"""Test the KitHubParams class."""

from kit_hub.params.kit_hub_params import KitHubParams
from kit_hub.params.kit_hub_params import get_kit_hub_params
from kit_hub.params.kit_hub_paths import KitHubPaths
from kit_hub.params.sample_params import SampleParams


def test_kit_hub_params_singleton() -> None:
    """Test that KitHubParams is a singleton."""
    params1 = KitHubParams()
    params2 = KitHubParams()
    assert params1 is params2
    assert get_kit_hub_params() is params1


def test_kit_hub_params_init() -> None:
    """Test initialization of KitHubParams."""
    params = KitHubParams()
    assert isinstance(params.paths, KitHubPaths)
    assert isinstance(params.sample, SampleParams)


def test_kit_hub_params_str() -> None:
    """Test string representation."""
    params = KitHubParams()
    s = str(params)
    assert "KitHubParams:" in s
    assert "KitHubPaths:" in s
    assert "SampleParams:" in s
