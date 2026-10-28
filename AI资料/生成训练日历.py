#!/usr/bin/env python3
"""从 02 的实际训练生成一张连续的 SVG 月历，并更新 Markdown 图片引用。"""

import argparse
import calendar
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "02_计划与长期记录.md"
OUTPUT = ROOT / "AI资料" / "训练日历"
WIDTH, MARGIN, CELL_W, CELL_H = 1680, 28, 232, 170
GRID_Y = 154
FONT = "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
COLORS = {
    "力量": ("#dce7f2", "#345775"),
    "有氧": ("#deebe3", "#3d6555"),
    "热身": ("#eae7e0", "#686359"),
}
BACKGROUND = "#fdfcf9"
WEEKEND = "#f2f1ec"
GRID = "#deded7"
INK = "#303634"
TODAY = "#b85c47"


def read_training(markdown):
    """只读实际记录的训练小节，忽略饮食、备注和末尾模板。"""
    body = markdown.split("## 按日记录\n", 1)[1].split("## 加一天的格式", 1)[0]
    days = {}
    for block in re.split(r"(?m)^### ", body)[1:]:
        lines = block.splitlines()
        day = date.fromisoformat(lines[0].strip())
        in_training = False
        rows = []
        for line in lines[1:]:
            if line.startswith("#### "):
                in_training = line.strip() == "#### 训练"
            elif in_training and line.startswith("|"):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if len(cells) != 2 or cells[0] == "动作" or re.fullmatch(r"[- :]+", cells[0]):
                    continue
                rows.append(tuple(cells))
        if rows:
            if day in days:
                raise ValueError(f"重复的训练日期：{day}")
            days[day] = rows
    if not days:
        raise ValueError("未找到实际训练记录")
    return days


def category(action):
    if "热身" in action or "活动" in action:
        return "热身"
    if any(word in action for word in ("步行", "跑步", "爬楼机", "骑行", "游泳")):
        return "有氧"
    return "力量"


def text_width(value, size=20):
    return sum(size if unicodedata.east_asian_width(c) in "WF" else size * 0.56 for c in value)


def events(rows):
    """同类相邻动作并排，完整动作和组次保存在 SVG 提示及原始日记录中。"""
    items = []
    for action, record in rows:
        kind = category(action)
        label = {"上斜哑铃卧推": "上斜卧推"}.get(action, action)
        if kind == "有氧":
            label += " " + record.split("；", 1)[0]
        detail = f"{action}：{record}"
        if items and items[-1][0] == kind and text_width(items[-1][1] + " · " + label) <= CELL_W - 32:
            old_kind, old_label, old_detail = items[-1]
            items[-1] = (old_kind, old_label + " · " + label, old_detail + "\n" + detail)
        else:
            items.append((kind, label, detail))
    return items


def calendar_range(days):
    """补齐最早、最晚训练月份，再向两端补齐整周（周日至周六）。"""
    first, last = min(days), max(days)
    start = first.replace(day=1)
    end = last.replace(day=calendar.monthrange(last.year, last.month)[1])
    grid_start = start - timedelta(days=(start.weekday() + 1) % 7)
    grid_end = end + timedelta(days=(5 - end.weekday()) % 7)
    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        weeks.append([cursor + timedelta(days=offset) for offset in range(7)])
        cursor += timedelta(days=7)
    return start, end, weeks


def range_label(start, end):
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.year}年{start.month}月"
    if start.year == end.year:
        return f"{start.year}年{start.month}–{end.month}月"
    return f"{start.year}年{start.month}月–{end.year}年{end.month}月"


