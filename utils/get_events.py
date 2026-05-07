import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from astrbot.api import logger

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

BEIJING_TZ = timezone(timedelta(hours=8))

MAP_NAMES = {
    "Dam": "大坝战场",
    "Dam Battleground": "大坝战场",
    "Spaceport": "太空港",
    "The Spaceport": "太空港",
    "Buried City": "掩埋废城",
    "Blue Gate": "蓝门",
    "The Blue Gate": "蓝门",
    "Stella Montis": "星辰山",
    "Riven Tides": "裂潮",
}

EVENT_NAMES = {
    "Night Raid": "夜间奇袭",
    "Electromagnetic Storm": "电磁风暴",
    "Cold Snap": "寒潮",
    "Locked Gate": "上锁的大门",
    "Matriarch": "族母",
    "Harvester": "收割者",
    "Lush Blooms": "繁茂花丛",
    "Prospecting Probes": "四处窥探的探测器",
    "Husk Graveyard": "机械坟场",
    "Uncovered Caches": "暴露的奇袭者箱",
    "Launch Tower Loot": "发射塔上的战利品",
    "Hidden Bunker": "隐藏地堡",
    "Bird City": "鸟城",
    "Beachcombing": "海滩拾荒点",
    "Close Scrutiny": "严密排查",
    "None": "无",
    "Hurricane": "飓风",
}


def _load_raw(data_dir: str) -> dict | None:
    file_path = Path(data_dir) / "data" / "events.json"
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _filter_events(raw: dict) -> dict:
    """返回按时间槽过滤后的结构化数据。

    Returns:
        {
            "current_slot": {"label": "05-07 14:00 - 05-07 15:00", "ms": 1778...},
            "next_slot":    {"label": "05-07 15:00 - 05-07 16:00", "ms": 1778...},
            "current_events": {map_en: event_dict, ...},
            "next_events":    {map_en: event_dict, ...},
            "all_maps":       [sorted unique map names],
            "cached_at_str":  "2026-05-07 14:00:00" | "未知",
        }
    """
    events = raw.get("data", [])
    now_beijing = datetime.now(BEIJING_TZ)
    current_slot_start = now_beijing.replace(minute=0, second=0, microsecond=0)
    next_slot_start = current_slot_start + timedelta(hours=1)

    current_slot_ms = int(current_slot_start.timestamp() * 1000)
    next_slot_ms = int(next_slot_start.timestamp() * 1000)

    current_events: dict[str, dict] = {}
    next_events: dict[str, dict] = {}

    for ev in events:
        st = ev.get("startTime")
        map_name = ev.get("map", "未知地图")
        if st == current_slot_ms:
            current_events[map_name] = ev
        elif st == next_slot_ms:
            next_events[map_name] = ev

    all_maps = sorted(set(list(current_events.keys()) + list(next_events.keys())))

    cached_at = raw.get("cachedAt")
    if cached_at:
        cache_time = datetime.fromtimestamp(cached_at / 1000, tz=BEIJING_TZ)
        cached_at_str = cache_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        cached_at_str = "未知"

    return {
        "current_slot": {
            "label": f"{_fmt_time(current_slot_ms)} - {_fmt_time(current_slot_ms + 3600000)}",
            "ms": current_slot_ms,
        },
        "next_slot": {
            "label": f"{_fmt_time(next_slot_ms)} - {_fmt_time(next_slot_ms + 3600000)}",
            "ms": next_slot_ms,
        },
        "current_events": current_events,
        "next_events": next_events,
        "all_maps": all_maps,
        "cached_at_str": cached_at_str,
    }


