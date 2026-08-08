from pathlib import Path
from typing import ClassVar


class TemplateLoader:
    _APPROVED_TEMPLATES: ClassVar[set[str]] = {"llama", "qwen", "gemma", "mistral"}

    def __init__(self, template_root: Path | None = None):
        self._template_root = template_root or self._default_template_root()

    def list_templates(self) -> list[str]:
        if not self._template_root.exists():
            return sorted(self._APPROVED_TEMPLATES)
        return sorted(
            path.name
            for path in self._template_root.iterdir()
            if path.name in self._APPROVED_TEMPLATES and path.is_dir() and (path / "train.py").is_file()
        )

    def resolve_template(self, template_name: str) -> str:
        normalized = template_name.lower().strip()
        template_path = self._template_root / normalized / "train.py"
        if self._template_root.exists() and not template_path.is_file():
            raise ValueError(f"Training template '{template_name}' is not installed.")
        if not self._template_root.exists() and normalized not in self._APPROVED_TEMPLATES:
            raise ValueError(f"Training template '{template_name}' is not installed.")
        return normalized

    @staticmethod
    def _default_template_root() -> Path:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "gpu-agent" / "templates"
            if candidate.exists():
                return candidate
        return Path("/workspace/templates")
