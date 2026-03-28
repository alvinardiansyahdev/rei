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

def fmt_position_opened(pos: dict) -> str:
    symbol   = pos.get("symbol", "?")
    side     = pos.get("positionSide", "?")
    size     = pos.get("positionAmt", "?")
    entry    = float(pos.get("entryPrice", 0))
    liq      = float(pos.get("liquidationPrice", 0))
    leverage = pos.get("leverage", "?")
    side_emoji = "🟢" if str(side).upper() == "LONG" else "🔴" if str(side).upper() == "SHORT" else "🟡"
    return (
        f"{side_emoji} <b>POSISI BARU DIBUKA</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Symbol     : <b>{symbol}</b>\n"
        f"📊 Side       : <b>{side}</b>\n"
        f"📦 Size       : {size}\n"
        f"💰 Entry      : {entry:,.4f} USDT\n"
        f"⚡ Leverage   : {leverage}x\n"
        f"💀 Liquidasi  : {liq:,.4f} USDT"
    )


def fmt_position_closed(pos: dict, pnl: float) -> str:
    symbol = pos.get("symbol", "?")
    side   = pos.get("positionSide", "?")
    pnl_emoji = "✅" if pnl >= 0 else "❌"
    pnl_sign  = "+" if pnl >= 0 else ""
    return (
        f"{pnl_emoji} <b>POSISI DITUTUP</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Symbol     : <b>{symbol}</b>\n"
        f"📊 Side       : <b>{side}</b>\n"
        f"💵 Est. PnL   : <b>{pnl_sign}{pnl:.2f} USDT</b>"
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

def fmt_balance(ct_balance: float, positions: list) -> str:
    # Hitung total unrealized PnL dari posisi aktif
    total_unrealized = sum(float(p.get("unRealizedProfit", 0)) for p in positions)
    equity = ct_balance + total_unrealized
    pnl_sign  = "+" if total_unrealized >= 0 else ""
    pnl_emoji = "📈" if total_unrealized >= 0 else "📉"

    pos_info = f"{len(positions)} posisi aktif" if positions else "Tidak ada posisi aktif"

    return (
        f"💼 <b>SALDO COPY TRADING</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗂 CT Balance    : <b>{ct_balance:.2f} USDT</b>\n"
        f"🏦 Equity        : {equity:.2f} USDT\n"
        f"{pnl_emoji} Unrealized PnL : <b>{pnl_sign}{total_unrealized:.2f} USDT</b>\n"
        f"📊 Posisi        : {pos_info}"
    )


# ─────────────────────────────────────────────
# Command: /report & daily summary
# ─────────────────────────────────────────────

def fmt_daily_summary(ct_balance: float, day_start_balance: float,
                      positions_opened: int, positions_closed: int,
                      win: int, loss: int) -> str:
    # PnL hari ini = selisih balance sekarang vs awal hari
    today_pnl = ct_balance - day_start_balance
    pnl_emoji = "📈" if today_pnl >= 0 else "📉"
    pnl_sign  = "+" if today_pnl >= 0 else ""
    winrate   = (win / (win + loss) * 100) if (win + loss) > 0 else 0

    return (
        f"🌙 <b>REI — DAILY SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} PnL Hari Ini   : <b>{pnl_sign}{today_pnl:.2f} USDT</b>\n"
        f"💼 Balance Skrg  : <b>{ct_balance:.2f} USDT</b>\n"
        f"📂 Dibuka        : {positions_opened} posisi\n"
        f"📁 Ditutup       : {positions_closed} posisi\n"
        f"✅ Win / ❌ Loss  : {win} / {loss}\n"
        f"🎯 Win Rate      : {winrate:.1f}%"
    )


# ─────────────────────────────────────────────
# Command: /status
# ─────────────────────────────────────────────

def fmt_status(positions: list) -> str:
    if not positions:
        return "📭 <b>Tidak ada posisi aktif saat ini.</b>"

    lines = [f"📊 <b>POSISI AKTIF</b> ({len(positions)} posisi)\n━━━━━━━━━━━━━━━━━━"]
    for pos in positions:
        symbol   = pos.get("symbol", "?")
        side     = pos.get("positionSide", "?")
        size     = pos.get("positionAmt", "?")
        entry    = float(pos.get("entryPrice", 0))
        unreal   = float(pos.get("unRealizedProfit", 0))
        liq      = float(pos.get("liquidationPrice", 0))
        leverage = pos.get("leverage", "?")
        pnl_sign  = "+" if unreal >= 0 else ""
        pnl_emoji = "🟢" if unreal >= 0 else "🔴"
        side_emoji = "📈" if str(side).upper() == "LONG" else "📉"

        lines.append(
            f"\n{side_emoji} <b>{symbol}</b> [{side}]\n"
            f"  📦 Size      : {size}\n"
            f"  💰 Entry     : {entry:,.4f}\n"
            f"  ⚡ Leverage  : {leverage}x\n"
            f"  {pnl_emoji} Unreal PnL : <b>{pnl_sign}{unreal:.2f} USDT</b>\n"
            f"  💀 Liquidasi : {liq:,.4f}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Command: /help
# ─────────────────────────────────────────────

def fmt_help() -> str:
    return (
        f"🤖 <b>REI — Command List</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 /status   — Posisi copy trade aktif\n"
        f"💼 /balance  — Saldo copy trading wallet\n"
        f"📋 /report   — Daily report sekarang\n"
        f"❓ /help     — Tampilkan pesan ini"
    )
