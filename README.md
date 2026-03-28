# 零 Rei — Copy Trading Monitor Bot

> *"Aku selalu mengawasi market untukmu."*

<p align="center">
  <img src="assets/logo.png" alt="Rei Logo" width="160"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white"/>
  <img src="https://img.shields.io/badge/Binance-Futures-F0B90B?style=for-the-badge&logo=binance&logoColor=black"/>
  <img src="https://img.shields.io/badge/Copy_Trading-Monitor-00C896?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>
</p>

Rei adalah bot Telegram untuk monitoring Binance Copy Trading Futures secara real-time. Dibangun dengan Python, Rei mengirimkan notifikasi otomatis dan daily summary langsung ke Telegram kamu.

---

## ✨ Fitur

| Fitur | Deskripsi |
|---|---|
| 🟢 Posisi Dibuka | Notifikasi real-time saat posisi baru dibuka |
| 🔴 Posisi Ditutup | Notifikasi lengkap dengan estimasi PnL |
| ⚠️ Drawdown Alert | Alert otomatis saat drawdown melebihi threshold |
| 🌙 Daily Summary | Laporan harian terjadwal otomatis |
| 📊 /status | Lihat semua posisi aktif on-demand |
| 💼 /balance | Cek saldo copy trading wallet |
| 📋 /report | Trigger daily report kapan saja |

---

## 🚀 Quick Start

### 1. Clone repo
```bash
git clone git@github.com:alvinardiansyahdev/rei.git
cd rei
```

### 2. Setup environment
```bash
cp .env.example .env
nano .env
```

Isi file `.env`:
```env
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

DRAWDOWN_ALERT_PERCENT=5.0
DAILY_SUMMARY_HOUR=23
DAILY_SUMMARY_MINUTE=59
POLL_INTERVAL_SECONDS=30
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Jalankan
```bash
python monitor.py
```

---

## ⚙️ Deploy di VPS (systemd)

```bash
sudo nano /etc/systemd/system/rei.service
```

```ini
[Unit]
Description=Rei - Copy Trading Monitor
After=network.target

[Service]
WorkingDirectory=/home/user/rei
ExecStart=/usr/bin/python3 /home/user/rei/monitor.py
Restart=always
RestartSec=10
User=user

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable rei
sudo systemctl start rei

# Cek status
sudo systemctl status rei

# Live log
journalctl -u rei -f
```

---

## 📋 Telegram Commands

| Command | Fungsi |
|---|---|
| `/status` | Posisi copy trade yang sedang aktif |
| `/balance` | Saldo copy trading wallet + unrealized PnL |
| `/report` | Daily report on-demand |
| `/help` | Daftar semua command |

---

## 🔑 Binance API Setup

1. Login ke [Binance](https://binance.com)
2. Pergi ke **Account → API Management**
3. Buat API Key baru
4. Centang **Enable Reading** dan **Enable Futures**
5. Simpan API Key & Secret ke `.env`

> ⚠️ Jangan pernah centang *Enable Withdrawals* untuk keamanan.

---

## 📁 Struktur Project

```
rei/
├── .env.example       # Template konfigurasi
├── .gitignore
├── binance_client.py  # Binance API client
├── config.py          # Load environment variables
├── monitor.py         # Main loop + scheduler + command handler
├── requirements.txt
└── telegram_bot.py    # Telegram formatter & sender
```

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **aiohttp** — Async HTTP client
- **APScheduler** — Daily summary scheduler
- **Binance API** — `/fapi/v3/` & `/sapi/v1/`
- **Telegram Bot API** — Long polling

---

## ⚠️ Disclaimer

Bot ini hanya untuk monitoring dan tidak melakukan trading apapun. Seluruh keputusan trading dilakukan oleh lead trader yang kamu follow di Binance Copy Trading.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/alvinardiansyahdev">alvinardiansyahdev</a>
</p>
