import asyncio
import logging
import time
import datetime

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

TELEGRAM_API        = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MIN_CHANGE_USDT     = 0.001   # perubahan balance minimum untuk dianggap signifikan
BALANCE_POLL_SECS   = 15      # cek balance setiap N detik
DEBOUNCE_SECS       = 30      # tunggu N detik sebelum konfirmasi perubahan

# ─────────────────────────────────────────────
# State in-memory
# ─────────────────────────────────────────────
_last_update_id:      int   = 0
_last_balance:        float = 0.0    # balance terakhir yang diketahui
_day_start_balance:   float = 0.0    # balance awal hari
_daily_pnl:           float = 0.0
_daily_trade_count:   int   = 0
_daily_win:           int   = 0
_daily_loss:          int   = 0

# Debounce: simpan kandidat perubahan sebelum dikonfirmasi
_pending_balance:     float = 0.0   # nilai balance yang "mencurigakan"
_pending_since:       float = 0.0   # timestamp saat pertama kali berubah
_notified_balance:    float = 0.0   # balance terakhir yang sudah dinotif


# ─────────────────────────────────────────────
# Monitor via balance polling + debounce
# ─────────────────────────────────────────────

async def check_balance_change(session: aiohttp.ClientSession):
    """
    Poll balance setiap BALANCE_POLL_SECS detik.
    Pakai debounce: kalau balance berubah dan TETAP berubah selama
    DEBOUNCE_SECS detik → baru dianggap trade closed → kirim notif.

    Ini mencegah spam dari unrealized PnL yang terus bergerak.
    Unrealized PnL = balance naik-turun terus (tidak stabil).
    Realized PnL   = balance berubah lalu STABIL di nilai baru.
    """
    global _last_balance, _pending_balance, _pending_since
    global _notified_balance, _daily_pnl, _daily_trade_count, _daily_win, _daily_loss

    try:
        current = await bc.get_copy_trading_balance(session)
    except Exception as e:
        log.error(f"Gagal fetch balance: {e}")
        return

    now       = time.time()
    from_last = current - _last_balance

    _last_balance = current

    # Kalau ada perubahan signifikan dari notif terakhir
    if abs(current - _notified_balance) >= MIN_CHANGE_USDT:
        if _pending_since == 0.0:
            # Mulai debounce — catat sebagai kandidat
            _pending_balance = current
            _pending_since   = now
            log.debug(f"Balance kandidat berubah: {current:.4f} USDT, tunggu konfirmasi...")
        else:
            # Cek apakah balance sudah stabil selama DEBOUNCE_SECS
            if now - _pending_since >= DEBOUNCE_SECS:
                diff = current - _notified_balance
                log.info(f"Balance STABIL dikonfirmasi: {_notified_balance:.4f} → {current:.4f} ({diff:+.4f} USDT)")

                _daily_pnl         += diff
                _daily_trade_count += 1
                if diff >= 0:
                    _daily_win += 1
                else:
                    _daily_loss += 1

                await tg.send_message(session, tg.fmt_balance_change(
                    diff=diff,
                    balance_before=_notified_balance,
                    balance_after=current,
                    daily_pnl=_daily_pnl,
                ))

                _notified_balance = current
                _pending_since    = 0.0
                _pending_balance  = 0.0
            else:
                # Masih dalam masa debounce, update kandidat ke nilai terbaru
                _pending_balance = current
    else:
        # Balance kembali ke nilai dekat notif terakhir → bukan trade, reset debounce
        if _pending_since > 0:
            log.debug("Balance kembali normal, debounce direset.")
        _pending_since   = 0.0
        _pending_balance = 0.0


# ─────────────────────────────────────────────
# Daily summary
# ─────────────────────────────────────────────

async def send_daily_summary(session: aiohttp.ClientSession):
    global _day_start_balance, _daily_pnl, _daily_trade_count, _daily_win, _daily_loss

    try:
        ct_balance = await bc.get_copy_trading_balance(session)
    except Exception:
        ct_balance = _last_balance

    await tg.send_message(session, tg.fmt_daily_summary(
        ct_balance=ct_balance,
        day_start_balance=_day_start_balance,
        trade_count=_daily_trade_count,
        win=_daily_win,
        loss=_daily_loss,
    ))
    log.info(f"Daily summary: balance {_day_start_balance:.2f} → {ct_balance:.2f} USDT")

    # Reset untuk hari berikutnya
    _day_start_balance  = ct_balance
    _daily_pnl          = 0.0
    _daily_trade_count  = 0
    _daily_win          = 0
    _daily_loss         = 0


# ─────────────────────────────────────────────
# Command handler
# ─────────────────────────────────────────────

async def handle_command(session: aiohttp.ClientSession, command: str):
    log.info(f"Command diterima: {command}")

    if command == "/status":
        try:
            ct_balance = await bc.get_copy_trading_balance(session)
            await tg.send_message(session, tg.fmt_status(
                ct_balance=ct_balance,
                day_start_balance=_day_start_balance,
                trade_count=_daily_trade_count,
                win=_daily_win,
                loss=_daily_loss,
                daily_pnl=_daily_pnl,
            ))
        except Exception as e:
            await tg.send_message(session, f"❌ Gagal ambil status: {e}")

    elif command == "/balance":
        try:
            ct_balance = await bc.get_copy_trading_balance(session)
            await tg.send_message(session, tg.fmt_balance(
                ct_balance=ct_balance,
                day_start_balance=_day_start_balance,
                daily_pnl=_daily_pnl,
            ))
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
                continue
            if text.startswith("/"):
                await handle_command(session, text.split("@")[0].lower())
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error(f"Error polling Telegram: {e}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

async def main():
    global _last_balance, _day_start_balance

    log.info("Rei aktif — monitoring copy trading futures...")
    async with aiohttp.ClientSession() as session:

        try:
            _last_balance      = await bc.get_copy_trading_balance(session)
            _day_start_balance = _last_balance
            log.info(f"Balance awal: {_last_balance:.4f} USDT")
        except Exception as e:
            log.error(f"Gagal ambil balance awal: {e}")

        await tg.send_message(
            session,
            "✨ <b>Rei aktif!</b>\n"
            "Monitoring copy trading futures dimulai.\n"
            f"💼 Balance saat ini : <b>{_last_balance:.2f} USDT</b>\n"
            f"🔄 Cek balance setiap <b>{BALANCE_POLL_SECS} detik</b>\n"
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

        balance_counter = 0
        while True:
            await poll_telegram_commands(session)

            balance_counter += 1
            if balance_counter >= BALANCE_POLL_SECS:
                await check_balance_change(session)
                balance_counter = 0

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
