FROM docker.io/library/python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /opt/requirements.txt && useradd --uid 1000 --create-home agent
COPY . /opt/experiment
RUN chmod -R a+rX /opt/experiment && mkdir /workspace && chown agent:agent /workspace
USER agent
WORKDIR /workspace
ENV PYTHONPATH=/workspace
CMD ["sleep", "infinity"]
