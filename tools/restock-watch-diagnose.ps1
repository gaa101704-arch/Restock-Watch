# Restock-Watch diagnostic - run from anywhere
# Finds the Restock-Watch repo automatically, then runs a full diagnostic.
# Does not print Telegram secrets.

$ErrorActionPreference = "Continue"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Write-OK($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Test-RestockRepo($Path) {
    if (-not $Path) { return $false }
    return ((Test-Path (Join-Path $Path "restock_watch")) -and (Test-Path (Join-Path $Path "config.toml")))
}

Write-Host "Restock-Watch Diagnostic" -ForegroundColor White
Write-Host "You can run this script from any folder."
Write-Host "It will not display your Telegram token or chat ID."

Write-Step "Finding Restock-Watch"

$candidates = New-Object System.Collections.Generic.List[string]
$candidates.Add((Get-Location).Path)

if ($PSScriptRoot) {
    $candidates.Add($PSScriptRoot)
    $candidates.Add((Join-Path $PSScriptRoot "Restock-Watch"))
}

$common = @(
    (Join-Path $HOME "Restock-Watch"),
    (Join-Path $HOME "Desktop\Restock-Watch"),
    (Join-Path $HOME "Documents\Restock-Watch"),
    (Join-Path $HOME "Downloads\Restock-Watch"),
    (Join-Path $HOME "source\repos\Restock-Watch"),
    (Join-Path $HOME "repos\Restock-Watch"),
    (Join-Path $HOME "GitHub\Restock-Watch")
)

foreach ($path in $common) { $candidates.Add($path) }

$oneDriveRoots = @($env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial) |
    Where-Object { $_ -and (Test-Path $_) } |
    Select-Object -Unique

foreach ($root in $oneDriveRoots) {
    $candidates.Add((Join-Path $root "Restock-Watch"))
    $candidates.Add((Join-Path $root "Desktop\Restock-Watch"))
    $candidates.Add((Join-Path $root "Documents\Restock-Watch"))
}

$repo = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (Test-RestockRepo $candidate) {
        $repo = $candidate
        break
    }
}

if (-not $repo) {
    Write-Host "Not found in the usual locations. Searching your user folder..."
    Write-Host "This can take a little longer."

    try {
        $found = Get-ChildItem -Path $HOME -Directory -Filter "Restock-Watch" -Recurse -ErrorAction SilentlyContinue |
            Where-Object { Test-RestockRepo $_.FullName } |
            Select-Object -First 5

        if ($found) {
            if (@($found).Count -eq 1) {
                $repo = @($found)[0].FullName
            }
            else {
                Write-Warn "I found more than one Restock-Watch folder:"
                $i = 1
                foreach ($item in @($found)) {
                    Write-Host "  [$i] $($item.FullName)"
                    $i++
                }

                $choice = Read-Host "Enter the number for the copy you're actually running"
                $number = 0
                if ([int]::TryParse($choice, [ref]$number) -and $number -ge 1 -and $number -le @($found).Count) {
                    $repo = @($found)[$number - 1].FullName
                }
            }
        }
    }
    catch {
        Write-Warn "Automatic search hit an error: $($_.Exception.Message)"
    }
}

if (-not $repo) {
    Write-Warn "I couldn't locate Restock-Watch automatically."
    $manual = Read-Host "Paste the full path to your Restock-Watch folder"

    if (Test-RestockRepo $manual) {
        $repo = $manual
    }
    else {
        Write-Fail "That folder does not contain both config.toml and restock_watch\."
        exit 1
    }
}

Set-Location $repo
Write-OK "Found Restock-Watch:"
Write-Host "     $repo"

Write-Step "Checking Python"

$PythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $PythonCmd = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PythonCmd = "py" }

if (-not $PythonCmd) {
    Write-Fail "Python was not found in PATH."
    exit 1
}

$pyVersion = & $PythonCmd --version 2>&1
Write-OK "Using: $pyVersion"

Write-Step "Checking Telegram configuration"

$configText = Get-Content ".\config.toml" -Raw
$telegramBlock = [regex]::Match($configText, '(?ms)^\[notify\.telegram\]\s*(.*?)(?=^\[|\z)')
$telegramEnabled = $false

if ($telegramBlock.Success) {
    if ($telegramBlock.Groups[1].Value -match '(?im)^\s*enabled\s*=\s*true\s*$') {
        $telegramEnabled = $true
        Write-OK "Telegram is enabled in config.toml."
    }
    else { Write-Warn "Telegram exists in config.toml but enabled is not true." }
}
else { Write-Warn "No [notify.telegram] section found in config.toml." }

Write-Step "Checking Telegram environment variables"

$tokenLoaded = -not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_TOKEN)
$chatLoaded = -not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_CHAT_ID)

if ($tokenLoaded) { Write-OK "RESTOCK_TELEGRAM_TOKEN is already loaded." }
else { Write-Warn "RESTOCK_TELEGRAM_TOKEN is not loaded in this terminal." }

