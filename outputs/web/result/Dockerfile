# Auto-eject A1 web app image -- NOT built in CI.
#
# Building this image downloads a pinned BambuStudio CLI and is therefore kept
# out of automated test runs.  The CLI stage below is commented on purpose so a
# plain `docker build` cannot silently pull an unpinned slicer.
#
# To build locally: uncomment the BambuStudio block, verify the checksum/URL in
# the binding environment, then run `docker build -t autoeject .`.

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

# uv, pinned by digest so the runtime dependency resolution is reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY autoeject ./autoeject
COPY app ./app
COPY profiles ./profiles

# ---------------------------------------------------------------------------
# Pinned BambuStudio CLI (not run in CI).
#
# BambuStudio ships an AppImage; extract it into /opt/bambustudio and expose
# the CLI.  Pin the exact release used for the seed fixture and verify the
# checksum before use.
#
# ARG BAMBU_STUDIO_VERSION=02.04.00.70
# ARG BAMBU_STUDIO_URL=https://github.com/bambulab/BambuStudio/releases/download/v${BAMBU_STUDIO_VERSION}/Bambu_Studio_linux_ubuntu-v${BAMBU_STUDIO_VERSION}.AppImage
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends fuse libgl1 libglib2.0-0 \
#     && rm -rf /var/lib/apt/lists/* \
#     && curl -fsSL "${BAMBU_STUDIO_URL}" -o /opt/BambuStudio.AppImage \
#     && chmod +x /opt/BambuStudio.AppImage \
#     && /opt/BambuStudio.AppImage --appimage-extract \
#     && mv squashfs-root /opt/bambustudio
ENV BAMBU_CLI=/opt/bambustudio/AppRun \
    BAMBU_PROFILE_ROOT=/opt/bambustudio/resources/profiles/BBL
# ---------------------------------------------------------------------------

EXPOSE 8000

# The FastAPI app serves the static UI and the /api/check, /api/build and
# /api/simulate endpoints.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
