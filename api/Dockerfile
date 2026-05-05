FROM python:3.12-slim-bookworm

# libsndfile1：Python soundfile 扩展依赖的系统库（Bookworm 包名）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api/requirements.txt /app/requirements-api.txt

# 阿里云 ECS 访问官方 PyPI 易超时或解析中断；默认清华镜像，可通过构建参数改回 https://pypi.org/simple
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=15

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefer-binary \
        -r /app/requirements-api.txt \
        -i "${PIP_INDEX_URL}" \
        --trusted-host "${PIP_TRUSTED_HOST}"

COPY assistant_stock_bot-5.py /app/
COPY faq.txt /app/
COPY api/app /app/app
COPY api/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN mkdir -p /app/image_show

ENV PYTHONPATH=/app
WORKDIR /app

EXPOSE 8000
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
