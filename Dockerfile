# PitSense - one container, one port, one process.
#
# The app ships with the validated races already exported to a bundle
# (backend/app/data/races, see scripts/export_race_bundle.py), so a deployed
# instance needs no FastF1 cache, downloads nothing on a request, and does not
# depend on an upstream API staying up during a demo. That is why the runtime
# image installs the serving dependencies only - FastF1 and pandas are build- and
# research-time tools here, and leaving them out takes the image from roughly a
# gigabyte to a couple of hundred megabytes.
#
# It must run as a SINGLE worker. Each visitor's loaded race lives in this
# process's memory (app/session_store.py); a second worker would serve half of
# them an empty slot.

# ---------------------------------------------------------------- frontend
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ----------------------------------------------------------------- runtime
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Serving dependencies only. requirements.txt additionally carries FastF1 and the
# test tooling, which the bundle makes unnecessary at request time.
RUN pip install \
      "fastapi>=0.115,<1" \
      "pydantic>=2.7,<3" \
      "numpy>=1.26,<3" \
      "uvicorn[standard]>=0.27,<1"

COPY backend/app ./app
COPY --from=frontend /build/dist ./static

# The timeline database is written at runtime; keep it somewhere writable.
ENV PITSENSE_DB_PATH=/tmp/pitsense.sqlite3

EXPOSE 8000

# Hosts that inject $PORT (Render, Railway, Cloud Run) are honoured; otherwise
# 8000. One worker, deliberately - see the note above.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
