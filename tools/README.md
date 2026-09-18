# Diagnostic tools

## Windows / PowerShell

[`restock-watch-diagnose.ps1`](restock-watch-diagnose.ps1) is a run-anywhere diagnostic for Windows users who are unsure whether Restock Watch or Telegram is configured correctly.

It will:

- locate the user's `Restock-Watch` folder automatically;
- verify Python is available;
- check whether Telegram is enabled in `config.toml`;
- check whether the Telegram token and chat ID are present without printing either secret;
- load those two values from `.env` for the diagnostic session when available;
- validate the Telegram bot token and send a direct test message;
- run `python -m restock_watch --test-notify`;
- run one verbose `--dry-run` without changing saved state; and
- show the last saved retailer statuses when a state file exists.

### Run it

Download the `.ps1` file, then from a fresh PowerShell window run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\path\to\restock-watch-diagnose.ps1"
```

A user can also type:

```powershell
powershell -ExecutionPolicy Bypass -File 
```

then drag the downloaded script into the PowerShell window and press Enter.

The diagnostic intentionally does **not** print the Telegram bot token or chat ID. Users should share the diagnostic output, not their `.env` file.
