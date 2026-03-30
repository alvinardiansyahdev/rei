import asyncio
import logging
import time

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
_last_update_id: int  = 0
_day_start_balance: float = 0.0

# Set of trade IDs yang sudah pernah dinotifkan
# Key: tranId dari income entry
_seen_trade_ids: set[str] = set()

# Timestamp terakhir kita cek income (untuk query incremental)
_last_income_check_ts: int = 0


# ─────────────────────────────────────────────
# Monitor trade via income history
# ─────────────────────────────────────────────

async def check_new_trades(session: aiohttp.ClientSession):
    """
    Poll income history sejak _last_income_check_ts.
    Setiap entry REALIZED_PNL baru = ada trade yang selesai → kirim notif.
    """
    global _seen_trade_ids, _last_income_check_ts

    try:
        # Query sejak 1 menit sebelum last check sebagai buffer
        since = max(0, _last_income_check_ts - 60_000)
        entries = await bc.get_recent_income(session, since_ts=since)
    except Exception as e:
        log.error(f"Gagal fetch income: {e}")
        return

    now_ts = int(time.time() * 1000)

    for entry in entries:
        tran_id = str(entry.get("tranId", ""))
        if not tran_id or tran_id in _seen_trade_ids:
            continue

        # Entry baru yang belum pernah dinotif
        _seen_trade_ids.add(tran_id)
        pnl = float(entry.get("income", 0))
        symbol = entry.get("symbol", "?")
        log.info(f"Trade baru terdeteksi: {symbol} PnL={pnl:.4f} USDT (tranId={tran_id})")
        await tg.send_message(session, tg.fmt_trade_closed(entry))

    _last_income_check_ts = now_ts


# ─────────────────────────────────────────────
# Daily summary
# ─────────────────────────────────────────────

async def send_daily_summary(session: aiohttp.ClientSession):
    global _day_start_balance

    try:
        ct_balance   = await bc.get_copy_trading_balance(session)
        today_income = await bc.get_today_income(session)
    except Exception as e:
        log.error(f"Error daily summary: {e}")
        return

    await tg.send_message(session, tg.fmt_daily_summary(
        ct_balance=ct_balance,
        day_start_balance=_day_start_balance,
        today_income=today_income,
    ))
    log.info("Daily summary terkirim.")

    # Reset baseline untuk hari berikutnya
    _day_start_balance = ct_balance


# ─────────────────────────────────────────────
# Command handler
# ─────────────────────────────────────────────

async def handle_command(session: aiohttp.ClientSession, command: str):
    log.info(f"Command diterima: {command}")

    if command == "/status":
        try:
            ct_balance   = await bc.get_copy_trading_balance(session)
            today_income = await bc.get_today_income(session)
            await tg.send_message(session, tg.fmt_status(today_income, ct_balance))
        except Exception as e:
            await tg.send_message(session, f"❌ Gagal ambil status: {e}")

    elif command == "/balance":
        try:
            ct_balance   = await bc.get_copy_trading_balance(session)
            today_income = await bc.get_today_income(session)
            await tg.send_message(session, tg.fmt_balance(ct_balance, today_income))
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
    global _day_start_balance, _last_income_check_ts, _seen_trade_ids

    log.info("Rei aktif — monitoring copy trading futures...")
    async with aiohttp.ClientSession() as session:

        # Balance awal sebagai baseline harian
        try:
            _day_start_balance = await bc.get_copy_trading_balance(session)
            log.info(f"Balance awal: {_day_start_balance:.2f} USDT")
        except Exception as e:
            log.error(f"Gagal ambil balance awal: {e}")

        # Snapshot income yang sudah ada SEBELUM Rei start
        # → cegah notif spam untuk trade yang sudah lama
        try:
            existing = await bc.get_today_income(session)
            _seen_trade_ids = {str(e.get("tranId", "")) for e in existing}
            _last_income_check_ts = int(time.time() * 1000)
            log.info(f"Snapshot income awal: {len(_seen_trade_ids)} trade sudah ada hari ini.")
        except Exception as e:
            log.error(f"Gagal snapshot income awal: {e}")
            _last_income_check_ts = int(time.time() * 1000)

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

        # Loop utama
        monitor_counter = 0
        while True:
            await poll_telegram_commands(session)

            monitor_counter += 1
            if monitor_counter >= POLL_INTERVAL_SECONDS:
                await check_new_trades(session)
                monitor_counter = 0

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
