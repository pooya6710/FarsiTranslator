# Telegram Bot

A simple Python-based Telegram bot with basic command handling functionality.

## Features

- Responds to basic commands (`/start`, `/help`, `/about`)
- Error handling for connection issues
- Logging of bot activities

## Prerequisites

- Python 3.7+
- python-telegram-bot library
- python-dotenv library

## Configuration

1. Clone this repository
2. Copy `.env.example` to `.env`
3. Replace the placeholder in `.env` with your actual Telegram bot token:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

## Running the Bot

Run the bot using:

```bash
python main.py
