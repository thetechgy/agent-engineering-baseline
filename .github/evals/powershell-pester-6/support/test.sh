#!/bin/sh
# Authored native verifier entry point; no evaluator installation or generated runner.
set -eu
exec python3 -I /tests/verifier/grader.py
