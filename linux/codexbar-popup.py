#!/usr/bin/env python3
"""Native GTK3 desktop popup for CodexBar Linux CLI.

Mirrors the macOS CodexBar menu popover: a provider tab strip at the top,
the active provider's usage windows shown as flat sections separated by
hairline dividers, no card boxes, thin progress bars, light translucent
background, dark text.

Positioned before mapping by GTK/GDK. Reads the cached last.json for
instant paint, then refetches in the background.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

import re
import math
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Gio, Gdk, Pango, GdkPixbuf


def append(container, child):
    if isinstance(container, Gtk.Box):
        expand = child.get_hexpand() if container.get_orientation() == Gtk.Orientation.HORIZONTAL else child.get_vexpand()
        container.pack_start(child, expand, expand, 0)
    else:
        container.add(child)


def add_css_class(widget, name):
    widget.get_style_context().add_class(name)


def set_css_classes(widget, names):
    for name in names:
        add_css_class(widget, name)


def remaining_percent(used):
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used):
        return None
    return 100.0 - min(100.0, max(0.0, float(used)))

from codexbar_paths import CODEXBAR, CONFIG_PATH, STATE_PATH, CACHE, ICONS_DIR, read_json, write_json
POPUP_WINDOW_TITLE = os.environ.get("CODEXBAR_POPUP_WINDOW_TITLE", "CodexBar")
LAST_GOOD = CACHE / "last.json"
SCRIPT_DIR = Path(__file__).resolve().parent
WRAPPER = SCRIPT_DIR / "codexbar.sh"
_ACTIVE_FETCH = None

PROVIDER_NAMES = {
    "abacus": "Abacus AI",
    "alibaba": "Alibaba",
    "alibabatokenplan": "Alibaba Token Plan",
    "amp": "Amp",
    "antigravity": "Antigravity",
    "augment": "Augment",
    "azureopenai": "Azure OpenAI",
    "bedrock": "AWS Bedrock",
    "chutes": "Chutes",
    "clawrouter": "ClawRouter",
    "codebuff": "Codebuff",
    "codex": "Codex",
    "claude": "Claude",
    "commandcode": "Command Code",
    "copilot": "Copilot",
    "crof": "Crof",
    "crossmodel": "CrossModel",
    "cursor": "Cursor",
    "deepgram": "Deepgram",
    "deepseek": "DeepSeek",
    "devin": "Devin",
    "doubao": "Doubao",
    "elevenlabs": "ElevenLabs",
    "factory": "Droid",
    "gemini": "Gemini",
    "grok": "Grok",
    "groq": "Groq",
    "jetbrains": "JetBrains AI",
    "kilo": "Kilo",
    "kimi": "Kimi",
    "kimik2": "Kimi K2",
    "kiro": "Kiro",
    "litellm": "LiteLLM",
    "llmproxy": "LLM Proxy",
    "manus": "Manus",
    "mimo": "Xiaomi MiMo",
    "minimax": "MiniMax",
    "mistral": "Mistral",
    "moonshot": "Moonshot / Kimi API",
    "ollama": "Ollama",
    "openai": "OpenAI",
    "opencode": "OpenCode",
    "opencodego": "OpenCode Go",
    "openrouter": "OpenRouter",
    "perplexity": "Perplexity",
    "poe": "Poe",
    "qoder": "Qoder",
    "sakana": "Sakana AI",
    "stepfun": "StepFun",
    "synthetic": "Synthetic",
    "t3chat": "T3 Chat",
    "venice": "Venice",
    "vertexai": "Vertex AI",
    "warp": "Warp",
    "windsurf": "Windsurf",
    "zai": "z.ai",
    "zed": "Zed",
}

WINDOW_LABELS = {
    "primary": "Session",
    "secondary": "Weekly",
    "tertiary": "Monthly",
}

# Provider id → icon filename (without the "ProviderIcon-" prefix and ".svg").
# Most providers map to their own id; a few share an icon upstream.
PROVIDER_ICON_ALIAS = {
    "openai": "codex",
    "azureopenai": "codex",
    "alibabatokenplan": "alibaba",
    "moonshot": "kimi",
    "kimik2": "kimi",
}

# CSS mirrors the macOS menu popover: light translucent panel, dark text,
# thin hairline dividers, no card boxes, restrained accent only on the
# active provider tab.
CSS = b"""
window.codexbar-popup { background: transparent; }
.codexbar-root {
    font-family: "Inter", "Noto Sans", sans-serif; font-size: 12px;
    color: #243345; background: #f4f6f8;
    border: 1px solid #cfd7df; border-radius: 16px; min-width: 350px;
}
.codexbar-root button { background-image: none; box-shadow: none; border: none; min-height: 0; min-width: 0; }
.codexbar-tabbar { padding: 12px 16px 10px; border-bottom: 1px solid #e4e9ee; }
.codexbar-tab { padding: 7px 10px; border-radius: 8px; color: #687587; background: transparent; }
.codexbar-tab label { font-size: 11px; font-weight: 600; color: inherit; }
.codexbar-tab:hover { background: #e6ebef; }
.codexbar-tab.active { color: #136f7c; background: #deeff0; }
.codexbar-provider-icon { margin-right: 3px; }
.codexbar-body { padding: 14px 16px 10px; }
.codexbar-provider-title { font-size: 17px; font-weight: 600; color: #172c40; }
.codexbar-subtitle, .codexbar-plan { font-size: 11px; color: #748091; }
.codexbar-divider { min-height: 1px; background: #e2e7ed; margin: 10px 0; }
.codexbar-metric { padding: 12px; margin: 0 0 8px; border: 1px solid #e0e6ec; border-radius: 10px; background: #fafcfd; }
.codexbar-section-title { font-size: 12px; font-weight: 600; color: #2d4052; margin-bottom: 5px; }
.codexbar-section-detail-left { font-size: 11px; font-weight: 600; color: #267884; font-feature-settings: "tnum"; }
.codexbar-section-detail-right { font-size: 10px; color: #7a8594; }
.codexbar-credits { font-size: 20px; font-weight: 600; color: #1b3447; font-feature-settings: "tnum"; }
.codexbar-credits-label { font-size: 11px; color: #748091; }
.codexbar-error { font-size: 12px; color: #b34a48; }
.codexbar-footer { padding: 8px 10px; border-top: 1px solid #e1e7ed; }
.codexbar-footer-btn { padding: 7px 10px; border-radius: 7px; color: #6b7787; background: transparent; }
.codexbar-footer-btn label { font-size: 11px; color: inherit; }
.codexbar-footer-btn:hover { background: #e2edef; color: #176d79; }
.codexbar-footer-btn:focus { outline: 2px solid #80bac1; outline-offset: -2px; }
.codexbar-settings-title { font-size: 14px; font-weight: 600; }
.codexbar-bar-picker { padding: 4px 0 8px; }
.codexbar-settings-row { padding: 9px 0; border-bottom: 1px solid #e4e9ee; }
.codexbar-settings-name { font-size: 12px; font-weight: 500; }
.codexbar-settings-hint, .codexbar-settings-row.disabled .codexbar-settings-name { color: #929cab; font-size: 11px; }
.codexbar-settings-group { padding: 12px 0 4px; font-size: 11px; color: #6b7787; }
.codexbar-details { color: #718092; padding: 8px 0 2px; font-size: 11px; }
.codexbar-details-box { padding: 8px 0; }
levelbar.codex-usage { background: transparent; margin: 0 0 4px; }
levelbar.codex-usage trough { background: transparent; padding: 0; border: none; min-height: 6px; }
levelbar.codex-usage block.filled { background: #3896a3; border: none; min-height: 6px; border-radius: 3px; }
levelbar.codex-usage block.empty { background: #fff; border: 1px solid #dce3e9; min-height: 4px; border-radius: 3px; }
scrollbar { background: transparent; }
scrollbar slider { min-width: 4px; min-height: 24px; border: none; border-radius: 3px; background: #c7d3dc; }
"""


def load_cached() -> list:
    return [entry for entry in read_json(LAST_GOOD, list, []) if isinstance(entry, dict)]


def load_state() -> dict:
    return read_json(STATE_PATH, dict, {})


def save_state(state: dict) -> None:
    write_json(STATE_PATH, state)


_ICON_CACHE: dict[str, Path] = {}


def resolve_icon_path(pid: str) -> Path | None:
    """Return a recoloured copy of the provider SVG (dark text colour) so it
    renders against the popup's light background. Upstream SVGs use
    `fill=\"white\"`; we substitute that with our theme dark and cache."""
    name = PROVIDER_ICON_ALIAS.get(pid, pid)
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]
    src = ICONS_DIR / f"ProviderIcon-{name}.svg"
    if not src.exists():
        return None
    out_dir = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "codexbar-waybar" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.svg"
    try:
        svg = src.read_text()
        # Recolour mask-style SVGs (single white path) to dark theme text.
        recoloured = svg.replace('fill="white"', 'fill="#1c1c1e"') \
                        .replace("fill='white'", "fill='#1c1c1e'") \
                        .replace('fill="#ffffff"', 'fill="#1c1c1e"') \
                        .replace('fill="#FFFFFF"', 'fill="#1c1c1e"')
        out.write_text(recoloured)
        _ICON_CACHE[name] = out
        return out
    except OSError:
        return None


def make_icon(pid: str, size: int = 18) -> Gtk.Widget | None:
    path = resolve_icon_path(pid)
    if path is None:
        return None
    # Let GTK render the SVG at the widget's scale; no custom Cairo surfaces.
    icon = Gio.FileIcon.new(Gio.File.new_for_path(str(path)))
    img = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.MENU)
    img.set_pixel_size(size)
    add_css_class(img, "codexbar-provider-icon")
    return img


_RESET_SPACE_AFTER = re.compile(r"^([Rr]esets)(?=\S)")
_RESET_SPACE_BEFORE_PAREN = re.compile(r"(?<=\S)\(")
_RESET_SPACE_AFTER_COMMA = re.compile(r",(?=\S)")
_RESET_SPACE_BEFORE_AMPM = re.compile(r"(?<=\d)(?=[AaPp][Mm]\b)")
_RESET_STARTS_WITH_RESETS = re.compile(r"^[Rr]esets")
_RESET_RELATIVE = re.compile(r"^[Rr]esets in ")

RESET_FORMATS = ("provider", "local", "utc")


def _safe_int(value: str | None, fallback: int) -> int:
    try:
        if value is None:
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


_X11_RIGHT_OFFSET = _safe_int(os.environ.get("CODEXBAR_POPUP_X11_RIGHT_OFFSET"), 8)
_X11_TOP_OFFSET = _safe_int(os.environ.get("CODEXBAR_POPUP_X11_TOP_OFFSET"), 8)


def normalize_reset_description(text: str) -> str:
    """Mirror codexbar.sh's reset normalisation. Handles both Claude OAuth
    (\"May 17 at 6:20AM\") and Claude CLI (\"Resets6:20am(Europe/Paris)\")
    by inserting the spaces the providers omit."""
    if not text:
        return text
    text = _RESET_SPACE_AFTER.sub(r"\1 ", text)
    text = _RESET_SPACE_BEFORE_PAREN.sub(" (", text)
    text = _RESET_SPACE_AFTER_COMMA.sub(", ", text)
    text = _RESET_SPACE_BEFORE_AMPM.sub(" ", text)
    return text


def current_reset_format(state: dict | None = None) -> str:
    """Resolve the active reset time format. Env var overrides state.json;
    unknown values fall back to `provider` (current behavior)."""
    env = os.environ.get("CODEXBAR_RESET_TIME_FORMAT")
    if env in RESET_FORMATS:
        return env
    if state is None:
        state = load_state()
    value = state.get("resetTimeFormat")
    return value if value in RESET_FORMATS else "provider"


def _from_description(desc: str) -> str:
    if not desc:
        return ""
    return desc if _RESET_STARTS_WITH_RESETS.match(desc) else f"Resets {desc}"


def format_reset_label(window: dict, mode: str) -> str:
    """Render the reset label for a usage window in the chosen format.

    Mirrors `reset_phrase` in codexbar.sh so the popover and tooltip never
    drift. Returns a string like "Resets 6:12 PM CDT" or "" for no info.
    Relative phrases ("Resets in 2 hours") are preserved even in absolute
    modes, since "in 2 hours" is more useful than a wall-clock time.
    """
    clean = normalize_reset_description(window.get("resetDescription") or "")
    from_desc = _from_description(clean)
    if mode == "provider":
        return from_desc
    if _RESET_RELATIVE.match(clean):
        return from_desc
    resets_at = window.get("resetsAt")
    if not resets_at:
        return from_desc
    try:
        ts = datetime.datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return from_desc
    if mode == "utc":
        ts = ts.astimezone(datetime.timezone.utc)
        tz_suffix = "UTC"
    else:
        ts = ts.astimezone()
        tz_suffix = ts.tzname() or ""
    now = datetime.datetime.now(ts.tzinfo)
    if ts.date() == now.date():
        body = ts.strftime("%-I:%M %p")
    elif ts.year == now.year:
        body = ts.strftime("%b %-d at %-I:%M %p")
    else:
        body = ts.strftime("%b %-d %Y at %-I:%M %p")
    return f"Resets {body} {tz_suffix}".rstrip()


def fetch_fresh() -> list:
    global _ACTIVE_FETCH
    env = dict(os.environ, CODEXBAR_BIN=CODEXBAR, CODEXBAR_CONFIG=str(CONFIG_PATH))
    process = None
    try:
        process = subprocess.Popen([str(WRAPPER)], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env, start_new_session=True)
        _ACTIVE_FETCH = process
        process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    except OSError:
        pass
    finally:
        _ACTIVE_FETCH = None
    return load_cached()


def max_pct(entry: dict) -> int:
    if entry.get("error"):
        return 0
    usage = entry.get("usage") or {}
    pcts = [
        (usage.get(k) or {}).get("usedPercent")
        for k in ("primary", "secondary", "tertiary")
    ]
    pcts = [p for p in pcts if remaining_percent(p) is not None]
    return int(max(pcts)) if pcts else 0


def provider_label(pid: str) -> str:
    return PROVIDER_NAMES.get(pid, pid.replace("-", " ").title())


def entry_key(entry: dict) -> str:
    provider = entry.get("provider") or "unknown"
    account = entry.get("account")
    if account:
        return f"{provider}\0{account}"
    identity = ((entry.get("usage") or {}).get("identity") or {})
    identity_account = identity.get("accountEmail") or identity.get("accountOrganization")
    if identity_account:
        return f"{provider}\0{identity_account}"
    return str(provider)


def entry_label(entry: dict, all_entries: list | None = None) -> str:
    pid = str(entry.get("provider") or "unknown")
    label = provider_label(pid)
    if all_entries is not None:
        duplicates = sum(1 for other in all_entries if other.get("provider") == pid)
        if duplicates <= 1:
            return label
    account = entry.get("account")
    identity = ((entry.get("usage") or {}).get("identity") or {})
    account = account or identity.get("accountEmail") or identity.get("accountOrganization")
    return f"{label} · {account}" if account else label


def money(value: float, currency: str = "USD") -> str:
    symbol = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    return f"{symbol}{value:,.2f}"


def compact_number(value: int | float) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{float(value):,.2f}"


def parse_iso_datetime(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def format_datetime_label(value: str | None) -> str:
    ts = parse_iso_datetime(value)
    if ts is None:
        return ""
    ts = ts.astimezone()
    now = datetime.datetime.now(ts.tzinfo)
    if ts.date() == now.date():
        return ts.strftime("%-I:%M %p %Z")
    if ts.year == now.year:
        return ts.strftime("%b %-d at %-I:%M %p %Z")
    return ts.strftime("%b %-d %Y at %-I:%M %p %Z")


def summarize_status(entry: dict) -> str | None:
    status = entry.get("status")
    if not isinstance(status, dict):
        return None
    indicator = status.get("indicator")
    description = status.get("description")
    if not indicator and not description:
        return None
    label = str(indicator or "unknown").replace("_", " ").title()
    return f"{label}: {description}" if description else label


def summarize_pace(entry: dict) -> list[str]:
    pace = entry.get("pace")
    if not isinstance(pace, dict):
        return []
    lines: list[str] = []
    for key, title in (("primary", "Session pace"), ("secondary", "Weekly pace")):
        data = pace.get(key)
        if isinstance(data, dict) and data.get("summary"):
            lines.append(f"{title}: {data['summary']}")
    return lines


def summarize_provider_cost(usage: dict) -> str | None:
    cost = usage.get("providerCost")
    if not isinstance(cost, dict):
        return None
    used = cost.get("used")
    limit = cost.get("limit")
    currency = str(cost.get("currencyCode") or "USD")
    period = cost.get("period") or "Budget"
    if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
        return f"{period}: {money(float(used), currency)} / {money(float(limit), currency)}"
    if isinstance(used, (int, float)):
        return f"{period}: {money(float(used), currency)} used"
    return None


def summarize_reset_credits(usage: dict) -> str | None:
    snapshot = usage.get("codexResetCredits")
    if not isinstance(snapshot, dict):
        return None
    credits = [
        c for c in snapshot.get("credits", [])
        if isinstance(c, dict) and c.get("status") == "available"
    ]
    available = snapshot.get("availableCount")
    count = int(available) if isinstance(available, int) else len(credits)
    expiring = sorted(
        (c for c in credits if c.get("expires_at")),
        key=lambda c: c.get("expires_at") or "")
    if expiring:
        expiry = format_datetime_label(expiring[0].get("expires_at"))
        if expiry:
            return f"{count} available; next expires {expiry}"
    if count:
        return f"{count} available; no expiry"
    return "None available"


def summarize_credit_limit(limit: dict | None) -> str | None:
    if not isinstance(limit, dict):
        return None
    title = limit.get("title") or "Monthly credit limit"
    used = limit.get("used")
    cap = limit.get("limit")
    remaining = limit.get("remaining")
    if isinstance(used, (int, float)) and isinstance(cap, (int, float)) and cap > 0:
        return f"{title}: {money(float(used))} / {money(float(cap))}"
    if isinstance(remaining, (int, float)):
        return f"{title}: {money(float(remaining))} remaining"
    return None


def summarize_openai_dashboard(entry: dict) -> list[str]:
    dashboard = entry.get("openaiDashboard")
    if not isinstance(dashboard, dict):
        return []
    lines: list[str] = []
    account_plan = dashboard.get("accountPlan")
    if account_plan:
        lines.append(f"Plan: {account_plan}")
    credits = dashboard.get("creditsRemaining")
    if isinstance(credits, (int, float)):
        lines.append(f"Dashboard credits: {money(float(credits))}")
    limit = summarize_credit_limit(dashboard.get("codexCreditLimit"))
    if limit:
        lines.append(limit)
    breakdown = dashboard.get("usageBreakdown") or dashboard.get("dailyBreakdown") or []
    if isinstance(breakdown, list) and breakdown:
        recent = breakdown[:7]
        total = sum(
            float(day.get("totalCreditsUsed", 0))
            for day in recent
            if isinstance(day, dict) and isinstance(day.get("totalCreditsUsed"), (int, float))
        )
        if total > 0:
            lines.append(f"Recent dashboard spend: {money(total)} over {len(recent)} days")
    return lines


def summarize_usage_details(usage: dict) -> list[str]:
    lines: list[str] = []
    cost = summarize_provider_cost(usage)
    if cost:
        lines.append(cost)

    openrouter = usage.get("openRouterUsage")
    if isinstance(openrouter, dict):
        balance = openrouter.get("balance")
        total_usage = openrouter.get("totalUsage")
        if isinstance(balance, (int, float)):
            text = f"OpenRouter balance: {money(float(balance))}"
            if isinstance(total_usage, (int, float)):
                text += f" ({money(float(total_usage))} used)"
            lines.append(text)

    sakana = usage.get("sakanaPayAsYouGo")
    if isinstance(sakana, dict):
        balance = sakana.get("creditBalance")
        total = sakana.get("periodUsageTotal")
        if isinstance(balance, (int, float)):
            text = f"Pay-as-you-go balance: {money(float(balance))}"
            if isinstance(total, (int, float)):
                text += f"; {money(float(total))} used"
            lines.append(text)

    openai_api = usage.get("openAIAPIUsage")
    if isinstance(openai_api, dict):
        daily = openai_api.get("daily")
        if isinstance(daily, list) and daily:
            total_cost = sum(
                float(day.get("costUSD", 0))
                for day in daily
                if isinstance(day, dict) and isinstance(day.get("costUSD"), (int, float))
            )
            requests = sum(
                int(day.get("requests", 0))
                for day in daily
                if isinstance(day, dict) and isinstance(day.get("requests"), int)
            )
            lines.append(f"API history: {money(total_cost)} across {requests:,} requests")

    reset_credits = summarize_reset_credits(usage)
    if reset_credits:
        lines.append(f"Reset credits: {reset_credits}")

    if usage.get("commandCodeSubscriptionEnrichmentUnavailable"):
        lines.append("Subscription lookup unavailable")
    if usage.get("commandCodeMonthlyGrantDepleted"):
        lines.append("Monthly grant depleted")

    expires = format_datetime_label(usage.get("subscriptionExpiresAt"))
    renews = format_datetime_label(usage.get("subscriptionRenewsAt"))
    if renews:
        lines.append(f"Subscription renews {renews}")
    elif expires:
        lines.append(f"Subscription expires {expires}")
    return lines


def default_provider(data: list, state: dict | None = None) -> str | None:
    """Pick the configured popup provider, or the highest used% as fallback."""
    if not data:
        return None
    if state is None:
        state = load_state()
    preferred = state.get("popupProvider")
    if isinstance(preferred, str) and preferred:
        matches = [entry for entry in data if entry.get("provider") == preferred]
        if matches:
            healthy_matches = [entry for entry in matches if not entry.get("error")]
            return entry_key((healthy_matches or matches)[0])
    healthy = [entry for entry in data if not entry.get("error")]
    pool = healthy or data
    return entry_key(max(pool, key=max_pct))

def load_full_config() -> dict:
    # Settings never spawn a CLI or perform network I/O on the GTK thread.
    config = read_json(CONFIG_PATH, dict, {"version": 1, "providers": [{"id": "codex", "enabled": True}]})
    by_id = {p["id"]: p for p in config.get("providers", []) if isinstance(p, dict) and isinstance(p.get("id"), str)}
    return {**config, "providers": [by_id.get(pid, {"id": pid, "enabled": False})
            for pid in sorted(set(PROVIDER_NAMES) | set(by_id))]}


def save_config(enabled: dict[str, bool]) -> None:
    # Preserve tokens, per-provider options, and unknown upstream fields.
    config = read_json(CONFIG_PATH, dict, {"version": 1, "providers": []})
    providers = {p["id"]: dict(p) for p in config.get("providers", []) if isinstance(p, dict) and isinstance(p.get("id"), str)}
    for pid, on in enabled.items():
        providers.setdefault(pid, {"id": pid})["enabled"] = bool(on)
    config["providers"] = list(providers.values())
    write_json(CONFIG_PATH, config)


def open_text_file(path: str) -> None:
    """Open a file in a real text editor.

    Resolution order (first hit wins):
      1. $CODEXBAR_EDITOR — explicit override (graphical command line).
      2. $VISUAL / $EDITOR — terminal editor, opened in a detected terminal.
      3. Common GUI editors discovered on PATH.
      4. xdg-open as a last resort (which is what was wrong before — it sends
         JSON to the browser on most setups).
    """
    explicit = os.environ.get("CODEXBAR_EDITOR")
    if explicit:
        subprocess.Popen([*explicit.split(), path])
        return

    gui_editors = [
        "code", "codium", "code-oss",
        "zed",
        "gnome-text-editor", "gedit", "kate", "mousepad", "xed", "leafpad",
        "sublime_text", "subl",
    ]
    for editor in gui_editors:
        which = subprocess.run(["which", editor], capture_output=True, text=True)
        if which.returncode == 0 and which.stdout.strip():
            subprocess.Popen([editor, path])
            return

    terminal_editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if terminal_editor:
        terminals = [
            ("kitty", ["kitty", "-e"]),
            ("alacritty", ["alacritty", "-e"]),
            ("foot", ["foot"]),
            ("wezterm", ["wezterm", "start", "--"]),
            ("gnome-terminal", ["gnome-terminal", "--"]),
            ("konsole", ["konsole", "-e"]),
            ("xterm", ["xterm", "-e"]),
        ]
        for term, cmd in terminals:
            which = subprocess.run(["which", term], capture_output=True, text=True)
            if which.returncode == 0:
                subprocess.Popen([*cmd, *terminal_editor.split(), path])
                return

    # Last resort. Usually opens the browser for .json — which is exactly what
    # we were trying to avoid — but better than silently failing.
    subprocess.Popen(["xdg-open", path])


class CodexBarPopup(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.codexbar.linux.popup")
        self.window: Gtk.Window | None = None
        self.data: list = []
        self.active_pid: str | None = None
        self.tab_buttons: dict[str, Gtk.Button] = {}
        self.view: str = "usage"             # "usage" | "settings"
        self.settings_switches: dict[str, Gtk.Switch] = {}
        self.expanded_details = set()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()
        self.refreshing = False
        self.anchor = None
        self.hidden_at = 0.0
        self.seat = None
        for name, callback, signature in [
            ("toggle", self._toggle_action, "(ii)"),
            ("hide", lambda *_: self.hide_window(), None),
            ("quit", lambda *_: self.quit(), None),
        ]:
            action = Gio.SimpleAction.new(name, GLib.VariantType.new(signature) if signature else None)
            action.connect("activate", callback)
            self.add_action(action)
        GLib.timeout_add_seconds(60, self._periodic_refresh)
        self.refresh(background=True)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)

    def do_shutdown(self):
        self.hide_window()
        if _ACTIVE_FETCH and _ACTIVE_FETCH.poll() is None:
            try:
                os.killpg(_ACTIVE_FETCH.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        Gtk.Application.do_shutdown(self)

    def _periodic_refresh(self):
        self.refresh(background=True)
        return True

    def _toggle_action(self, _action, parameter):
        self.anchor = parameter.unpack()
        if time.monotonic() - self.hidden_at > 0.3:
            self.do_activate()

    def quit_all(self):
        group = Gio.DBusActionGroup.get(Gio.bus_get_sync(Gio.BusType.SESSION, None),
            "dev.codexbar.linux.tray", "/dev/codexbar/linux/tray")
        group.activate_action("quit", None)
        self.quit()

    def hide_window(self):
        if self.window and self.window.has_grab():
            self.window.grab_remove()
        if self.seat:
            self.seat.ungrab()
            self.seat = None
        if self.window and self.window.get_visible():
            self.hidden_at = time.monotonic()
            self.window.hide()
        return True

    def _outside_click(self, _win, event):
        x, y = self.window.get_position()
        width, height = self.window.get_size()
        if not (x <= event.x_root < x + width and y <= event.y_root < y + height):
            return self.hide_window()
        return False

    def _key_press(self, _win, event):
        if event.keyval == Gdk.KEY_Escape:
            return self.hide_window()
        return False

    def do_activate(self):
        if self.window is None:
            self.window = self.build_window()
        elif self.window.get_visible():
            self.hide_window()
            return
        # A native TOPLEVEL with POPUP_MENU hint keeps X11 input coordinates correct
        # at HiDPI scales. Position before mapping, without opacity/frame polling.
        display = self.window.get_display()
        ax, ay = self.anchor or (0, 28)
        monitor = display.get_monitor_at_point(ax, ay)
        bounds = monitor.get_workarea()
        self.content_scroll.set_max_content_height(max(160, min(720, bounds.height - 220)))
        if self.view == "usage":
            self.active_pid = default_provider(self.data)
            self.render()
        self.window.get_child().show_all()
        minimum, natural = self.window.get_preferred_size()
        width, height = natural.width, min(natural.height, bounds.height - 8)
        x = max(bounds.x + 4, min(ax - width + 24, bounds.x + bounds.width - width - 4))
        y = max(bounds.y, min(ay + 4, bounds.y + bounds.height - height - 4))
        self.window.realize()
        self.window.resize(width, height)
        self.window.move(x, y)
        self.window.show()
        self.window.get_window().focus(Gdk.CURRENT_TIME)
        self.window.grab_add()
        seat = display.get_default_seat()
        status = seat.grab(self.window.get_window(), Gdk.SeatCapabilities.ALL_POINTING | Gdk.SeatCapabilities.KEYBOARD,
                           False, None, None, None, None)
        if status == Gdk.GrabStatus.SUCCESS:
            self.seat = seat
        print("Native popup mapped", (x, y, width, height), flush=True)

    def _make_pill(self, label: str, css_classes: list[str], on_click,
                   *, icon_pid: str | None = None) -> Gtk.Widget:
        """A clickable pill made from Gtk.Box + Gtk.Label so we bypass
        Gtk.Button styling. Optionally prefixes a provider SVG icon."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        if icon_pid:
            icon = make_icon(icon_pid, size=16)
            if icon is not None:
                append(box, icon)
        lbl = Gtk.Label(label=label)
        append(box, lbl)
        button = Gtk.Button()
        set_css_classes(button, css_classes)
        button.add(box)
        button.connect("clicked", lambda *_: on_click())
        return button

    def build_window(self) -> Gtk.Window:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.add_window(win)
        add_css_class(win, "codexbar-popup")
        win.set_title(POPUP_WINDOW_TITLE)
        visual = win.get_screen().get_rgba_visual()
        if visual:
            win.set_visual(visual)
        win.set_decorated(False)
        win.set_resizable(False)
        win.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_default_size(350, -1)
        win.connect("delete-event", lambda *_: self.hide_window())
        win.connect("key-press-event", self._key_press)
        win.connect("button-press-event", self._outside_click)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        add_css_class(root, "codexbar-root")
        win.add(root)

        self.tabbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        add_css_class(self.tabbar, "codexbar-tabbar")
        self.tab_scroll = Gtk.ScrolledWindow()
        self.tab_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.tab_scroll.set_propagate_natural_height(True)
        self.tab_scroll.add(self.tabbar)
        append(root, self.tab_scroll)

        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        add_css_class(self.body, "codexbar-body")
        self.content_scroll = Gtk.ScrolledWindow()
        self.content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.content_scroll.set_propagate_natural_height(True)
        self.content_scroll.set_propagate_natural_width(True)
        self.content_scroll.set_max_content_height(720)
        self.content_scroll.add(self.body)
        append(root, self.content_scroll)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        add_css_class(footer, "codexbar-footer")
        for label, callback in [
            ("Refresh", lambda: self.refresh(background=True)),
            ("Settings…", self._on_settings_call),
            ("About", self._on_about_call),
            ("Quit", self.quit_all),
        ]:
            row = self._make_pill(label, ["codexbar-footer-btn"], callback)
            row.set_hexpand(True)
            append(footer, row)
        append(root, footer)

        self.data = load_cached()
        self.active_pid = default_provider(self.data)
        if os.environ.get("CODEXBAR_INITIAL_VIEW") == "settings":
            self.view = "settings"
        self.render()
        self.refresh(background=True)
        return win

    def _on_key(self, _ctl, keyval, _kc, _state):
        if keyval == 0xff1b:  # Escape
            self.hide_window()
            return True
        return False

    def _on_settings_call(self):
        self.settings_switches.clear()
        self.view = "settings"
        self.render()

    def _on_about_call(self):
        self.hide_window()
        subprocess.Popen(["xdg-open", "https://github.com/AidenLyu/CodexBar-Linux"])

    def _on_settings_back(self):
        self.view = "usage"
        self.render()

    def _on_settings_save(self):
        enabled = {pid: sw.get_active() for pid, sw in self.settings_switches.items()}
        save_config(enabled)
        self.view = "usage"
        self.render()
        self.refresh(background=True)
        # Nudge waybar so the bar reflects the new provider list without
        # waiting for the next interval. The signal is wired up in codexbar.jsonc.
        # Native tray reads this preference on its next update.

    def refresh(self, *, background: bool):
        if self.refreshing:
            return
        self.refreshing = True
        def worker():
            try:
                new_data = fetch_fresh()
            except Exception:
                new_data = load_cached()
            GLib.idle_add(self._apply_refresh, new_data)
        if background:
            Thread(target=worker, daemon=True).start()
        else:
            self._apply_refresh(fetch_fresh())

    def _apply_refresh(self, new_data: list) -> bool:
        self.refreshing = False
        self.data = new_data
        if self.active_pid is None or not any(entry_key(e) == self.active_pid for e in new_data):
            self.active_pid = default_provider(new_data)
        if self.window is not None and self.view != "settings":
            self.render()
        return False

    def render(self):
        self._clear(self.tabbar)
        self._clear(self.body)
        if self.view == "settings":
            self._render_settings_header()
            self._render_settings_body()
        else:
            self._render_usage_header()
            self._render_usage_body()
        self.tabbar.show_all()
        self.body.show_all()

    def _render_usage_header(self):
        if not self.data:
            append(self.tabbar, Gtk.Label(label="CodexBar"))
            return
        self.tab_buttons.clear()
        for entry in self.data:
            pid = entry.get("provider", "")
            key = entry_key(entry)
            classes = ["codexbar-tab"]
            if key == self.active_pid:
                classes.append("active")
            pill = self._make_pill(
                entry_label(entry, self.data),
                classes,
                lambda k=key: self._select(k),
                icon_pid=pid)
            append(self.tabbar, pill)
            self.tab_buttons[key] = pill
        append(self.tabbar, Gtk.Box(hexpand=True))

    def _render_usage_body(self):
        if not self.data:
            append(self.body, Gtk.Label(label="No usage data yet. Enable a provider in Settings, sign in with its CLI, then Refresh.", wrap=True, max_width_chars=38, xalign=0))
            return
        active = next((e for e in self.data if entry_key(e) == self.active_pid), None)
        if active is None:
            return
        self._render_provider(active)

    def _render_settings_header(self):
        back = self._make_pill("← Back", ["codexbar-tab"], self._on_settings_back)
        append(self.tabbar, back)
        title = Gtk.Label(label="Settings", xalign=0.0, hexpand=True)
        add_css_class(title, "codexbar-settings-title")
        append(self.tabbar, title)
        save = self._make_pill("Save", ["codexbar-tab", "active"], self._on_settings_save)
        append(self.tabbar, save)

    def _render_settings_body(self):
        pending = {pid: switch.get_active() for pid, switch in self.settings_switches.items()}
        self.settings_switches.clear()
        cfg = load_full_config()
        existing = {p.get("id"): bool(p.get("enabled")) for p in cfg.get("providers", [])}
        existing.update(pending)

        # --- Section: which provider shows in the bar ---
        bar_title = Gtk.Label(label="Tray tooltip", xalign=0.0)
        add_css_class(bar_title, "codexbar-section-title")
        append(self.body, bar_title)
        bar_hint = Gtk.Label(
            label="Pick a provider for the tray tooltip, or leave on Highest to show all.",
            xalign=0.0, wrap=True, max_width_chars=44)
        add_css_class(bar_hint, "codexbar-subtitle")
        append(self.body, bar_hint)
        append(self.body, self._build_bar_provider_picker(existing))
        append(self.body, self._divider())

        # --- Section: which provider is selected when the popup opens ---
        popup_title = Gtk.Label(label="Open popup on", xalign=0.0)
        add_css_class(popup_title, "codexbar-section-title")
        append(self.body, popup_title)
        popup_hint = Gtk.Label(
            label="Choose the provider tab selected when the popup opens, or use Highest.",
            xalign=0.0, wrap=True, max_width_chars=44)
        add_css_class(popup_hint, "codexbar-subtitle")
        append(self.body, popup_hint)
        append(self.body, self._build_popup_provider_picker(existing))

        # Divider between sections.
        append(self.body, self._divider())

        # --- Section: reset time format ---
        reset_title = Gtk.Label(label="Reset times", xalign=0.0)
        add_css_class(reset_title, "codexbar-section-title")
        append(self.body, reset_title)
        reset_hint = Gtk.Label(
            label="How to render the “Resets …” label. Provider keeps the raw "
                  "string each backend emits; Local/UTC reformat the reset "
                  "timestamp with an explicit timezone.",
            xalign=0.0, wrap=True, max_width_chars=44)
        add_css_class(reset_hint, "codexbar-subtitle")
        append(self.body, reset_hint)
        append(self.body, self._build_reset_format_picker())

        # Divider between sections.
        append(self.body, self._divider())

        # --- Section: enabled providers ---
        section_title = Gtk.Label(label="Providers", xalign=0.0)
        add_css_class(section_title, "codexbar-section-title")
        append(self.body, section_title)
        section_hint = Gtk.Label(
            label="Toggle which providers feed the bar and the popup.",
            xalign=0.0, wrap=True)
        add_css_class(section_hint, "codexbar-subtitle")
        append(self.body, section_hint)

        # Scrollable list.
        scroller = Gtk.ScrolledWindow()
        scroller.set_min_content_height(280)
        scroller.set_propagate_natural_width(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        add_css_class(list_box, "codexbar-settings-list")
        scroller.add(list_box)
        append(self.body, scroller)

        # The Linux CLI's config dump is authoritative. If upstream exposes a
        # provider there, keep it selectable here.
        provider_ids = [p.get("id") for p in cfg.get("providers", [])]
        supported = sorted(p for p in provider_ids if isinstance(p, str))

        for pid in supported:
            append(list_box, self._settings_row(pid, existing.get(pid, False), enabled_ui=True))

        # Footer note.
        note = Gtk.Label(
            label=f"Config: {CONFIG_PATH}",
            xalign=0.0, wrap=True)
        add_css_class(note, "codexbar-subtitle")
        append(self.body, note)

    def _build_provider_picker(self, existing: dict[str, bool], current: str | None,
                               on_change) -> Gtk.Widget:
        wrap = Gtk.FlowBox()
        add_css_class(wrap, "codexbar-bar-picker")
        wrap.set_selection_mode(Gtk.SelectionMode.NONE)
        wrap.set_homogeneous(False)
        wrap.set_max_children_per_line(8)

        def make_chip(pid: str | None, label: str):
            classes = ["codexbar-tab"]
            if pid == current or (pid is None and not current):
                classes.append("active")
            return self._make_pill(
                label, classes,
                lambda p=pid: on_change(p),
                icon_pid=pid)

        append(wrap, make_chip(None, "Highest"))
        enabled_pids = [pid for pid, enabled in existing.items() if enabled]
        for pid in enabled_pids:
            append(wrap, make_chip(pid, provider_label(pid)))
        return wrap

    def _build_bar_provider_picker(self, existing: dict[str, bool]) -> Gtk.Widget:
        current = load_state().get("barProvider")
        return self._build_provider_picker(existing, current, self._on_bar_provider_change)

    def _build_popup_provider_picker(self, existing: dict[str, bool]) -> Gtk.Widget:
        enabled_pids = [pid for pid, enabled in existing.items() if enabled]
        current = load_state().get("popupProvider")
        if current not in enabled_pids:
            current = None
        return self._build_provider_picker(existing, current, self._on_popup_provider_change)

    def _on_bar_provider_change(self, pid: str | None):
        state = load_state()
        if pid is None:
            state.pop("barProvider", None)
        else:
            state["barProvider"] = pid
        save_state(state)
        # Re-render so the active chip highlight tracks the click.
        self.render()
        # Nudge waybar so the bar text updates immediately.
        # Native tray reads this preference on its next update.

    def _on_popup_provider_change(self, pid: str | None):
        state = load_state()
        if pid is None:
            state.pop("popupProvider", None)
        else:
            state["popupProvider"] = pid
        save_state(state)
        # Re-render so the active chip highlight tracks the click.
        self.render()

    def _build_reset_format_picker(self) -> Gtk.Widget:
        wrap = Gtk.FlowBox()
        add_css_class(wrap, "codexbar-bar-picker")
        wrap.set_selection_mode(Gtk.SelectionMode.NONE)
        wrap.set_homogeneous(False)
        wrap.set_max_children_per_line(8)
        current = current_reset_format()
        labels = (("provider", "Provider"), ("local", "Local"), ("utc", "UTC"))
        for value, label in labels:
            classes = ["codexbar-tab"]
            if value == current:
                classes.append("active")
            append(wrap, self._make_pill(
                label, classes,
                lambda v=value: self._on_reset_format_change(v)))
        return wrap

    def _on_reset_format_change(self, value: str):
        state = load_state()
        if value == "provider":
            state.pop("resetTimeFormat", None)
        else:
            state["resetTimeFormat"] = value
        save_state(state)
        # Re-render the Settings view so the chip highlight tracks the click,
        # and signal waybar so the tooltip picks up the new format on its
        # next refresh.
        self.render()
        # Native tray reads this preference on its next update.

    def _settings_row(self, pid: str, enabled: bool, *, enabled_ui: bool) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_css_class(row, "codexbar-settings-row")
        if not enabled_ui:
            add_css_class(row, "disabled")

        icon = make_icon(pid, size=18)
        if icon is not None:
            append(row, icon)

        name = Gtk.Label(label=provider_label(pid), xalign=0.0, hexpand=True)
        add_css_class(name, "codexbar-settings-name")
        append(row, name)

        if not enabled_ui:
            hint = Gtk.Label(label="macOS only", xalign=1.0)
            add_css_class(hint, "codexbar-settings-hint")
            append(row, hint)

        switch = Gtk.Switch()
        switch.set_active(enabled)
        switch.set_sensitive(enabled_ui)
        switch.set_valign(Gtk.Align.CENTER)
        append(row, switch)
        self.settings_switches[pid] = switch
        return row

    def _select(self, key: str):
        if key == self.active_pid:
            return
        self.active_pid = key
        self.render()

    def _render_provider(self, entry: dict):
        pid = entry.get("provider", "?")
        usage = entry.get("usage") or {}
        identity = usage.get("identity") or {}
        email = usage.get("accountEmail") or identity.get("accountEmail")
        login_method = identity.get("loginMethod") or usage.get("loginMethod")

        # Header row.
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=provider_label(pid), xalign=0.0, hexpand=True)
        add_css_class(title, "codexbar-provider-title")
        append(header, title)
        if email:
            account = Gtk.Label(label=email, xalign=1.0)
            account.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            account.set_max_width_chars(23)
            add_css_class(account, "codexbar-subtitle")
            append(header, account)
        append(self.body, header)

        # Subtitle line (status / updated / stale).
        sub_text = "Updated just now"
        if entry.get("stale"):
            sub_text = "Cached — last refresh failed"
        elif entry.get("error"):
            sub_text = "Refresh failed"
        else:
            status_text = summarize_status(entry)
            if status_text:
                sub_text = status_text
        sub_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sub = Gtk.Label(label=sub_text, xalign=0.0, hexpand=True)
        add_css_class(sub, "codexbar-subtitle")
        append(sub_row, sub)
        if login_method:
            email_label = Gtk.Label(label=str(login_method).title(), xalign=1.0)
            add_css_class(email_label, "codexbar-subtitle")
            append(sub_row, email_label)
        append(self.body, sub_row)

        if entry.get("error"):
            append(self.body, self._divider())
            err = Gtk.Label(
                label=entry["error"].get("message", "Unknown error"),
                xalign=0.0,
                wrap=True,
                max_width_chars=44)
            add_css_class(err, "codexbar-error")
            append(self.body, err)
            return

        append(self.body, self._divider())

        # Usage windows.
        rendered_any = False
        for key in ("primary", "secondary", "tertiary"):
            window = usage.get(key)
            if not window:
                continue
            append(self.body, self._section(WINDOW_LABELS.get(key, key.title()), window))
            rendered_any = True

        for item in usage.get("extraRateWindows") or []:
            if not isinstance(item, dict):
                continue
            window = item.get("window")
            if not isinstance(window, dict):
                continue
            title = item.get("title") or item.get("id") or "Extra quota"
            append(self.body, self._section(str(title), window, usage_known=item.get("usageKnown", True)))
            rendered_any = True

        # Credits (when provider exposes it).
        credits = entry.get("credits") or {}
        remaining = credits.get("remaining")
        credit_lines = []
        if isinstance(remaining, (int, float)):
            credit_lines.append((money(float(remaining)), "remaining"))
        limit_line = summarize_credit_limit(credits.get("codexCreditLimit"))
        if limit_line:
            credit_lines.append((limit_line, ""))
        if credit_lines:
            append(self.body, self._divider())
            credit_title = Gtk.Label(label="Credits", xalign=0.0)
            add_css_class(credit_title, "codexbar-section-title")
            append(self.body, credit_title)
            for value, label in credit_lines:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                val = Gtk.Label(label=value, xalign=0.0, hexpand=True)
                add_css_class(val, "codexbar-credits")
                append(row, val)
                if label:
                    lbl = Gtk.Label(label=label, xalign=1.0)
                    add_css_class(lbl, "codexbar-credits-label")
                    append(row, lbl)
                append(self.body, row)
            rendered_any = True

        detail_lines = [
            *summarize_pace(entry),
            *summarize_openai_dashboard(entry),
            *summarize_usage_details(usage),
        ]
        plan_info = entry.get("antigravityPlanInfo")
        if isinstance(plan_info, dict):
            plan = (
                plan_info.get("planDisplayName")
                or plan_info.get("displayName")
                or plan_info.get("planShortName")
                or plan_info.get("planName")
            )
            if plan:
                detail_lines.append(f"Plan: {plan}")
        if detail_lines:
            append(self.body, self._divider())
            expander = Gtk.Expander(label="Usage details")
            detail_key = entry_key(entry)
            expander.set_expanded(detail_key in self.expanded_details)
            expander.connect("notify::expanded", self._details_changed, detail_key)
            add_css_class(expander, "codexbar-details")
            detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            add_css_class(detail_box, "codexbar-details-box")
            for line in detail_lines:
                detail = Gtk.Label(label=line, xalign=0.0, wrap=True, max_width_chars=40)
                add_css_class(detail, "codexbar-subtitle")
                append(detail_box, detail)
            expander.add(detail_box)
            append(self.body, expander)
            rendered_any = True

        if not rendered_any:
            append(self.body, self._divider())
            empty = Gtk.Label(label="No usage data for this provider.", xalign=0.0)
            add_css_class(empty, "codexbar-subtitle")
            append(self.body, empty)

    def _details_changed(self, expander, _property, key):
        if expander.get_expanded():
            self.expanded_details.add(key)
        else:
            self.expanded_details.discard(key)

    def _divider(self) -> Gtk.Widget:
        d = Gtk.Box()
        add_css_class(d, "codexbar-divider")
        return d

    def _section(self, title: str, window: dict, *, usage_known: bool = True) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        add_css_class(box, "codexbar-metric")
        t = Gtk.Label(label=title, xalign=0.0)
        add_css_class(t, "codexbar-section-title")
        append(box, t)

        pct = window.get("usedPercent")
        bar = Gtk.LevelBar()
        add_css_class(bar, "codex-usage")
        active = next((e for e in self.data if entry_key(e) == self.active_pid), {})
        if active.get("provider") == "codex":
            add_css_class(bar, "provider-codex")
        bar.set_min_value(0)
        bar.set_max_value(100)
        remaining = remaining_percent(pct) if usage_known else None
        bar.set_value(remaining if remaining is not None else 0)
        if remaining is None:
            bar.set_no_show_all(True)
            bar.hide()
        bar.set_tooltip_text(f"{remaining:g}% remaining" if remaining is not None else "Usage unavailable")
        if isinstance(pct, (int, float)):
            if pct >= 90:
                add_css_class(bar, "critical")
            elif pct >= 70:
                add_css_class(bar, "warning")
        append(box, bar)

        details = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if not usage_known:
            left_text = "Reset tracked"
        elif isinstance(pct, (int, float)):
            regen = window.get("nextRegenPercent")
            left_text = f"{remaining:g}% remaining" if remaining is not None else "—"
            if isinstance(regen, (int, float)) and regen > 0:
                left_text += f" · +{compact_number(regen)}% next regen"
        else:
            left_text = "—"
        left = Gtk.Label(label=left_text, xalign=0.0, hexpand=True)
        add_css_class(left, "codexbar-section-detail-left")
        append(details, left)

        reset_text = format_reset_label(window, current_reset_format())
        if reset_text:
            r = Gtk.Label(label=reset_text, xalign=1.0)
            add_css_class(r, "codexbar-section-detail-right")
            append(details, r)
        append(box, details)
        return box

    def _clear(self, container):
        for child in container.get_children():
            child.destroy()


def main():
    app = CodexBarPopup()
    if "--background" in sys.argv:
        app.set_flags(Gio.ApplicationFlags.IS_SERVICE)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
