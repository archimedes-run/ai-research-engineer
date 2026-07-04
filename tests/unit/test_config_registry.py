"""S1-6: tool registry availability resolution + config file parsing."""

import textwrap

from ai_research_engineer.core import config, tool_registry


# --------------------------------------------------------------------------- #
# Registry: key:ENV requirement gates availability
# --------------------------------------------------------------------------- #
def test_key_requirement_gates_availability(monkeypatch):
    monkeypatch.delenv("FAKE_KEY", raising=False)
    tool_registry.register_tool("_probe_needs_key", lambda: "ok", requires=["key:FAKE_KEY"])

    # Missing env -> registered but not available, excluded from the toolbelt.
    assert "_probe_needs_key" in tool_registry.registered_names()
    assert tool_registry.is_available("_probe_needs_key") is False
    funcs = tool_registry.available_tools()

    # Present env -> available, included.
    monkeypatch.setenv("FAKE_KEY", "secret")
    assert tool_registry.is_available("_probe_needs_key") is True
    included = tool_registry.available_tools()
    assert len(included) == len(funcs) + 1


def test_binary_requirement(monkeypatch):
    tool_registry.register_tool("_probe_needs_binary", lambda: "ok",
                                requires=["binary:definitely-not-a-real-binary-xyz"])
    assert tool_registry.is_available("_probe_needs_binary") is False


def test_no_requirements_always_available():
    tool_registry.register_tool("_probe_free", lambda: "ok", requires=[])
    assert tool_registry.is_available("_probe_free") is True


# --------------------------------------------------------------------------- #
# Config: defaults when the file is absent; file values when present
# --------------------------------------------------------------------------- #
def test_config_defaults_when_absent(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    cfg = config.load_config(path=str(missing))
    assert cfg["search"]["web_provider"] == "none"
    assert cfg["embeddings"]["model"] == config.DEFAULT_EMBEDDINGS_MODEL
    assert cfg["ingestion"]["pdf_engine"] == config.DEFAULT_PDF_ENGINE


def test_config_file_values_layer_over_defaults(tmp_path):
    cfg_file = tmp_path / "archimedes.yaml"
    cfg_file.write_text(
        textwrap.dedent(
            """
            search:
              web_provider: tavily
            embeddings:
              model: custom/model-x
            """
        )
    )
    cfg = config.load_config(path=str(cfg_file))
    assert cfg["search"]["web_provider"] == "tavily"   # from file
    assert cfg["embeddings"]["model"] == "custom/model-x"  # from file
    assert cfg["ingestion"]["pdf_engine"] == config.DEFAULT_PDF_ENGINE  # default preserved


def test_env_overrides_config_file(tmp_path, monkeypatch):
    cfg_file = tmp_path / "archimedes.yaml"
    cfg_file.write_text("embeddings:\n  model: file/model\n")
    monkeypatch.setenv("ARCHIMEDES_CONFIG", str(cfg_file))

    # File value wins over the default...
    assert config.get_embeddings_model() == "file/model"
    # ...and the env var wins over the file.
    monkeypatch.setenv("EMBEDDINGS_MODEL", "env/model")
    assert config.get_embeddings_model() == "env/model"


def test_malformed_config_falls_back_to_defaults(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("this: is: not: valid: yaml: [unclosed")
    cfg = config.load_config(path=str(bad))
    assert cfg["ingestion"]["pdf_engine"] == config.DEFAULT_PDF_ENGINE
