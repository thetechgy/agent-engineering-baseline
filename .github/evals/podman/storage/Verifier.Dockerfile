FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
WORKDIR /workspace
RUN mkdir -p /workspace/output
COPY test.sh entry.json /tests/
COPY verifier/grader.py /tests/verifier/grader.py
RUN chmod 700 /tests /tests/test.sh