def load_and_format_events(data_dir: str) -> str:
    """读取 events.json，按当前北京时间过滤当前时段和下一时段的事件并格式化返回。"""
    raw = _load_raw(data_dir)
    if raw is None:
        return "暂无事件数据，请先使用 /arc get 下载数据。"

    events = raw.get("data", [])
    if not events:
        return "暂无事件数据"

    filtered = _filter_events(raw)

    if not filtered["all_maps"]:
        return "当前时段暂无事件"

    lines = ["🗺️ Arc Raiders 当前地图事件", "=" * 30]

    for map_name_en in filtered["all_maps"]:
        map_name_cn = MAP_NAMES.get(map_name_en, map_name_en)
        lines.append(f"\n📍 {map_name_cn} ({map_name_en})")

        current_ev = filtered["current_events"].get(map_name_en)
        next_ev = filtered["next_events"].get(map_name_en)

        if current_ev:
            name_cn = EVENT_NAMES.get(current_ev.get("name", ""), current_ev.get("name", ""))
            lines.append(f"  当前时段 ({filtered['current_slot']['label']}): {name_cn}")
        else:
            lines.append(f"  当前时段 ({filtered['current_slot']['label']}): 无事件")

        if next_ev:
            name_cn = EVENT_NAMES.get(next_ev.get("name", ""), next_ev.get("name", ""))
            lines.append(f"  下一时段 ({filtered['next_slot']['label']}): {name_cn}")
        else:
            lines.append(f"  下一时段 ({filtered['next_slot']['label']}): 无事件")

    lines.append("\n" + "=" * 30)
    lines.append(f"🕐 上一次数据更新时间: {filtered['cached_at_str']} (北京时间)")

    return "\n".join(lines)


