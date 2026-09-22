# 1. Start with a standard Python base image
FROM python:3.9-slim

# 2. Copy the official uv executable directly into your image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. Set standard optimization environment variables for uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 4. Set the working directory
WORKDIR /app

# 5. Copy configuration files first to utilize Docker layer caching
COPY pyproject.toml uv.lock ./

# 6. Install project dependencies without installing the project itself
RUN uv sync --frozen --no-install-project

# 7. Copy the rest of your application code
COPY . .

# 8. Complete the sync (installs your local project packages)
RUN uv sync --frozen

# 9. Expose port and run the app using 'uv run'
EXPOSE 8080
CMD ["uv", "run", "python", "-m", "myapp"]
