from pathlib import Path


def resolve_under(base_path: Path, requested_path: str | Path) -> Path:
    base = base_path.resolve()
    requested = Path(requested_path)
    candidate = requested.resolve() if requested.is_absolute() else (base / requested).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Path escapes the configured workspace.")
    return candidate


def relative_to(base_path: Path, path: Path) -> str:
    return str(path.resolve().relative_to(base_path.resolve())).replace("\\", "/")
