# 1. S? d?ng Python 3.11 b?n nh?
FROM python:3.11-slim

# 2. Ð?t thu m?c làm vi?c
WORKDIR /app

# 3. Copy toàn b? code vào container
COPY . /app

# 4. Cài dependencies t? requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 5. Ch?y init_db.py d? t?o database n?u c?n (l?n d?u)
RUN python init_db.py

# 6. M? port (không b?t bu?c cho bot Telegram nhung thông thu?ng)
# EXPOSE 8443

# 7. Khi container ch?y, kh?i bot
CMD ["python", "bot.py"]
