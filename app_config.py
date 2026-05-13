import copy
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CONFIG_CANDIDATES = (BASE_DIR / "config.jsonc", BASE_DIR / "config.json")
DEFAULT_CONFIG = {
    "features": {
        "enable_attack": True,
        "enable_auto_buff": True,
        "enable_warning": True,
    },
    "detection": {
        "hunter_edge_threshold": 0.20,
        "hunter_gray_threshold": 0.66,
        "hunter_max_candidates_per_template": 60,
        "hunter_group_eps": 0.24,
        "hunter_track_max_miss": 3,
        "hunter_edge_only": False,
    },
    "patrol": {
        "enabled": False,
        "no_hunter_timeout_sec": 1.2,
        "move_tolerance_px": 24,
        "step_cooldown_sec": 0.6,
        "steps": [],
    },
}


def _strip_json_comments(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False
    i = 0

    while i < len(text):
        ch = text[i]
        next_two = text[i:i + 2]

        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if next_two == "//":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        if next_two == "/*":
            i += 2
            while i < len(text) - 1 and text[i:i + 2] != "*/":
                i += 1
            i += 2
            continue

        result.append(ch)
        if ch == '"':
            in_string = True
        i += 1

    return "".join(result)


def _merge_dict(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(defaults)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    for path in CONFIG_CANDIDATES:
        if not path.exists():
            continue

        try:
            raw_text = path.read_text(encoding="utf-8")
            parsed = json.loads(_strip_json_comments(raw_text))
            if not isinstance(parsed, dict):
                raise ValueError("配置文件顶层必须是对象")
            return _merge_dict(DEFAULT_CONFIG, parsed)
        except Exception as exc:
            print(f"⚠️ 配置文件读取失败，已回退默认配置: {path.name} -> {exc}")
            break

    return copy.deepcopy(DEFAULT_CONFIG)

