"""Tests for LlmConfig."""

from pathlib import Path

from langchain_core.messages import AIMessage
from llm_core.testing.fake_chat_model import FakeChatModelConfig

from kit_hub.config.llm_config import LlmConfig


def test_llm_config_init(tmp_path: Path) -> None:
    """LlmConfig stores chat_config and prompts_fol."""
    fake_config = FakeChatModelConfig(responses=[AIMessage(content="")])
    config = LlmConfig(chat_config=fake_config, prompts_fol=tmp_path)
    assert config.prompts_fol == tmp_path
    assert config.chat_config is fake_config


def test_llm_config_to_kw(tmp_path: Path) -> None:
    """to_kw returns chat_config and prompts_fol at top level."""
    fake_config = FakeChatModelConfig(responses=[AIMessage(content="")])
    config = LlmConfig(chat_config=fake_config, prompts_fol=tmp_path)
    kw = config.to_kw()
    assert "chat_config" in kw
    assert "prompts_fol" in kw
    assert kw["prompts_fol"] == tmp_path
