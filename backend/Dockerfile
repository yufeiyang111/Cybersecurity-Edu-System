FROM python:3.11-slim

WORKDIR /app

# 安装必要的编译工具库
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 预先复制依赖清单并安装，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 复制后端全量源码
COPY . .

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py

EXPOSE 5001

# 使用 Gunicorn 生产级 WSGI 服务器启动 4 个 Worker
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "--timeout", "120", "app:create_app()"]
