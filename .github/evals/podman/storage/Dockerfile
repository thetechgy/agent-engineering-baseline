FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
RUN rm -f /etc/apt/sources.list.d/* && rm -rf /var/lib/apt/lists/* && \
    printf '%s\n' \
      'deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot.debian.org/archive/debian/20261103T000000Z/ trixie main' \
      'deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot.debian.org/archive/debian-security/20261103T000000Z/ trixie-security main' \
      > /etc/apt/sources.list && \
    useradd --create-home --uid 1000 agent && \
    mkdir -p /workspace/output && chown agent:agent /workspace/output
ENV HOME=/home/agent
WORKDIR /workspace
