# The desk API and its MCP server.
FROM python:3.13-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.13-slim
RUN useradd --create-home --uid 10001 desk
COPY --from=build /install /usr/local
WORKDIR /app
COPY config ./config
COPY data ./data
COPY migrations ./migrations
ENV DESK_CONFIG=/app/config DESK_DATA=/app/data PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["desk", "serve", "--port", "8080"]
