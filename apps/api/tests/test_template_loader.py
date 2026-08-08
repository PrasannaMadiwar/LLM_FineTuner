import pytest

from app.services.template_loader import TemplateLoader


def test_template_loader_falls_back_to_approved_templates_when_root_is_missing(tmp_path):
    loader = TemplateLoader(tmp_path / "missing")

    assert "llama" in loader.list_templates()
    assert loader.resolve_template("llama") == "llama"


def test_template_loader_rejects_unknown_template_when_root_is_missing(tmp_path):
    loader = TemplateLoader(tmp_path / "missing")

    with pytest.raises(ValueError):
        loader.resolve_template("unknown")
