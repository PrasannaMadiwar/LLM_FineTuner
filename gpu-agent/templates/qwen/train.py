import importlib.util
from pathlib import Path


def _load_runner():
    runner_path = Path(__file__).resolve().parents[1] / "common" / "unsloth_runner.py"
    spec = importlib.util.spec_from_file_location("unsloth_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load shared Unsloth runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_training_template


if __name__ == "__main__":
    raise SystemExit(_load_runner()("qwen"))