def render(days, today):
    start, end, weeks = calendar_range(days)
    heading = range_label(start, end)
    # 各周同高；动作增多时统一增加格高，避免内容被裁切。
    most_events = max(len(events(rows)) for rows in days.values())
    cell_h = max(CELL_H, 54 + most_events * 27 + 12)
    height = GRID_Y + len(weeks) * cell_h + 28
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title description">',
        f'<title id="title">{heading}实际训练月历</title>',
        '<desc id="description">周日起始。仅显示已记录的训练，空白不代表休息；重量、次数等完整明细见下方按日记录。</desc>',
        f'<rect width="{WIDTH}" height="{height}" fill="{BACKGROUND}"/>',
        f'<g font-family="{escape(FONT, quote=True)}">',
        f'<text x="{MARGIN}" y="76" font-size="52" font-weight="700" fill="{INK}">{heading}</text>',
    ]
    for i, kind in enumerate(COLORS):
        x = WIDTH - MARGIN - 300 + i * 106
        fill, color = COLORS[kind]
        parts.append(f'<rect x="{x}" y="49" width="16" height="16" rx="4" fill="{fill}"/>')
        parts.append(f'<text x="{x + 25}" y="64" font-size="20" fill="{color}">{kind}</text>')
    for col, weekday in enumerate(("周日", "周一", "周二", "周三", "周四", "周五", "周六")):
        color = "#8c8b82" if col in (0, 6) else INK
        parts.append(f'<text x="{MARGIN + (col + 0.5) * CELL_W}" y="132" text-anchor="middle" font-size="25" fill="{color}">{weekday}</text>')

    for row, week in enumerate(weeks):
        for col, day in enumerate(week):
            x, y = MARGIN + col * CELL_W, GRID_Y + row * cell_h
            in_range = start <= day <= end
            fill = WEEKEND if col in (0, 6) else BACKGROUND
            parts.append(f'<rect x="{x}" y="{y}" width="{CELL_W}" height="{cell_h}" fill="{fill}"/>')
            color = "#b9b8af" if not in_range else ("#89897e" if col in (0, 6) else INK)
            label = str(day.day) if in_range else f"{day.month}月{day.day}日"
            if in_range and day.day == 1:
                parts.append(f'<text x="{x + 14}" y="{y + 38}" font-size="23" font-weight="600" fill="#345775">{day.month}月</text>')
            if day == today and in_range:
                parts.append(f'<circle cx="{x + CELL_W - 29}" cy="{y + 29}" r="22" fill="{TODAY}"/>')
                parts.append(f'<text x="{x + CELL_W - 29}" y="{y + 39}" text-anchor="middle" font-size="28" fill="#ffffff">{day.day}</text>')
            else:
                parts.append(f'<text x="{x + CELL_W - 14}" y="{y + 39}" text-anchor="end" font-size="28" fill="{color}">{label}</text>')
            if not in_range:
                continue
            for index, (kind, label, detail) in enumerate(events(days.get(day, []))):
                event_y = y + 54 + index * 27
                bg, fg = COLORS[kind]
                size = min(20, 20 * (CELL_W - 32) / max(text_width(label), 1))
                parts.extend([
                    f'<g><title>{escape(day.isoformat() + " " + detail)}</title>',
                    f'<rect x="{x + 5}" y="{event_y}" width="{CELL_W - 10}" height="24" rx="8" fill="{bg}"/>',
                    f'<text x="{x + 14}" y="{event_y + 18}" font-size="{size:.2f}" fill="{fg}">{escape(label)}</text></g>',
                ])

    grid_bottom = GRID_Y + len(weeks) * cell_h
    for col in range(8):
        x = MARGIN + col * CELL_W
        parts.append(f'<path d="M{x},{GRID_Y} V{grid_bottom}" stroke="{GRID}" stroke-width="1"/>')
    for row in range(len(weeks) + 1):
        y = GRID_Y + row * cell_h
        parts.append(f'<path d="M{MARGIN},{y} H{WIDTH - MARGIN}" stroke="{GRID}" stroke-width="1"/>')
    parts.append('</g></svg>')
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Shanghai")).date(), help="红圈日期，默认使用上海当天日期")
    args = parser.parse_args()
    markdown = RECORD.read_text(encoding="utf-8")
    days = read_training(markdown)
    months = {(day.year, day.month) for day in days}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    name = "训练月历.svg"
    (OUTPUT / name).write_text(render(days, args.today), encoding="utf-8")
    start, end, _ = calendar_range(days)
    embed = f"![{range_label(start, end)}实际训练月历](AI资料/训练日历/{name})"
    section = "## 训练日\n\n仅显示已记录的训练；空白不代表休息。完整动作与组次见下方按日记录。\n\n" + embed + "\n\n"
    before, rest = markdown.split("## 训练日\n", 1)
    _, after = rest.split("## 按日记录\n", 1)
    RECORD.write_text(before + section + "## 按日记录\n" + after, encoding="utf-8")
    print(f"已将 {len(months)} 个月合为一张连续月历，包含 {len(days)} 个实际训练日。")


if __name__ == "__main__":
    main()
