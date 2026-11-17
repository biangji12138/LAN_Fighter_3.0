"""Persistent local game settings."""
import json
import os
import sys
from pathlib import Path

DEFAULTS = {"nickname": "玩家", "server_ip": "127.0.0.1", "port": 50007,
            "music": True, "sfx": True, "fullscreen": False, "gamepad": True,
            "ai_level": "normal", "ai_level_p1": "normal", "ai_level_p2": "normal",
            "char_ai": True, "map": "dojo"}
AI_LEVELS = ("normal", "medium", "hard", "hell")
# 旧存档难度键改名迁移："hard" 曾是中等、"expert" 曾是困难。
AI_LEVEL_MIGRATE = {"hard": "medium", "expert": "hard"}


def config_path():
    base = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "LANFighter"
    return base / "settings.json"


def normalize_level(level, fallback):
    """把任意难度值收敛到合法档位；无法识别时回退到 fallback。"""
    level = AI_LEVEL_MIGRATE.get(level, level)
    return level if level in AI_LEVELS else fallback


def load_settings():
    result = DEFAULTS.copy()
    has_slots = False
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            has_slots = "ai_level_p1" in raw and "ai_level_p2" in raw
            for key, typ in (("nickname", str), ("server_ip", str), ("port", int),
                             ("music", bool), ("sfx", bool), ("fullscreen", bool),
                             ("gamepad", bool), ("ai_level", str), ("ai_level_p1", str),
                             ("ai_level_p2", str), ("char_ai", bool), ("map", str)):
                if type(raw.get(key)) is typ: result[key] = raw[key]
    except FileNotFoundError:
        pass  # 首次运行尚无配置文件，属正常情况
    except (ValueError, OSError):
        print("LANFighter: 配置文件损坏或不可读，已回退为默认设置", file=sys.stderr)
    result["nickname"] = result["nickname"][:12] or "玩家"
    if not 1024 <= result["port"] <= 65535: result["port"] = DEFAULTS["port"]
    result["ai_level"] = normalize_level(result["ai_level"], DEFAULTS["ai_level"])
    # 旧存档没有分槽难度：AI 对打两侧沿用原来的全局难度，免得突然掉回普通。
    result["ai_level_p1"] = normalize_level(result["ai_level_p1"], result["ai_level"])
    result["ai_level_p2"] = normalize_level(result["ai_level_p2"], result["ai_level"])
    if not has_slots:
        result["ai_level_p1"] = result["ai_level_p2"] = result["ai_level"]
    return result


def save_settings(data):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
