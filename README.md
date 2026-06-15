# Olibber Bot

---

## About

A Telegram bot that downloads Instagram posts, reels, and stories and sends them straight into your chat.

---

## What It Does

Send an Instagram link to the bot — it downloads the photos or videos and sends them back to you in Telegram. That's it.

**Supported content:** Posts, reels.

## Features

- 📸 **Download posts & reels** — Just paste a link, get the media
- 🎬 **Stories support** — Download stories too
- 👥 **Group chats** — Add to a group, make it admin, and anyone can use it
- ⚡ **Fast** — Streams media directly, no waiting for downloads
- 🔒 **Rate limiting** — Prevents spam and abuse

## Quick Start

### 1. Install

```bash
git clone https://github.com/akbarjorayev/olibber.git
cd olibber
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
```

Edit `.env` with your values.

### 3. Generate Instagram session

```bash
python tools/instagram_session_b64.py
```

Enter your Instagram credentials. Copy the output into `INSTALOADER_SESSION_B64` in your `.env`.

### 4. Run

```bash
python main.py
```

That's it. The bot is live.

### 5. Use Olibber

If you do not want to do all of them, just go to [@olibberBot](https://t.me/olibber_bot) and start sending Instagram links.

## How It Works

1. User sends an Instagram link
2. Bot fetches the media
3. Bot sends the photos/videos back to the chat
4. Done ✨
