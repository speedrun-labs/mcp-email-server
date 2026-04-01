FROM python:3.12-alpine AS builder
RUN pip install uv
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN uv pip install --system --no-cache .

FROM python:3.12-alpine
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
EXPOSE 8000
ENTRYPOINT ["python", "-m", "mcp_mail.main"]
CMD ["--transport", "http"]
