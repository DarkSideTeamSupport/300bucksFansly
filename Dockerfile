FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	QT_QPA_PLATFORM=offscreen \
	LIBGL_ALWAYS_SOFTWARE=1

# opentele → PyQt5 нужен libgthread и базовые Qt/X11 libs (даже headless)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		ca-certificates \
		libglib2.0-0 \
		libgl1 \
		libxkbcommon0 \
		libdbus-1-3 \
		libxcb1 \
		libxcb-xinerama0 \
		libxcb-cursor0 \
		libfontconfig1 \
		libx11-6 \
		libxext6 \
		libxrender1 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data sessions dumps landing/media tdata_out

EXPOSE 1337

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "1337"]
