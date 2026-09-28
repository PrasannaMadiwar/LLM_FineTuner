from app.domain.training import ModelDefinition


class ModelRegistry:
    def __init__(self, models: list[ModelDefinition] | None = None):
        self._models = {model.model_key: model for model in (models or self._default_models())}

    def list_models(self) -> list[ModelDefinition]:
        return list(self._models.values())

    def get_model(self, model_key: str) -> ModelDefinition:
        model = self._models.get(model_key)
        if model is None:
            raise ValueError(f"Model '{model_key}' is not supported.")
        return model

    @staticmethod
    def _default_models() -> list[ModelDefinition]:
        return [
            # Small enough to fine-tune with 4-bit LoRA on an 8 GB consumer GPU.
            # Unsloth's mirror is used because it is not gated on Hugging Face.
            ModelDefinition(
                model_key="qwen2.5-1.5b",
                model_id="unsloth/Qwen2.5-1.5B-Instruct",
                display_name="Qwen2.5 1.5B Instruct",
                huggingface_repo="unsloth/Qwen2.5-1.5B-Instruct",
                template="qwen",
                sequence_length=2048,
                gpu_requirements={"recommended": "8 GB GPU (e.g. RTX 4060 / 5050)", "minimum_vram_gb": 6},
            ),
            ModelDefinition(
                model_key="llama-3.1-8b",
                model_id="meta-llama/Llama-3.1-8B-Instruct",
                display_name="Llama 3.1 8B Instruct",
                huggingface_repo="meta-llama/Llama-3.1-8B-Instruct",
                template="llama",
                sequence_length=4096,
                gpu_requirements={"recommended": "A100", "minimum_vram_gb": 24},
            ),
            ModelDefinition(
                model_key="qwen2.5-7b",
                model_id="Qwen/Qwen2.5-7B-Instruct",
                display_name="Qwen2.5 7B Instruct",
                huggingface_repo="Qwen/Qwen2.5-7B-Instruct",
                template="qwen",
                sequence_length=4096,
                gpu_requirements={"recommended": "A100", "minimum_vram_gb": 24},
            ),
            ModelDefinition(
                model_key="gemma-2-9b",
                model_id="google/gemma-2-9b-it",
                display_name="Gemma 2 9B IT",
                huggingface_repo="google/gemma-2-9b-it",
                template="gemma",
                sequence_length=4096,
                gpu_requirements={"recommended": "A100", "minimum_vram_gb": 24},
            ),
            ModelDefinition(
                model_key="mistral-7b",
                model_id="mistralai/Mistral-7B-Instruct-v0.3",
                display_name="Mistral 7B Instruct v0.3",
                huggingface_repo="mistralai/Mistral-7B-Instruct-v0.3",
                template="mistral",
                sequence_length=32768,
                gpu_requirements={"recommended": "A100", "minimum_vram_gb": 24},
            ),
        ]
