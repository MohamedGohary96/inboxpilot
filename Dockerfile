FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Mirror what a Linux user would have: Python 3.11+, Node 20+, basic build tools,
# libnotify-bin for the notification fallback, plus dbus headers for `secretstorage`
# which `keyring` uses on Linux.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git bash \
        python3.11 python3.11-venv python3-pip \
        build-essential pkg-config \
        libdbus-1-dev libdbus-glib-1-dev libgirepository1.0-dev \
        libnotify-bin \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# `python` → python3.11 so the launcher's prereq check passes
RUN ln -sf /usr/bin/python3.11 /usr/local/bin/python \
 && ln -sf /usr/bin/python3.11 /usr/local/bin/python3 \
 && python3 -m pip install --upgrade pip

WORKDIR /app
COPY . /app

# A fake HOME so the visible-folder logic and platformdirs both work without
# touching the host's filesystem.
ENV HOME=/root
RUN mkdir -p /root/inboxpilot

CMD ["bash"]
