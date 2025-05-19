# 1. S? d?ng Python 3.11 b?n nh?
FROM python:3.11-slim

# 2. �?t thu m?c l�m vi?c
WORKDIR /app

# 3. Copy to�n b? code v�o container
COPY . /app

# 4. C�i dependencies t? requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 5. Ch?y init_db.py d? t?o database n?u c?n (l?n d?u)
RUN python init_db.py

# 6. M? port (kh�ng b?t bu?c cho bot Telegram nhung th�ng thu?ng)
# EXPOSE 8443

# 7. Khi container ch?y, kh?i bot
CMD ["python", "bot.py"]