def generate_event_image(data_dir: str) -> str | None:
    """生成事件排班图片（双卡片横向布局），返回图片文件路径。无事件时返回 None。"""
    raw = _load_raw(data_dir)
    if raw is None:
        return None

    filtered = _filter_events(raw)
    if not filtered["all_maps"]:
        return None

    if not HAS_PIL:
        logger.error("[ArcRaiders] 需要安装 Pillow 库以支持图片生成: pip install Pillow")
        return None

    # ---------- 布局参数 ----------
    outer_margin = 16  # 外环边距
    inner_pad = 18     # 卡片内部填充
    card_gap = 16      # 两个卡片之间的间隔
    icon_size = 52
    icon_gap = 10
    line_h = 52        # 每行高度
    
    font_size_title = 30
    font_size_countdown = 16
    font_size_card_title = 22
    font_size_body = 20
    font_size_footer = 12
    
    section_v_gap = 10  # 各区域间距

    icons_dir = Path(data_dir) / "data" / "icons"

    # 预计算
    remaining = _remaining_time()
    title_text = "Arc Raiders 地图事件"

    cur_maps = sorted([m for m in filtered["all_maps"] if m in filtered["current_events"]])
    next_maps = sorted([m for m in filtered["all_maps"] if m in filtered["next_events"]])
    row_count = max(len(cur_maps), len(next_maps), 1)

    # 加载字体
    font_title = _load_font(font_size_title, bold=True)
    font_countdown = _load_font(font_size_countdown)
    font_card_title = _load_font(font_size_card_title, bold=True)
    font_body = _load_font(font_size_body)
    font_footer = _load_font(font_size_footer)

    # 创建临时画布用于测量文本
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    def get_text_width(text: str, font) -> int:
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        return int(bbox[2] - bbox[0])

    # 测量标题宽度
    title_w = get_text_width(title_text, font_title)

    # 测量卡片头标题
    cur_card_title = f"正在进行 ({filtered['current_slot']['label']})"
    next_card_title = f"即将到来 ({filtered['next_slot']['label']})"
    cur_title_w = get_text_width(cur_card_title, font_card_title)
    next_title_w = get_text_width(next_card_title, font_card_title)
    card_title_w = max(cur_title_w, next_title_w)

    # 测量每行最大宽度（map name + event name）
    def measure_max_row_width(map_list: list[str], events_map: dict) -> int:
        max_w = 0
        for m in map_list:
            map_cn = MAP_NAMES.get(m, m)
            ev = events_map.get(m)
            if ev:
                ev_cn = EVENT_NAMES.get(ev.get("name", ""), ev.get("name", ""))
                text = f"{map_cn}  |  {ev_cn}"
            else:
                text = f"{map_cn}"
            w = get_text_width(text, font_body)
            max_w = max(max_w, w)
        return max_w

    cur_row_w = measure_max_row_width(cur_maps, filtered["current_events"])
    next_row_w = measure_max_row_width(next_maps, filtered["next_events"])
    row_w = max(cur_row_w, next_row_w)

    # 卡片内容宽度 = icon + gap + 文本
    card_content_w = max(icon_size + icon_gap + row_w, card_title_w)
    single_card_w = inner_pad * 2 + card_content_w

    # 总宽度
    cards_total_w = single_card_w * 2 + card_gap
    main_w = max(outer_margin * 2 + cards_total_w, outer_margin * 2 + title_w + inner_pad * 2)
    img_w = int(main_w)

    # 计算高度
    title_h = font_size_title + 8
    countdown_h = font_size_countdown + 4
    card_title_h = font_size_card_title + 8
    card_content_h = row_count * line_h
    card_inner_h = card_title_h + section_v_gap + card_content_h
    single_card_h = inner_pad * 2 + card_inner_h

    footer_h = font_size_footer + 4

    img_h = int(
        outer_margin +  # 上外边距
        title_h + 8 +  # 标题
        countdown_h + 8 +  # 倒计时
        section_v_gap +  # 间隔
        single_card_h +  # 卡片高度
        section_v_gap +  # 间隔
        footer_h + 12 +  # 底部单行（左右两段）
        outer_margin  # 下外边距
    )

    # 创建画布
    img = Image.new("RGB", (img_w, img_h), color=(30, 30, 32))
    draw = ImageDraw.Draw(img)

    # 绘制外环（深色背景已有）
    y = outer_margin

    # ---------- 标题区 ----------
    draw.text((outer_margin + inner_pad, y), title_text, fill=(255, 255, 255), font=font_title)
    y += title_h + 8

    countdown_text = f"当前轮换周期剩余：{remaining}"
    draw.text((outer_margin + inner_pad, y), countdown_text, fill=(255, 200, 80), font=font_countdown)
    y += countdown_h + section_v_gap

    # ---------- 双卡片区 ----------
    cards_y = y
    
    # 计算卡片x位置使其居中
    cards_start_x = (img_w - cards_total_w) // 2

    # 左卡片（正在进行）- 绿色
    cur_card_x = cards_start_x
    draw.rounded_rectangle(
        [cur_card_x, cards_y, cur_card_x + single_card_w, cards_y + single_card_h],
        radius=12,
        fill=(50, 50, 54),
    )
    _draw_card_content(
        draw, img, cur_card_x + inner_pad, cards_y + inner_pad,
        cur_card_title, cur_maps, filtered["current_events"],
        header_color=(100, 210, 100),
        icons_dir=icons_dir, icon_size=icon_size, icon_gap=icon_gap,
        line_h=line_h, card_title_h=card_title_h, section_v_gap=section_v_gap,
        font_card_title=font_card_title, font_body=font_body,
    )

    # 右卡片（即将到来）- 蓝色
    next_card_x = cards_start_x + single_card_w + card_gap
    draw.rounded_rectangle(
        [next_card_x, cards_y, next_card_x + single_card_w, cards_y + single_card_h],
        radius=12,
        fill=(50, 50, 54),
    )
    _draw_card_content(
        draw, img, next_card_x + inner_pad, cards_y + inner_pad,
        next_card_title, next_maps, filtered["next_events"],
        header_color=(80, 160, 255),
        icons_dir=icons_dir, icon_size=icon_size, icon_gap=icon_gap,
        line_h=line_h, card_title_h=card_title_h, section_v_gap=section_v_gap,
        font_card_title=font_card_title, font_body=font_body,
    )

    y = cards_y + single_card_h + section_v_gap

    # ---------- 底部信息（同一行：左更新 / 右来源） ----------
    footer_gray = (150, 150, 155)

    left_x = outer_margin + inner_pad
    right_text = "数据来源：metaforge.app/arc-raiders"
    right_w = get_text_width(right_text, font_footer)
    right_x = img_w - (outer_margin + inner_pad) - right_w

    def fit_text(text: str, max_width: int) -> str:
        if max_width <= 0:
            return ""
        if get_text_width(text, font_footer) <= max_width:
            return text
        ell = "..."
        ell_w = get_text_width(ell, font_footer)
        if ell_w >= max_width:
            return ""
        # 逐字符截断（数据量很小，性能足够）
        out = text
        while out and get_text_width(out, font_footer) + ell_w > max_width:
            out = out[:-1]
        return out + ell if out else ""

    left_text = f"数据更新于：{filtered['cached_at_str']} (北京时间)"
    gap = 12
    left_max_w = max(0, right_x - gap - left_x)
    left_text = fit_text(left_text, left_max_w)

    draw.text((left_x, y), left_text, fill=footer_gray, font=font_footer)
    draw.text((right_x, y), right_text, fill=footer_gray, font=font_footer)

    # 保存
    output_dir = Path(data_dir) / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "events_schedule.png"
    img.save(str(output_path), "PNG")
    logger.info(f"[ArcRaiders] 事件图片已生成: {output_path}")

    return str(output_path)


