import json
from pathlib import Path
from typing import Any, Dict, List

from flask import current_app


REQUIRED_FIELDS = [
    "script_id",
    "version",
    "name",
    "description",
    "input_vars",
    "output_schema",
    "excel_layout",
]


class PromptRegistry:
    """
    MVP: load scripts from local files (JSON preferred) under:
      - <repo>/app/prompt_scripts
      - <repo>/prompt_scripts   (optional fallback)

    Validation: required field existence only.
    No extra dependencies (YAML will be ignored).
    """

    @staticmethod
    def _candidate_dirs() -> List[Path]:
        # current_app.root_path == <repo>/app
        app_dir = Path(current_app.root_path)
        repo_root = app_dir.parent
        return [app_dir / "prompt_scripts", repo_root / "prompt_scripts"]

    @staticmethod
    def _validate(script: Dict[str, Any], filename: str) -> None:
        if not isinstance(script, dict):
            raise ValueError(f"{filename}: script must be an object")

        missing = [k for k in REQUIRED_FIELDS if k not in script]
        if missing:
            raise ValueError(f"{filename}: missing fields: {', '.join(missing)}")

        if not isinstance(script.get("script_id"), str) or not script["script_id"].strip():
            raise ValueError(f"{filename}: script_id must be a non-empty string")
        if not isinstance(script.get("version"), str) or not script["version"].strip():
            raise ValueError(f"{filename}: version must be a non-empty string")

    @classmethod
    def load_all(cls) -> List[Dict[str, Any]]:
        scripts: List[Dict[str, Any]] = []
        seen = set()  # (script_id, version)

        dirs = cls._candidate_dirs()
        for d in dirs:
            if not d.exists():
                continue

            # 只加载 JSON（不引入 PyYAML）
            for path in sorted(d.glob("*.json"), key=lambda p: p.name.lower()):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)

                    cls._validate(data, path.name)

                    key = (data.get("script_id"), data.get("version"))
                    if key in seen:
                        continue
                    seen.add(key)

                    scripts.append({k: data.get(k) for k in REQUIRED_FIELDS})
                except Exception as e:
                    # 不要让单个坏文件导致整个接口 500
                    print(f"[PromptRegistry] skip {path.name}: {e}")

            # YAML/YML 一律忽略（避免 PyYAML 依赖）
            for path in list(d.glob("*.yml")) + list(d.glob("*.yaml")):
                print(f"[PromptRegistry] ignore yaml file (no yaml support in MVP): {path.name}")

        # 稳定排序：script_id + version
        scripts.sort(key=lambda s: (str(s.get("script_id", "")), str(s.get("version", ""))))
        return scripts
