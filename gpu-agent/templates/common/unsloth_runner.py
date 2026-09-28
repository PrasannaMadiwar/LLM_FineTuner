import argparse
import inspect
import json
import shutil
import time
from pathlib import Path
from typing import Any

DEFAULT_MODEL_IDS = {
    "llama": "meta-llama/Llama-3.1-8B-Instruct",
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
    "gemma": "google/gemma-2-9b-it",
    "mistral": "mistralai/Mistral-7B-Instruct-v0.3",
}


def run_training_template(model_family: str) -> int:
    args = _parse_args()
    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    config = _training_config(payload)
    dataset_path = Path(payload["dataset_path"])
    output_dir = Path(payload["output_dir"])
    artifact_dir = Path(payload["artifact_dir"])
    checkpoint_dir = output_dir / "checkpoints"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if config.get("dry_run"):
        _write_dry_run_outputs(model_family, output_dir, artifact_dir, checkpoint_dir)
        return 0

    _run_unsloth_training(
        model_family=model_family,
        payload=payload,
        config=config,
        dataset_path=dataset_path,
        output_dir=output_dir,
        artifact_dir=artifact_dir,
    )
    return 0


def _run_unsloth_training(
    model_family: str,
    payload: dict,
    config: dict,
    dataset_path: Path,
    output_dir: Path,
    artifact_dir: Path,
) -> None:
    # Unsloth must be imported before transformers and trl so its patches apply.
    from unsloth import FastLanguageModel  # isort: skip
    from datasets import load_dataset
    from transformers import TrainerCallback
    from trl import SFTConfig, SFTTrainer

    model_id = payload.get("model") or config.get("model_id") or DEFAULT_MODEL_IDS[model_family]
    max_sequence_length = int(config.get("max_sequence_length") or config.get("sequence_length") or 2048)
    load_in_4bit = bool(config.get("load_in_4bit", True))
    lora_rank = int(config.get("lora_rank") or config.get("r") or 16)
    lora_alpha = int(config.get("lora_alpha") or lora_rank)
    lora_dropout = float(config.get("lora_dropout", 0.0))

    started_at = time.monotonic()
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_id,
        max_seq_length=max_sequence_length,
        dtype=None,
        load_in_4bit=load_in_4bit,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_rank,
        target_modules=config.get("target_modules")
        or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        use_gradient_checkpointing=config.get("use_gradient_checkpointing", "unsloth"),
        random_state=int(config.get("seed", 3407)),
        use_rslora=bool(config.get("use_rslora", False)),
        loftq_config=config.get("loftq_config"),
    )

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    dataset = dataset.map(
        lambda row: {"text": _format_messages(tokenizer, row)},
        remove_columns=dataset.column_names,
    )

    sft_config_kwargs = {
        "output_dir": str(output_dir),
        "per_device_train_batch_size": int(config.get("batch_size", 2)),
        "gradient_accumulation_steps": int(config.get("gradient_accumulation_steps", 4)),
        "warmup_steps": int(config.get("warmup_steps", 5)),
        "num_train_epochs": float(config.get("epochs", 3)),
        "learning_rate": float(config.get("learning_rate", 2e-4)),
        "logging_steps": int(config.get("logging_steps", 1)),
        "save_strategy": str(config.get("save_strategy", "epoch")),
        "save_steps": int(config.get("save_steps", 100)),
        "save_total_limit": int(config.get("save_total_limit", 3)),
        "optim": str(config.get("optim", "adamw_8bit")),
        "weight_decay": float(config.get("weight_decay", 0.01)),
        "lr_scheduler_type": str(config.get("lr_scheduler_type", "linear")),
        "seed": int(config.get("seed", 3407)),
        "report_to": config.get("report_to", "none"),
        "dataset_text_field": "text",
        "dataset_num_proc": int(config.get("dataset_num_proc", 2)),
        "packing": bool(config.get("packing", False)),
    }
    # TRL renamed these across releases; pass whichever name the installed version accepts.
    sft_config_kwargs[_supported_name(SFTConfig, "max_length", "max_seq_length")] = max_sequence_length
    trainer_kwargs = {
        "model": model,
        "train_dataset": dataset,
        "args": SFTConfig(**sft_config_kwargs),
        "callbacks": [_live_metrics_callback(TrainerCallback, output_dir, started_at)],
    }
    trainer_kwargs[_supported_name(SFTTrainer, "processing_class", "tokenizer")] = tokenizer
    trainer = SFTTrainer(**trainer_kwargs)
    result = trainer.train(resume_from_checkpoint=config.get("resume_from_checkpoint"))

    adapter_dir = artifact_dir / "adapter"
    tokenizer_dir = artifact_dir / "tokenizer"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(tokenizer_dir))
    _copy_checkpoints(output_dir, artifact_dir / "checkpoints")
    _write_metrics(
        output_dir,
        {
            "current_epoch": float(getattr(trainer.state, "epoch", 0) or 0),
            "loss": _last_loss(trainer.state.log_history),
            "learning_rate": _last_learning_rate(trainer.state.log_history),
            "eta_seconds": 0,
            "training_duration_seconds": time.monotonic() - started_at,
            "global_step": int(getattr(trainer.state, "global_step", 0) or 0),
            "train_runtime": getattr(result, "metrics", {}).get("train_runtime"),
            "train_samples_per_second": getattr(result, "metrics", {}).get("train_samples_per_second"),
        },
    )
    (artifact_dir / "training_config.json").write_text(
        json.dumps({"model_family": model_family, "model_id": model_id, "config": config}, indent=2),
        encoding="utf-8",
    )


