"""UI language for the native Linux frontend: English strings are the keys."""
import os
from codexbar_paths import STATE_PATH, read_json

LANGUAGES = (("auto", "Auto"), ("en", "English"), ("zh", "中文"))

ZH = {
    # Footer / header
    "Refresh": "刷新",
    "Settings…": "设置…",
    "About": "关于",
    "Quit": "退出",
    "← Back": "← 返回",
    "Settings": "设置",
    "Save": "保存",
    # Settings
    "Language": "语言",
    "Auto follows the system language.": "自动：跟随系统语言。",
    "Auto": "自动",
    "Tray tooltip": "托盘提示",
    "Pick a provider for the tray tooltip, or leave on Highest to show all.":
        "选择托盘悬停提示显示哪个服务商，或选“最高”显示全部。",
    "Highest": "最高",
    "Open popup on": "弹窗默认打开",
    "Choose the provider tab selected when the popup opens, or use Highest.":
        "选择打开弹窗时默认选中的服务商，或选“最高”。",
    "Reset times": "重置时间",
    "How to render the “Resets …” label. Provider keeps the raw string each backend emits; "
    "Local/UTC reformat the reset timestamp with an explicit timezone.":
        "“重置”时间的显示方式。服务商：使用服务商原始文本；本地 / UTC：按指定时区重新格式化。",
    "Provider": "服务商",
    "Local": "本地",
    "UTC": "UTC",
    "Notifications": "通知",
    "Notify when quota left drops below 50% and 20%, runs out, or comes back.":
        "剩余额度低于 50%、20%，用完或恢复时发送通知。",
    "On": "开",
    "Off": "关",
    "Providers": "服务商",
    "Toggle which providers feed the bar and the popup.": "选择在状态栏和弹窗中显示哪些服务商。",
    "Config: {path}": "配置文件：{path}",
    "macOS only": "仅 macOS",
    # Usage view
    "No usage data yet. Enable a provider in Settings, sign in with its CLI, then Refresh.":
        "暂无用量数据。请在设置中启用服务商，用它的 CLI 登录，然后点刷新。",
    "Updated just now": "刚刚更新",
    "Cached — last refresh failed": "缓存数据 — 上次刷新失败",
    "Refresh failed": "刷新失败",
    "Unknown error": "未知错误",
    "Session": "会话（5 小时）",
    "Weekly": "每周",
    "Monthly": "每月",
    "Extra quota": "额外额度",
    "Credits": "额度",
    "remaining": "剩余",
    "{pct}% remaining": "剩余 {pct}%",
    "Usage unavailable": "用量不可用",
    "Reset tracked": "已跟踪重置",
    " · +{n}% next regen": " · 下次恢复 +{n}%",
    "Resets {when}": "重置：{when}",
    "in {span}": "{span}后",
    "Usage details": "用量详情",
    "No usage data for this provider.": "该服务商暂无用量数据。",
    "Plan: {plan}": "套餐：{plan}",
    "Session pace": "会话进度",
    "Weekly pace": "每周进度",
    "Budget": "预算",
    "{period}: {used} used": "{period}：已用 {used}",
    "{count} available; next expires {when}": "可用 {count} 个；最近一个 {when} 过期",
    "{count} available; no expiry": "可用 {count} 个；无过期时间",
    "None available": "无可用",
    "Monthly credit limit": "每月额度上限",
    "{title}: {amount} remaining": "{title}：剩余 {amount}",
    "Dashboard credits: {amount}": "控制台额度：{amount}",
    "Recent dashboard spend: {amount} over {days} days": "近 {days} 天控制台花费：{amount}",
    "OpenRouter balance: {amount}": "OpenRouter 余额：{amount}",
    " ({amount} used)": "（已用 {amount}）",
    "Pay-as-you-go balance: {amount}": "按量付费余额：{amount}",
    "; {amount} used": "；已用 {amount}",
    "API history: {amount} across {requests} requests": "API 历史：{requests} 次请求，共 {amount}",
    "Reset credits: {summary}": "重置额度：{summary}",
    "Subscription lookup unavailable": "无法查询订阅",
    "Monthly grant depleted": "本月赠送额度已用完",
    "Subscription renews {when}": "订阅续费：{when}",
    "Subscription expires {when}": "订阅到期：{when}",
    "Minor": "轻微故障",
    "Major": "严重故障",
    "Critical": "重大故障",
    "Maintenance": "维护中",
    # Tray
    "CodexBar Linux · Click to view usage": "CodexBar Linux · 点击查看用量",
    "cached": "缓存",
    "service issue": "服务异常",
    "Show usage": "查看用量",
    "Quit CodexBar": "退出 CodexBar",
    "{name} session depleted": "{name} 会话额度已用完",
    "0% left. Will notify when it's available again.": "剩余 0%。恢复时会再通知你。",
    "{name} session restored": "{name} 会话额度已恢复",
    "Session quota is available again.": "会话额度可以再次使用了。",
    "{name} {window} quota low": "{name} {window}额度不足",
    "{pct}% left. Below your {limit}% warning.": "剩余 {pct}%，已低于 {limit}% 提醒线。",
    "session": "会话",
    "weekly": "每周",
}


def language(state=None):
    """'zh' or 'en': the Settings choice, else the system locale."""
    choice = (state if state is not None else read_json(STATE_PATH, dict, {})).get("language", "auto")
    if choice in ("en", "zh"):
        return choice
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "zh" if value.lower().startswith("zh") else "en"
    return "en"


def t(text, **values):
    if language() == "zh":
        text = ZH.get(text, text)
    return text.format(**values) if values else text
