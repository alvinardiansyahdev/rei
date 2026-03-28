import asyncio
import logging

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import binance_client as bc
import telegram_bot as tg
from config import (
    DRAWDOWN_ALERT_PERCENT,
    DAILY_SUMMARY_HOUR,
    DAILY_SUMMARY_MINUTE,
    POLL_INTERVAL_SECONDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("rei")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ─────────────────────────────────────────────
# State in-memory
# ─────────────────────────────────────────────
_known_positions: dict[str, dict] = {}
_daily_stats     = {"opened": 0, "closed": 0, "win": 0, "loss": 0}
_drawdown_alerted: set[str] = set()
_last_update_id: int = 0

# Tracking balance harian untuk hitung PnL
_day_start_balance: float = 0.0


def _pos_key(pos: dict) -> str:
    return f"{pos['symbol']}_{pos.get('positionSide', 'BOTH')}"


# ─────────────────────────────────────────────
# Monitor posisi
# ─────────────────────────────────────────────

async def check_positions(session: aiohttp.ClientSession):
    global _known_positions
    try:
        positions = await bc.get_positions(session)
    except Exception as e:
        log.error(f"Gagal fetch posisi: {e}")
        return

    current = {_pos_key(p): p for p in positions}

    # Posisi baru dibuka
    for key, pos in current.items():
        if key not in _known_positions:
            log.info(f"Posisi baru dibuka: {key}")
            _daily_stats["opened"] += 1
            await tg.send_message(session, tg.fmt_position_opened(pos))

    # Posisi ditutup
    for key, pos in list(_known_positions.items()):
        if key not in current:
            log.info(f"Posisi ditutup: {key}")
            realized = float(pos.get("unRealizedProfit", 0))
            _daily_stats["closed"] += 1
            if realized >= 0:
                _daily_stats["win"] += 1
            else:
                _daily_stats["loss"] += 1
            await tg.send_message(session, tg.fmt_position_closed(pos, realized))
            _drawdown_alerted.discard(key)

    # Cek drawdown
    for key, pos in current.items():
        try:
            unrealized     = float(pos.get("unRealizedProfit", 0))
            initial_margin = float(pos.get("initialMargin", 0)) or float(pos.get("isolatedMargin", 0))
            if initial_margin > 0 and unrealized < 0:
                drawdown_pct = abs(unrealized / initial_margin * 100)
                if drawdown_pct >= DRAWDOWN_ALERT_PERCENT and key not in _drawdown_alerted:
                    await tg.send_message(session, tg.fmt_drawdown_alert(pos["symbol"], drawdown_pct))
                    _drawdown_alerted.add(key)
                elif drawdown_pct < DRAWDOWN_ALERT_PERCENT:
                    _drawdown_alerted.discard(key)
        except (ValueError, ZeroDivisionError):
            pass

    _known_positions = current


# ─────────────────────────────────────────────
# Daily summary
# ─────────────────────────────────────────────

async def send_daily_summary(session: aiohttp.ClientSession):
    global _day_start_balance

    try:
        ct_balance = await bc.get_copy_trading_balance(session)
    except Exception as e:
        log.error(f"Error ambil balance untuk daily summary: {e}")
        ct_balance = 0.0

    await tg.send_message(session, tg.fmt_daily_summary(
        ct_balance=ct_balance,
        day_start_balance=_day_start_balance,
        positions_opened=_daily_stats["opened"],
        positions_closed=_daily_stats["closed"],
        win=_daily_stats["win"],
        loss=_daily_stats["loss"],
    ))
    log.info(f"Daily summary terkirim. PnL hari ini: {ct_balance - _day_start_balance:.2f} USDT")

    # Reset untuk hari berikutnya
    _day_start_balance = ct_balance
    for key in _daily_stats:
        _daily_stats[key] = 0


# ─────────────────────────────────────────────
# Command handler
# ─────────────────────────────────────────────

async def handle_command(session: aiohttp.ClientSession, command: str):
    log.info(f"Command diterima: {command}")

    if command == "/status":
        try:
            positions = await bc.get_positions(session)
            await tg.send_message(session, tg.fmt_status(positions))
        except Exception as e:
            await tg.send_message(session, f"❌ Gagal ambil posisi: {e}")

    elif command == "/balance":
        try:
            ct_balance = await bc.get_copy_trading_balance(session)
            positions  = await bc.get_positions(session)
            await tg.send_message(session, tg.fmt_balance(ct_balance, positions))
        except Exception as e:
            await tg.send_message(session, f"❌ Gagal ambil balance: {e}")

    elif command == "/report":
        await send_daily_summary(session)

    elif command == "/help":
        await tg.send_message(session, tg.fmt_help())

    else:
        await tg.send_message(
            session,
            f"❓ Command <b>{command}</b> tidak dikenal.\nKetik /help untuk daftar command."
        )


# ─────────────────────────────────────────────
# Telegram long-polling
# ─────────────────────────────────────────────

async def poll_telegram_commands(session: aiohttp.ClientSession):
    global _last_update_id
    try:
        params = {"timeout": 10, "offset": _last_update_id + 1}
        async with session.get(f"{TELEGRAM_API}/getUpdates", params=params) as resp:
            data = await resp.json()

        if not data.get("ok"):
            return

        for update in data.get("result", []):
            _last_update_id = update["update_id"]
            message = update.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", ""))
            text    = message.get("text", "").strip()

            if chat_id != str(TELEGRAM_CHAT_ID):
                log.warning(f"Pesan dari chat_id tidak dikenal: {chat_id}")
                continue

            if text.startswith("/"):
                command = text.split("@")[0].lower()
                await handle_command(session, command)

    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error(f"Error polling Telegram: {e}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

async def main():
    global _day_start_balance

    log.info("Rei aktif — monitoring copy trading futures...")
    async with aiohttp.ClientSession() as session:

        # Ambil balance awal sebagai baseline harian
        try:
            _day_start_balance = await bc.get_copy_trading_balance(session)
            log.info(f"Balance awal hari: {_day_start_balance:.2f} USDT")
        except Exception as e:
            log.error(f"Gagal ambil balance awal: {e}")

        await tg.send_message(
            session,
            "✨ <b>Rei aktif!</b>\n"
            "Monitoring copy trading futures dimulai.\n"
            f"💼 Balance saat ini : <b>{_day_start_balance:.2f} USDT</b>\n"
            f"🔄 Polling setiap <b>{POLL_INTERVAL_SECONDS} detik</b>\n"
            f"📊 Daily summary jam <b>{DAILY_SUMMARY_HOUR:02d}:{DAILY_SUMMARY_MINUTE:02d} UTC</b>\n"
            f"💬 Ketik /help untuk daftar command"
        )

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            send_daily_summary,
            "cron",
            hour=DAILY_SUMMARY_HOUR,
            minute=DAILY_SUMMARY_MINUTE,
            args=[session],
        )
        scheduler.start()

        # Snapshot posisi awal (tanpa notifikasi)
        try:
            initial = await bc.get_positions(session)
            _known_positions.update({_pos_key(p): p for p in initial})
            log.info(f"Snapshot awal: {len(initial)} posisi aktif.")
        except Exception as e:
            log.error(f"Gagal snapshot awal: {e}")

        # Loop utama
        monitor_counter = 0
        while True:
            await poll_telegram_commands(session)

            monitor_counter += 1
            if monitor_counter >= POLL_INTERVAL_SECONDS:
                await check_positions(session)
                monitor_counter = 0

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
