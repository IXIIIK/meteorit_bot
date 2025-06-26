#!/bin/bash
set -e

echo "🔧 Инициализация базы..."
python -c "import asyncio; from bot.db import init_db; asyncio.run(init_db())"

echo "🚀 Запуск бота..."
exec python bot/main.py
