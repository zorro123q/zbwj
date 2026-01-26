import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TemplateRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class TemplateKey:
    template_id: str
    version: str


class TemplateRegistry:
    """
    Template center v1: load YAML/JSON templates from domain/templates/registry.
    File naming convention: <template_id>_<version>.yaml|yml|json
    """

    @staticmethod
    def _registry_dir() -> Path:
        return Path(__file__).resolve().parent / "registry"

    @staticmethod
    def _parse_yaml(path: Path) -> Dict[str, Any]:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise TemplateRegistryError(
                "PyYAML is required to load .yaml templates"
            ) from exc

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            raise TemplateRegistryError(f"failed to parse yaml: {path.name}") from exc

        if not isinstance(data, dict):
            raise TemplateRegistryError(f"{path.name}: template must be a mapping")
        return data

    @staticmethod
    def _parse_json(path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise TemplateRegistryError(f"failed to parse json: {path.name}") from exc

        if not isinstance(data, dict):
            raise TemplateRegistryError(f"{path.name}: template must be an object")
        return data

    @classmethod
    def _load_file(cls, path: Path) -> Dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            return cls._parse_yaml(path)
        if suffix == ".json":
            return cls._parse_json(path)
        raise TemplateRegistryError(f"unsupported template type: {path.name}")

    @staticmethod
    def _normalize_key(template_id: str, version: str) -> TemplateKey:
        tid = (template_id or "").strip()
        ver = (version or "").strip()
        if not tid:
            raise TemplateRegistryError("template_id is required")
        if not ver:
            raise TemplateRegistryError("version is required")
        return TemplateKey(template_id=tid, version=ver)

    @staticmethod
    def _validate_sections(template: Dict[str, Any], name: str) -> None:
        sections = template.get("sections")
        if not isinstance(sections, list) or len(sections) == 0:
            raise TemplateRegistryError(f"{name}: sections must be a non-empty array")

        for idx, section in enumerate(sections):
            if not isinstance(section, dict):
                raise TemplateRegistryError(f"{name}: sections[{idx}] must be an object")

            allowed_section_keys = {"title", "pick"}
            extra_keys = set(section.keys()) - allowed_section_keys
            if extra_keys:
                raise TemplateRegistryError(
                    f"{name}: sections[{idx}] has unsupported keys: {', '.join(sorted(extra_keys))}"
                )

            if "title" in section and not isinstance(section["title"], str):
                raise TemplateRegistryError(f"{name}: sections[{idx}].title must be string")

            if "pick" in section:
                pick = section["pick"]
                if not isinstance(pick, dict):
                    raise TemplateRegistryError(f"{name}: sections[{idx}].pick must be object")

                allowed_pick_keys = {"by_tag", "fallback_title_keywords", "top_k"}
                extra_pick_keys = set(pick.keys()) - allowed_pick_keys
                if extra_pick_keys:
                    raise TemplateRegistryError(
                        f"{name}: sections[{idx}].pick has unsupported keys: {', '.join(sorted(extra_pick_keys))}"
                    )

                if "by_tag" in pick and not (
                    isinstance(pick["by_tag"], list)
                    and all(isinstance(v, str) for v in pick["by_tag"])
                ):
                    raise TemplateRegistryError(
                        f"{name}: sections[{idx}].pick.by_tag must be string array"
                    )

                if "fallback_title_keywords" in pick and not (
                    isinstance(pick["fallback_title_keywords"], list)
                    and all(isinstance(v, str) for v in pick["fallback_title_keywords"])
                ):
                    raise TemplateRegistryError(
                        f"{name}: sections[{idx}].pick.fallback_title_keywords must be string array"
                    )

                if "top_k" in pick and not isinstance(pick["top_k"], int):
                    raise TemplateRegistryError(
                        f"{name}: sections[{idx}].pick.top_k must be integer"
                    )

    @classmethod
    def get(cls, template_id: str, version: str) -> Dict[str, Any]:
        key = cls._normalize_key(template_id, version)
        registry_dir = cls._registry_dir()

        if not registry_dir.exists():
            raise TemplateRegistryError("template registry directory does not exist")

        candidates = [
            registry_dir / f"{key.template_id}_{key.version}.yaml",
            registry_dir / f"{key.template_id}_{key.version}.yml",
            registry_dir / f"{key.template_id}_{key.version}.json",
        ]

        for path in candidates:
            if path.exists():
                template = cls._load_file(path)
                cls._validate_sections(template, path.name)
                return template

        raise TemplateRegistryError(
            f"template not found: {key.template_id}@{key.version}"
        )
