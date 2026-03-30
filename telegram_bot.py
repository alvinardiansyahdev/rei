import aiohttp
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ─────────────────────────────────────────────
# Kirim pesan
# ─────────────────────────────────────────────

async def send_message(session: aiohttp.ClientSession, text: str, parse_mode: str = "HTML"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode}
    async with session.post(url, json=payload) as resp:
        return await resp.json()


# ─────────────────────────────────────────────
# Notifikasi otomatis
# ─────────────────────────────────────────────

def fmt_trade_closed(income: dict) -> str:
    """Notifikasi dari income history — trade selesai."""
    symbol   = income.get("symbol", "?")
    pnl      = float(income.get("income", 0))
    trade_id = income.get("tradeId", "-")
    ts       = income.get("time", 0)
    pnl_emoji = "✅" if pnl >= 0 else "❌"
    pnl_sign  = "+" if pnl >= 0 else ""

    # Format timestamp ke jam:menit
    import datetime
    dt = datetime.datetime.utcfromtimestamp(ts / 1000).strftime("%H:%M UTC")

    return (
        f"{pnl_emoji} <b>TRADE SELESAI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Symbol     : <b>{symbol}</b>\n"
        f"💵 Realized PnL : <b>{pnl_sign}{pnl:.4f} USDT</b>\n"
        f"🕐 Waktu      : {dt}\n"
        f"🔖 Trade ID   : {trade_id}"
    )


def fmt_drawdown_alert(symbol: str, drawdown_pct: float) -> str:
    return (
        f"⚠️ <b>DRAWDOWN ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Symbol     : <b>{symbol}</b>\n"
        f"📉 Drawdown   : <b>-{drawdown_pct:.2f}%</b>\n"
        f"Perhatikan posisi ini!"
    )


# ─────────────────────────────────────────────
# Command: /balance
# ─────────────────────────────────────────────

def fmt_balance(ct_balance: float, today_income: list) -> str:
    total_unrealized = 0.0  # tidak bisa lihat posisi aktif copy trading
    today_pnl = sum(float(i.get("income", 0)) for i in today_income)
    trade_count = len(today_income)
    win  = sum(1 for i in today_income if float(i.get("income", 0)) >= 0)
    loss = trade_count - win
    pnl_sign  = "+" if today_pnl >= 0 else ""
    pnl_emoji = "📈" if today_pnl >= 0 else "📉"

    return (
        f"💼 <b>SALDO COPY TRADING</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗂 CT Balance     : <b>{ct_balance:.2f} USDT</b>\n"
        f"{pnl_emoji} PnL Hari Ini  : <b>{pnl_sign}{today_pnl:.4f} USDT</b>\n"
        f"📊 Trade Hari Ini : {trade_count} trade\n"
        f"✅ Win / ❌ Loss  : {win} / {loss}"
    )


# ─────────────────────────────────────────────
# Command: /status
# ─────────────────────────────────────────────

def fmt_status(today_income: list, ct_balance: float) -> str:
    if not today_income:
        return (
            f"📭 <b>Belum ada trade hari ini.</b>\n"
            f"💼 Balance : {ct_balance:.2f} USDT"
        )

    today_pnl = sum(float(i.get("income", 0)) for i in today_income)
    win  = sum(1 for i in today_income if float(i.get("income", 0)) >= 0)
    loss = len(today_income) - win
    pnl_sign  = "+" if today_pnl >= 0 else ""
    pnl_emoji = "📈" if today_pnl >= 0 else "📉"

    lines = [
        f"📊 <b>STATUS HARI INI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💼 Balance        : <b>{ct_balance:.2f} USDT</b>\n"
        f"{pnl_emoji} Total PnL     : <b>{pnl_sign}{today_pnl:.4f} USDT</b>\n"
        f"📋 Total Trade    : {len(today_income)}\n"
        f"✅ Win / ❌ Loss  : {win} / {loss}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>History Trade:</b>"
    ]

    # Tampilkan max 10 trade terakhir
    for i in today_income[-10:]:
        symbol = i.get("symbol", "?")
        pnl    = float(i.get("income", 0))
        import datetime
        dt     = datetime.datetime.utcfromtimestamp(i.get("time", 0) / 1000).strftime("%H:%M")
        emoji  = "✅" if pnl >= 0 else "❌"
        sign   = "+" if pnl >= 0 else ""
        lines.append(f"{emoji} {symbol} {sign}{pnl:.4f} USDT ({dt})")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Command: /report & daily summary
# ─────────────────────────────────────────────

def fmt_daily_summary(ct_balance: float, day_start_balance: float,
                      today_income: list) -> str:
    today_pnl = sum(float(i.get("income", 0)) for i in today_income)
    trade_count = len(today_income)
    win  = sum(1 for i in today_income if float(i.get("income", 0)) >= 0)
    loss = trade_count - win
    winrate   = (win / trade_count * 100) if trade_count > 0 else 0
    pnl_emoji = "📈" if today_pnl >= 0 else "📉"
    pnl_sign  = "+" if today_pnl >= 0 else ""

    return (
        f"🌙 <b>REI — DAILY SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} PnL Hari Ini   : <b>{pnl_sign}{today_pnl:.4f} USDT</b>\n"
        f"💼 Balance Skrg  : <b>{ct_balance:.2f} USDT</b>\n"
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
        f"📊 /status   — Trade & PnL hari ini\n"
        f"💼 /balance  — Saldo copy trading wallet\n"
        f"📋 /report   — Daily report sekarang\n"
        f"❓ /help     — Tampilkan pesan ini"
    )
