"""Test the kit_hub paths."""

from kit_hub.params.kit_hub_params import get_kit_hub_paths


def test_kit_hub_paths() -> None:
    """Test the kit_hub paths."""
    kit_hub_paths = get_kit_hub_paths()
    assert kit_hub_paths.src_fol.name == "kit_hub"
    assert kit_hub_paths.root_fol.name == "kit-hub"
    assert kit_hub_paths.data_fol.name == "data"
