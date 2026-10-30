FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
COPY lifecycle ./lifecycle
RUN uv pip install --system -e ".[wrds,workers]"
ENV NUMBA_CACHE_DIR=/tmp/numba
EXPOSE 8000