def _format_messages(tokenizer: Any, row: dict) -> str:
    messages = row.get("messages")
    if not isinstance(messages, list):
        raise TypeError("Dataset JSONL rows must contain a 'messages' list.")
    normalized = [
        {"role": str(message["role"]), "content": str(message["content"])}
        for message in messages
        if isinstance(message, dict) and message.get("role") and message.get("content")
    ]
    if not normalized:
        raise ValueError("Dataset row does not contain usable chat messages.")
    if hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(normalized, tokenize=False, add_generation_prompt=False)
    return "\n".join(f"{message['role']}: {message['content']}" for message in normalized)


def _training_config(payload: dict) -> dict:
    config = dict(payload.get("config") or {})
    nested = config.get("training_config")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update({key: value for key, value in config.items() if key != "training_config"})
        config = merged
    if payload.get("model"):
        config.setdefault("model_id", payload["model"])
    return config


def _copy_checkpoints(output_dir: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    # The Trainer writes checkpoint-N straight into output_dir; the dry run uses output_dir/checkpoints.
    checkpoints = sorted((output_dir / "checkpoints").glob("checkpoint-*")) or sorted(
        output_dir.glob("checkpoint-*")
    )
    for checkpoint in checkpoints:
        if checkpoint.is_dir():
            target = destination / checkpoint.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(checkpoint, target)


def _supported_name(target: Any, *candidates: str) -> str:
    parameters = inspect.signature(target.__init__).parameters
    for name in candidates:
        if name in parameters:
            return name
    return candidates[-1]


def _live_metrics_callback(callback_base: type, output_dir: Path, started_at: float) -> Any:
    """Write metrics.json on every log step so the agent can report progress mid-run."""

    class LiveMetricsCallback(callback_base):
        def __init__(self):
            self._last_loss: float | None = None

        def on_log(self, args, state, control, logs=None, **kwargs):
            logs = logs or {}
            if "loss" in logs:
                self._last_loss = float(logs["loss"])
            step = int(state.global_step or 0)
            max_steps = int(state.max_steps or 0)
            elapsed = time.monotonic() - started_at
            _write_metrics(
                output_dir,
                {
                    "current_epoch": float(state.epoch or 0),
                    "loss": self._last_loss,
                    "learning_rate": logs.get("learning_rate"),
                    "global_step": step,
                    "max_steps": max_steps,
                    "eta_seconds": elapsed / step * (max_steps - step) if step and max_steps else None,
                },
            )

    return LiveMetricsCallback()


def _write_metrics(output_dir: Path, metrics: dict) -> None:
    sanitized = {key: value for key, value in metrics.items() if value is not None}
    # Write then rename so the agent never reads a half-written file while training runs.
    temporary = output_dir / "metrics.json.tmp"
    temporary.write_text(json.dumps(sanitized, indent=2), encoding="utf-8")
    temporary.replace(output_dir / "metrics.json")


def _write_dry_run_outputs(
    model_family: str,
    output_dir: Path,
    artifact_dir: Path,
    checkpoint_dir: Path,
) -> None:
    checkpoint = checkpoint_dir / "checkpoint-1"
    checkpoint.mkdir(parents=True, exist_ok=True)
    (checkpoint / "adapter_model.safetensors").write_text("dry-run checkpoint", encoding="utf-8")
    adapter_dir = artifact_dir / "adapter"
    tokenizer_dir = artifact_dir / "tokenizer"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    tokenizer_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (tokenizer_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    _copy_checkpoints(output_dir, artifact_dir / "checkpoints")
    _write_metrics(
        output_dir,
        {
            "current_epoch": 1,
            "loss": 0.0,
            "learning_rate": 0.0,
            "eta_seconds": 0,
            "training_duration_seconds": 0.0,
            "global_step": 1,
            "dry_run": True,
        },
    )
    (artifact_dir / "training_config.json").write_text(
        json.dumps({"model_family": model_family, "dry_run": True}, indent=2),
        encoding="utf-8",
    )


def _last_loss(log_history: list[dict]) -> float | None:
    for entry in reversed(log_history):
        if "loss" in entry:
            return float(entry["loss"])
        if "train_loss" in entry:
            return float(entry["train_loss"])
    return None


def _last_learning_rate(log_history: list[dict]) -> float | None:
    for entry in reversed(log_history):
        if "learning_rate" in entry:
            return float(entry["learning_rate"])
    return None


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    return parser.parse_args()