def _icon_path(icons_dir: Path, ev: dict) -> Path:
    """根据事件的 map 和 name 构造图标文件路径。"""
    map_name = ev.get("map", "unknown")
    event_name = ev.get("name", "unknown")
    raw = f"{map_name}_{event_name}"
    safe = re.sub(r"[^\w\-]", "_", raw)
    return icons_dir / f"{safe}.webp"


def _draw_card_content(draw, img, x: int, y: int,
                       card_title: str,
                       maps: list[str], events_map: dict,
                       header_color: tuple[int, int, int],
                       icons_dir: Path, icon_size: int, icon_gap: int,
                       line_h: int, card_title_h: int, section_v_gap: int,
                       font_card_title, font_body):
    """绘制单个卡片：标题 + 地图事件行。"""
    # 绘制卡片标题
    draw.text((x, y), card_title, fill=header_color, font=font_card_title)
    cy = y + card_title_h + section_v_gap

    # 绘制地图事件
    for map_en in maps:
        ev = events_map.get(map_en)
        map_cn = MAP_NAMES.get(map_en, map_en)

        text_x = x
        # 使用 textbbox 计算字体高度
        bbox = draw.textbbox((0, 0), "Test", font=font_body)
        text_height = bbox[3] - bbox[1]
        text_y = cy + (line_h - text_height) // 2 - 2

        # 图标
        if ev:
            icon_path = _icon_path(icons_dir, ev)
            icon_y = cy + (line_h - icon_size) // 2
            if icon_path.exists():
                try:
                    icon_img = Image.open(icon_path).convert("RGBA")
                    icon_img = icon_img.resize((icon_size, icon_size), Image.LANCZOS)
                    img.paste(icon_img, (x, icon_y), icon_img)
                    text_x = x + icon_size + icon_gap
                except Exception as e:
                    logger.debug(f"[ArcRaiders] 图标加载失败 {icon_path}: {e}")

        # 地图名称
        map_text = f"{map_cn}"
        draw.text((text_x, text_y), map_text, fill=(220, 220, 225), font=font_body)

        # 事件名称
        if ev:
            bbox_map = draw.textbbox((text_x, text_y), map_text, font=font_body)
            name_w = bbox_map[2] - bbox_map[0]
            ev_cn = EVENT_NAMES.get(ev.get("name", ""), ev.get("name", ""))
            ev_text = f"  |  {ev_cn}"
            draw.text((text_x + name_w, text_y), ev_text, fill=(255, 200, 80), font=font_body)
        else:
            bbox_map = draw.textbbox((text_x, text_y), map_text, font=font_body)
            name_w = bbox_map[2] - bbox_map[0]
            no_event_text = "（无）"
            draw.text((text_x + name_w, text_y), no_event_text, fill=(120, 120, 125), font=font_body)

        cy += line_h


def get_cached_time(data_dir: str) -> str:
    """读取 events.json 中的 cachedAt 并返回格式化的北京时间字符串。"""
    raw = _load_raw(data_dir)
    if raw is None:
        return "暂无数据"

    cached_at = raw.get("cachedAt")
    if not cached_at:
        return "未知"

    cache_time = datetime.fromtimestamp(cached_at / 1000, tz=BEIJING_TZ)
    return cache_time.strftime("%Y-%m-%d %H:%M:%S")


def _remaining_time() -> str:
    """计算当前轮换周期剩余时间（到下一个整点）。"""
    now = datetime.now(BEIJING_TZ)
    next_slot = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    delta = next_slot - now
    minutes = delta.seconds // 60
    seconds = delta.seconds % 60
    return f"{minutes}分{seconds:02d}秒"


def _fmt_time(ts: int) -> str:
    if not ts:
        return "--:--"
    dt = datetime.fromtimestamp(ts / 1000, tz=BEIJING_TZ)
    return dt.strftime("%m-%d %H:%M")


_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"
_FONT_CJK = _FONTS_DIR / "SarasaGothicSC.ttf"
_FONT_EMOJI = _FONTS_DIR / "NotoColorEmoji.ttf"


def _load_font(size: int, bold: bool = False):
    """加载主字体 SarasaGothicSC，加载失败回退到 PIL 默认字体。"""
    try:
        return ImageFont.truetype(str(_FONT_CJK), size)
    except (OSError, AttributeError):
        logger.warning(f"[ArcRaiders] 未找到字体: {_FONT_CJK}")
        try:
            return ImageFont.load_default(size)
        except TypeError:
            return ImageFont.load_default()
