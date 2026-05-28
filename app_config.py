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
    "navigation": {
        "enabled": False,
        "no_hunter_timeout_sec": 1.2,
        "move_tolerance_px": 24,
        "command_cooldown_sec": 0.6,
        "dynamic_rope_x": True,
        "rope_match_threshold": 0.32,
        "rope_max_candidates_per_template": 30,
        "rope_templates": [],
        "layer_y_bounds": {},
        "layer_points": {},
        "anchors": {},
        "steps": [],
    },
    "minimap": {
        "player_color": [67, 255, 255],
        "offset": [0, 0],
        "player_color_tolerance": 12,
        "min_player_pixels": 3,
        "border_tolerance": 8,
        "use_fallback_when_not_found": False,
        "fallback_region": [0, 0, 0, 0],
        "debug_draw_region": True,
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
            merged = _merge_dict(DEFAULT_CONFIG, parsed)

            # Backward compatibility: map legacy patrol config to new navigation config
            # when navigation is not explicitly configured.
            nav_cfg = merged.get("navigation") if isinstance(merged.get("navigation"), dict) else {}
            patrol_cfg = merged.get("patrol") if isinstance(merged.get("patrol"), dict) else {}
            nav_steps = nav_cfg.get("steps") if isinstance(nav_cfg, dict) else []
            if (not nav_steps) and patrol_cfg:
                nav_cfg = _merge_dict(nav_cfg, {
                    "enabled": patrol_cfg.get("enabled", nav_cfg.get("enabled", False)),
                    "no_hunter_timeout_sec": patrol_cfg.get("no_hunter_timeout_sec", nav_cfg.get("no_hunter_timeout_sec", 1.2)),
                    "move_tolerance_px": patrol_cfg.get("move_tolerance_px", nav_cfg.get("move_tolerance_px", 24)),
                    "command_cooldown_sec": patrol_cfg.get("step_cooldown_sec", nav_cfg.get("command_cooldown_sec", 0.6)),
                    "dynamic_rope_x": patrol_cfg.get("dynamic_rope_x", nav_cfg.get("dynamic_rope_x", True)),
                    "rope_match_threshold": patrol_cfg.get("rope_match_threshold", nav_cfg.get("rope_match_threshold", 0.32)),
                    "rope_max_candidates_per_template": patrol_cfg.get("rope_max_candidates_per_template", nav_cfg.get("rope_max_candidates_per_template", 30)),
                    "rope_templates": patrol_cfg.get("rope_templates", nav_cfg.get("rope_templates", [])),
                    "layer_y_bounds": patrol_cfg.get("layer_y_bounds", nav_cfg.get("layer_y_bounds", {})),
                    "layer_points": patrol_cfg.get("layer_points", nav_cfg.get("layer_points", {})),
                    "steps": patrol_cfg.get("steps", nav_cfg.get("steps", [])),
                })
                merged["navigation"] = nav_cfg

            return merged
        except Exception as exc:
            print(f"⚠️ 配置文件读取失败，已回退默认配置: {path.name} -> {exc}")
            break

    return copy.deepcopy(DEFAULT_CONFIG)

