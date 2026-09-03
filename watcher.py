#!/usr/bin/env python3
"""
SURGE whale-alert watcher
=========================
Polls the wallets in watchlist.json for NEW large fills on Hyperliquid and
sends a Telegram push for each one. Runs on a schedule (GitHub Actions cron,
every 5 min) — see .github/workflows/alerts.yml.

Key behaviours (tested against the live Hyperliquid API):
  • First time it sees a wallet, it seeds silently (records the latest fill time,
    sends nothing) so you don't get flooded with a backlog.
  • On later runs it only alerts on fills newer than last time, and only those
    at/above that wallet's min_usd threshold.
  • It never alerts on the same fill twice (state.json remembers the last fill time).
  • A per-run cap stops a burst from spamming your phone.

Secrets (set as GitHub Actions repository secrets, NOT committed):
  TELEGRAM_BOT_TOKEN   – from @BotFather
  TELEGRAM_CHAT_ID     – your chat id, or a group chat id (see ALERTS_SETUP.md)
"""

import os
import json
import datetime as dt
import requests

HL_INFO = "https://api.hyperliquid.xyz/info"
STATE_FILE = "state.json"
WATCHLIST_FILE = "watchlist.json"
MAX_ALERTS_PER_WALLET = 8          # safety cap so one run can't spam you

BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def short(a):
    return a[:6] + "…" + a[-4:] if len(a) >= 10 else a


def send(text):
    """Send one Telegram message. If creds are missing, print instead (dry-run)."""
    if not (BOT and CHAT):
        print("[dry-run — no Telegram creds] " + text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT}/sendMessage",
            json={"chat_id": CHAT, "text": text, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=15,
        )
    except Exception as e:
        print("Telegram send error:", e)


def get_fills(addr):
    try:
        r = requests.post(HL_INFO, json={"type": "userFills", "user": addr}, timeout=15)
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception as e:
        print("fills error", addr, e)
        return []


def run():
    watchlist = load(WATCHLIST_FILE, [])
    state = load(STATE_FILE, {})
    changed = False

    if not watchlist:
        print("watchlist.json is empty — add wallets to start getting alerts.")
        return

    for entry in watchlist:
        addr = str(entry.get("wallet", "")).lower().strip()
        if not (addr.startswith("0x") and len(addr) == 42):
            print("skipping invalid wallet:", entry.get("wallet"))
            continue
        threshold = float(entry.get("min_usd", 250000))
        label = entry.get("label") or short(addr)

        fills = get_fills(addr)
        if not fills:
            continue
        latest_ts = max(int(f.get("time", 0)) for f in fills)
        last_seen = state.get(addr, {}).get("last_ts")

        if last_seen is None:                       # first sight → seed silently
            state[addr] = {"last_ts": latest_ts}
            changed = True
            print(f"seeded {label} (no alerts on first add)")
            continue

        # new, large fills since last run
        new = [f for f in fills if int(f.get("time", 0)) > last_seen]
        big = []
        for f in new:
            try:
                notional = abs(float(f.get("sz", 0)) * float(f.get("px", 0)))
            except Exception:
                continue
            if notional >= threshold:
                big.append((int(f.get("time", 0)), notional, f))
        big.sort()                                   # oldest → newest reads naturally

        for ts, notional, f in big[-MAX_ALERTS_PER_WALLET:]:
            direction = f.get("dir") or ("Buy" if f.get("side") == "B" else "Sell")
            coin = f.get("coin", "?")
            px = float(f.get("px", 0))
            when = dt.datetime.utcfromtimestamp(ts / 1000).strftime("%H:%M UTC")
            send(f"🐋 *{label}*  {direction} *{coin}*\n"
                 f"${notional:,.0f} @ {px:g}  ·  {when}")

        if new:
            state[addr] = {"last_ts": latest_ts}
            changed = True
            if big:
                print(f"{label}: sent {len(big[-MAX_ALERTS_PER_WALLET:])} alert(s)")

    if changed:
        save(STATE_FILE, state)


if __name__ == "__main__":
    run()
