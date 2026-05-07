import re
from datetime import timezone, timedelta
from pathlib import Path

BEIJING_TZ = timezone(timedelta(hours=8))


def icon_path(icons_dir: Path, ev: dict) -> Path:
    """根据事件的 map 和 name 构造安全的图标文件路径。"""
    map_name = ev.get("map", "unknown")
    event_name = ev.get("name", "unknown")
    raw = f"{map_name}_{event_name}"
    safe = re.sub(r"[^\w\-]", "_", raw)
    return icons_dir / f"{safe}.webp"
