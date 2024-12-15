# 构建阶段
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 最终阶段
FROM python:3.11-slim

WORKDIR /app

# 复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 复制应用代码
COPY main.py .
COPY keep_alive.py .
COPY .env .

RUN addgroup -g 10016 user && \
    adduser  --disabled-password  --no-create-home --uid 10016 --ingroup user user1

USER 10016

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--loop", "uvloop", "--http", "httptools"]
