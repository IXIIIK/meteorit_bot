# Используем минимальный Python-образ
FROM python:3.11-slim

# Установка зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Устанавливаем переменные окружения (если нужно)
ENV PYTHONUNBUFFERED=1

# Запуск бота
CMD ["python", "bot/bot.py"]
