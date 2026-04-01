FROM python:3.12-alpine AS builder
RUN pip install uv
COPY pyproject.toml /app/
WORKDIR /app
RUN uv pip install --system --no-cache .

FROM python:3.12-alpine
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src /app/src
WORKDIR /app
ENV PYTHONPATH=/app/src
EXPOSE 8000
ENTRYPOINT ["python", "-m", "mcp_mail.main"]
CMD ["--transport", "http"]
