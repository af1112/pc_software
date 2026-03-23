# استفاده از نسخه پایدار و سبک پایتون
FROM python:3.10-slim

# تنظیم متغیرهای محیطی
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# نصب پیش‌نیازهای سیستم‌عامل (برای MySQL و کتابخانه‌های پایتونی)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# تعیین پوشه کاری
WORKDIR /app

# نصب نیازمندی‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir Pillow

# کپی کردن کل پروژه به داخل کانتینر
COPY . .

# آماده‌سازی اسکریپت استارت
RUN chmod +x /app/entrypoint.sh

# جمع‌آوری فایل‌های استاتیک
RUN python manage.py collectstatic --noinput

# باز کردن پورت ۸۰۰۰
EXPOSE 8000

# اجرای migrate و سپس شروع به کار با Gunicorn
CMD ["/app/entrypoint.sh"]
