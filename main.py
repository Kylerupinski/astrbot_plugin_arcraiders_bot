import asyncio
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.config.astrbot_config import AstrBotConfig

from .utils.get_data import fetch_and_save_events
from .utils.get_events import get_cached_time, load_and_format_events, generate_event_image


@register("astrbot_plugin_arcraiders_bot", "Kylerupinski", "Arc Raiders 查询工具", "1.0.0")
class ArcRaidersPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._data_dir: Path = Path()

    async def initialize(self):
        self._data_dir = StarTools.get_data_dir("astrbot_plugin_arcraiders_bot")
        logger.info(f"[ArcRaiders] 插件已初始化，数据目录: {self._data_dir}")

        err = await fetch_and_save_events(str(self._data_dir))
        if err:
            logger.error(f"[ArcRaiders] 初始化获取事件数据失败: {err}")
        else:
            logger.info("[ArcRaiders] 初始化事件数据获取完成")

    @property
    def _plain_text(self) -> bool:
        output_cfg = self.config.get("output_config", {})
        return bool(output_cfg.get("plain_text_output", True))

    @filter.command_group("arc")
    def arc_group(self):
        """Arc Raiders Bot的指令组。"""

    @arc_group.command("get")
    async def cmd_get(self, event: AstrMessageEvent):
        """手动拉取最新事件数据。"""
        err = await fetch_and_save_events(str(self._data_dir))
        if err:
            yield event.plain_result(f"获取事件数据失败: {err}")
            return

        cached_time = get_cached_time(str(self._data_dir))
        yield event.plain_result(f"事件数据已更新。\n🕐 数据更新时间: {cached_time} (北京时间)")

    @arc_group.command("map")
    async def cmd_map(self, event: AstrMessageEvent):
        """查询当前及下一时段各地图事件。"""
        if self._plain_text:
            result = load_and_format_events(str(self._data_dir))
            yield event.plain_result(result)
            return

        try:
            img_path = await asyncio.to_thread(generate_event_image, str(self._data_dir))
        except Exception as e:
            logger.error(f"[ArcRaiders] 图片生成失败: {e}")
            yield event.plain_result(f"图片生成失败: {e}")
            return

        if img_path is None:
            yield event.plain_result("暂无事件数据，请先使用 /arc get 下载数据。")
            return

        yield event.image_result(img_path)

    async def terminate(self):
        pass
