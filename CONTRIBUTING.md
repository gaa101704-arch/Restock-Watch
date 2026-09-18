# Contributing

Thanks for helping improve Restock Watch.

## Development setup

Restock Watch requires Python 3.11 or newer.

```bash
git clone https://github.com/gaa101704-arch/Restock-Watch.git
cd Restock-Watch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

For browser-source work:

```bash
python -m pip install -e ".[browser]"
python -m playwright install chromium
```

## Pull requests

Keep changes focused and include tests for behavior changes. In particular, source adapters should include parser fixtures or mocked page responses for both positive and negative availability states.

Before opening a pull request:

1. Run the full unit test suite.
2. Run `python -m compileall -q restock_watch`.
3. Do not commit `.env`, `config.toml`, state files, credentials, tokens, cookies, or captured pages containing private data.
4. Update documentation when configuration or behavior changes.

## Source adapter rules

Source adapters must follow three safety rules:

- Never infer `OUT_OF_STOCK` from a timeout, CAPTCHA, parsing failure, or blocked request.
- Return only statuses defined in `restock_watch.status`.
- Use stable target labels because target labels become persistent state keys.

See [docs/ADDING-A-SOURCE.md](docs/ADDING-A-SOURCE.md) for the adapter contract.
