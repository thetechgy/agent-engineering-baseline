FROM docker.io/library/python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
RUN useradd --uid 1000 --create-home agent && mkdir /workspace && chown agent:agent /workspace
COPY codex /opt/codex
COPY native_probe.py /opt/probe.py
COPY broker.py /opt/broker.py
RUN chmod -R a+rX /opt/codex /opt/probe.py /opt/broker.py
USER agent
WORKDIR /workspace
CMD ["python", "/opt/probe.py"]
