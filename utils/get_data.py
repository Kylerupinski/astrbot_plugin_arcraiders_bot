import aiohttp
import asyncio
import json
from datetime import datetime
from pathlib import Path

from astrbot.api import logger

from . import BEIJING_TZ, icon_path

API_URL = "https://metaforge.app/api/arc-raiders"


async def fetch_and_save_events(data_dir: str) -> str | None:
    """从 API 获取事件数据并保存到 data/events.json，同时下载图标到 data/icons/。

    返回错误信息字符串表示失败，返回 None 表示成功。
    """
    data_path = Path(data_dir) / "data"
    data_path.mkdir(parents=True, exist_ok=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/events-schedule", timeout=15) as resp:
                if resp.status != 200:
                    return f"API 请求失败，状态码: {resp.status}"
                raw = await resp.json()

            events = raw.get("data", [])

            # 保存 events.json
            file_path = data_path / "events.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)

            cached_at = raw.get("cachedAt")
            if cached_at:
                cache_time = datetime.fromtimestamp(cached_at / 1000, tz=BEIJING_TZ)
                logger.info(
                    f"[ArcRaiders] 事件数据已保存至 {file_path}，"
                    f"数据更新时间: {cache_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)"
                )
            else:
                logger.info(f"[ArcRaiders] 事件数据已保存至 {file_path}")

            # 下载图标
            icons_dir = data_path / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)

            icon_count = 0
            for ev in events:
                icon_url = ev.get("icon")
                if not icon_url:
                    continue

                filepath = icon_path(icons_dir, ev)

                if filepath.exists():
                    icon_count += 1
                    continue

                try:
                    async with session.get(icon_url, timeout=10) as icon_resp:
                        if icon_resp.status == 200:
                            icon_data = await icon_resp.read()
                            with open(filepath, "wb") as f:
                                f.write(icon_data)
                            icon_count += 1
                        else:
                            logger.warning(
                                f"[ArcRaiders] 图标下载失败 ({icon_url}): 状态码 {icon_resp.status}"
                            )
                except Exception as e:
                    logger.warning(f"[ArcRaiders] 图标下载异常 ({icon_url}): {e}")

            logger.info(f"[ArcRaiders] 图标已下载 {icon_count}/{len(events)} 个至 {icons_dir}")

    except asyncio.TimeoutError:
        return "请求超时，请稍后重试"
    except Exception as e:
        return f"请求失败: {str(e)}"

    return None
