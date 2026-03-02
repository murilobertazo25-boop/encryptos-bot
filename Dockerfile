FROM python:3.11-slim
RUN apt-get update && apt-get install -y wget gnupg
RUN pip install playwright python-telegram-bot APScheduler python-dotenv
RUN playwright install chromium
RUN playwright install-deps chromium
WORKDIR /app
COPY . .
CMD ["python", "bot.py"]

