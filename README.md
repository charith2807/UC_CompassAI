# UC_CompassAI

## Extraction setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-crawl.txt
.venv/bin/python -m crawler.extract --raw-dir ../data/raw
```

Run these commands from this repository. If raw files are stored in the repository's
`data/raw/`, omit `--raw-dir`. Each raw file needs its crawler-generated `.meta.json`.
Outputs go to `data/processed/` and `data/extract_log.csv`. Missing input is rejected
before existing output is deleted. Raw and normalized content are git-ignored.

See [the ingestion report](reports/01_ingestion.md) for current results and limitations.
