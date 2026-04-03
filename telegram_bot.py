import aiohttp
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(session: aiohttp.ClientSession, text: str, parse_mode: str = "HTML"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode}
    async with session.post(url, json=payload) as resp:
        return await resp.json()


# ─────────────────────────────────────────────
# Notifikasi otomatis: balance berubah = ada trade
# ─────────────────────────────────────────────

def fmt_balance_change(diff: float, balance_before: float,
                       balance_after: float, daily_pnl: float) -> str:
    emoji     = "✅" if diff >= 0 else "❌"
    result    = "PROFIT" if diff >= 0 else "LOSS"
    diff_sign = "+" if diff >= 0 else ""
    pnl_sign  = "+" if daily_pnl >= 0 else ""
    pnl_emoji = "📈" if daily_pnl >= 0 else "📉"

    return (
        f"{emoji} <b>TRADE TERDETEKSI — {result}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 PnL Trade     : <b>{diff_sign}{diff:.4f} USDT</b>\n"
        f"💼 Balance       : {balance_before:.4f} → <b>{balance_after:.4f} USDT</b>\n"
        f"{pnl_emoji} PnL Hari Ini  : <b>{pnl_sign}{daily_pnl:.4f} USDT</b>"
    )


# ─────────────────────────────────────────────
# Command: /balance
# ─────────────────────────────────────────────

def fmt_balance(ct_balance: float, day_start_balance: float, daily_pnl: float) -> str:
    pnl_sign  = "+" if daily_pnl >= 0 else ""
    pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
    return (
        f"💼 <b>SALDO COPY TRADING</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗂 CT Balance     : <b>{ct_balance:.4f} USDT</b>\n"
        f"📅 Awal Hari      : {day_start_balance:.4f} USDT\n"
        f"{pnl_emoji} PnL Hari Ini  : <b>{pnl_sign}{daily_pnl:.4f} USDT</b>"
    )


# ─────────────────────────────────────────────
# Command: /status
# ─────────────────────────────────────────────

def fmt_status(ct_balance: float, day_start_balance: float,
               trade_count: int, win: int, loss: int, daily_pnl: float) -> str:
    pnl_sign  = "+" if daily_pnl >= 0 else ""
    pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
    winrate   = (win / trade_count * 100) if trade_count > 0 else 0
    return (
        f"📊 <b>STATUS HARI INI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💼 Balance        : <b>{ct_balance:.4f} USDT</b>\n"
        f"📅 Awal Hari      : {day_start_balance:.4f} USDT\n"
        f"{pnl_emoji} PnL Hari Ini  : <b>{pnl_sign}{daily_pnl:.4f} USDT</b>\n"
        f"📋 Total Trade    : {trade_count}\n"
        f"✅ Win / ❌ Loss  : {win} / {loss}\n"
        f"🎯 Win Rate      : {winrate:.1f}%"
    )


# ─────────────────────────────────────────────
# Command: /report & daily summary
# ─────────────────────────────────────────────

def fmt_daily_summary(ct_balance: float, day_start_balance: float,
                      trade_count: int, win: int, loss: int) -> str:
    today_pnl = ct_balance - day_start_balance
    winrate   = (win / trade_count * 100) if trade_count > 0 else 0
    pnl_sign  = "+" if today_pnl >= 0 else ""
    pnl_emoji = "📈" if today_pnl >= 0 else "📉"
    return (
        f"🌙 <b>REI — DAILY SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} PnL Hari Ini   : <b>{pnl_sign}{today_pnl:.4f} USDT</b>\n"
        f"💼 Balance Skrg  : <b>{ct_balance:.4f} USDT</b>\n"
        f"📋 Total Trade   : {trade_count}\n"
        f"✅ Win / ❌ Loss  : {win} / {loss}\n"
        f"🎯 Win Rate      : {winrate:.1f}%"
    )


# ─────────────────────────────────────────────
# Command: /help
# ─────────────────────────────────────────────

def fmt_help() -> str:
    return (
        f"🤖 <b>REI — Command List</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 /status   — Status & PnL hari ini\n"
        f"💼 /balance  — Saldo copy trading wallet\n"
        f"📋 /report   — Daily report sekarang\n"
        f"❓ /help     — Tampilkan pesan ini"
    )
