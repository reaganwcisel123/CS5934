# US-003 outreach pipeline - convenience targets.
# `make all` runs the safe, credential-free chain (ingest -> report).

PY ?= python3

.PHONY: help setup ingest send send-live track followup followup-live report all clean

help:
	@echo "Targets: setup ingest send send-live track followup followup-live report all clean"

setup:
	$(PY) -m pip install -r requirements.txt
	cp -n config.example.yaml config.yaml || true

ingest:          ## load the curated contact list into the DB
	$(PY) run.py ingest

send:            ## dry run (renders, sends nothing)
	$(PY) run.py send

send-live:       ## actually sends via Gmail
	$(PY) run.py send --send

track:
	$(PY) run.py track

followup:        ## dry run
	$(PY) run.py followup

followup-live:
	$(PY) run.py followup --send

report:
	$(PY) run.py report

all:
	$(PY) run.py all

clean:
	rm -rf data/*.db data/*.md pipeline/__pycache__ __pycache__