if ($chatLoaded) { Write-OK "RESTOCK_TELEGRAM_CHAT_ID is already loaded." }
else { Write-Warn "RESTOCK_TELEGRAM_CHAT_ID is not loaded in this terminal." }

Write-Step "Checking .env"

if (Test-Path ".\.env") {
    Write-OK ".env file found."

    foreach ($line in (Get-Content ".\.env")) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }

        $parts = $trimmed.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")

        if ($name -in @("RESTOCK_TELEGRAM_TOKEN", "RESTOCK_TELEGRAM_CHAT_ID")) {
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                Set-Item -Path "Env:$name" -Value $value
            }
        }
    }

    $tokenLoaded = -not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_TOKEN)
    $chatLoaded = -not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_CHAT_ID)

    if ($tokenLoaded -and $chatLoaded) {
        Write-OK "Telegram values from .env are loaded for this diagnostic."
    }
    else { Write-Warn ".env exists, but one or both Telegram values are missing/blank." }
}
else { Write-Warn "No .env file was found in the Restock-Watch folder." }

Write-Step "Testing Telegram directly"

$telegramDirectOK = $false
if (-not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_TOKEN) -and -not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_CHAT_ID)) {
    try {
        $getMeUrl = "https://api.telegram.org/bot$($env:RESTOCK_TELEGRAM_TOKEN)/getMe"
        $me = Invoke-RestMethod -Uri $getMeUrl -Method Get -TimeoutSec 15
        if ($me.ok) { Write-OK "Telegram bot token is valid. Bot: @$($me.result.username)" }
        else { Write-Fail "Telegram rejected the bot token." }
    }
    catch { Write-Fail "Telegram token check failed: $($_.Exception.Message)" }

    try {
        $sendUrl = "https://api.telegram.org/bot$($env:RESTOCK_TELEGRAM_TOKEN)/sendMessage"
        $body = @{
            chat_id = $env:RESTOCK_TELEGRAM_CHAT_ID
            text = "Restock-Watch diagnostic test: Telegram delivery is working."
            disable_web_page_preview = $true
        } | ConvertTo-Json

        $sent = Invoke-RestMethod -Uri $sendUrl -Method Post -ContentType "application/json" -Body $body -TimeoutSec 15
        if ($sent.ok) {
            $telegramDirectOK = $true
            Write-OK "Direct Telegram test message sent successfully."
        }
        else { Write-Fail "Telegram did not accept the test message." }
    }
    catch {
        Write-Fail "Telegram message test failed: $($_.Exception.Message)"
        Write-Host "Common causes: wrong chat ID, invalid token, or the bot was never messaged first."
    }
}
else { Write-Warn "Skipping direct Telegram test because token/chat ID are not both available." }

Write-Step "Testing Restock-Watch notifications"

& $PythonCmd -m restock_watch --test-notify
$notifyExit = $LASTEXITCODE
Write-Host "Notification test exit code: $notifyExit"

if ($notifyExit -eq 0) { Write-OK "All enabled Restock-Watch notification channels passed." }
else { Write-Warn "At least one Restock-Watch notification channel failed." }

Write-Step "Running one verbose dry-run"
Write-Host "This checks the configured retailer sources."
Write-Host "It will not send a stock alert or alter the saved state."

& $PythonCmd -m restock_watch -v --dry-run
$watchExit = $LASTEXITCODE
Write-Host ""
Write-Host "Watcher dry-run exit code: $watchExit"

Write-Step "Checking saved watcher state"

$statePath = ".\data\state.json"
if (Test-Path $statePath) {
    try {
        $state = Get-Content $statePath -Raw | ConvertFrom-Json
        if ($state.statuses) {
            Write-Host "Last saved retailer statuses:"
            $state.statuses.PSObject.Properties |
                Sort-Object Name |
                ForEach-Object { Write-Host ("  {0}: {1}" -f $_.Name, $_.Value) }
        }
        else { Write-Warn "State file exists, but no saved statuses were found." }
    }
    catch { Write-Warn "State file exists but could not be parsed." }
}
else { Write-Warn "No data\state.json file exists yet. The watcher may not have completed a normal run." }

Write-Step "Summary"
Write-Host "Repo:                        $repo"
Write-Host "Telegram enabled in config: $telegramEnabled"
Write-Host "Telegram token available:   $(-not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_TOKEN))"
Write-Host "Telegram chat ID available: $(-not [string]::IsNullOrWhiteSpace($env:RESTOCK_TELEGRAM_CHAT_ID))"
Write-Host "Direct Telegram send:       $telegramDirectOK"
Write-Host "Notification test exit:     $notifyExit"
Write-Host "Watcher dry-run exit:       $watchExit"
Write-Host ""
Write-Host "Send the output to whoever is helping you troubleshoot." -ForegroundColor Cyan
Write-Host "Do NOT send the contents of .env or your Telegram token." -ForegroundColor Yellow
