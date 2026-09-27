# =====================================================================
#  HMS setup script - only ASCII, PS 5.1 compatible
# =====================================================================

$ErrorActionPreference = "Stop"

$PgUser           = "hmsusr"
$PgPassword       = "hmspwd"
$PgDatabase       = "hmsdb"
$PostgresSuperUser = "postgres"

function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    [!]  $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "    [X]  $m" -ForegroundColor Red }

function Fail($msg) {
    Err $msg
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 0. Check we are in project root --------------------------------
Step "Checking project files"
$required = @("app.py","model.py","schema.sql","requirements.txt")
foreach ($f in $required) {
    if (-not (Test-Path $f)) {
        Fail "File '$f' not found. Run this script from the project root (where app.py lives)."
    }
}
Ok "Required files present."

# --- 1. Locate psql.exe ---------------------------------------------
Step "Locating psql.exe"
$psql = $null

$cmd = Get-Command psql.exe -ErrorAction SilentlyContinue
if ($cmd) {
    $psql = $cmd.Source
    Ok "psql found in PATH: $psql"
}

if (-not $psql) {
    $roots = @(
        "C:\Program Files\PostgreSQL",
        "C:\Program Files (x86)\PostgreSQL",
        "D:\Program Files\PostgreSQL",
        "C:\PostgreSQL"
    )
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $dirs = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
                    Sort-Object Name -Descending
            foreach ($d in $dirs) {
                $candidate = Join-Path $d.FullName "bin\psql.exe"
                if (Test-Path $candidate) {
                    $psql = $candidate
                    break
                }
            }
        }
        if ($psql) { break }
    }
    if ($psql) {
        $pgBin = Split-Path $psql -Parent
        $env:Path = $pgBin + ";" + $env:Path
        Ok "psql found: $psql"
        Write-Host "    (added to PATH for this session only)" -ForegroundColor DarkGray
    }
}

if (-not $psql) {
    Write-Host ""
    Write-Host "psql.exe not found. Install PostgreSQL first:" -ForegroundColor Yellow
    Write-Host "  https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
    Fail "PostgreSQL not found."
}

# --- 2. Check PostgreSQL service ------------------------------------
Step "Checking PostgreSQL service"
$services = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if (-not $services) {
    Fail "PostgreSQL service not found. Is PostgreSQL installed?"
}
$running = @($services | Where-Object { $_.Status -eq "Running" })
if ($running.Count -eq 0) {
    Warn "PostgreSQL service is not running. Trying to start..."
    foreach ($svc in $services) {
        try {
            Start-Service $svc.Name
            Ok "Started service $($svc.Name)"
        } catch {
            Fail "Could not start service $($svc.Name). Run PowerShell as Administrator."
        }
    }
} else {
    Ok "PostgreSQL service is running."
}

# --- 3. Python + venv -----------------------------------------------
Step "Checking Python"
$py = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $py) { Fail "Python not found. Install Python 3.11+ and add to PATH." }
$v = & python --version 2>&1
Ok "$v"

Step "Creating virtual environment"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Ok "Created .venv"
} else {
    Ok ".venv already exists"
}
$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { Fail "Not found: $venvPython" }

Step "Installing dependencies (may take a few minutes)"
& $venvPython -m pip install --upgrade pip | Out-Null
& $venvPython -m pip install -r requirements.txt
Ok "Dependencies installed."

# --- 4. .env --------------------------------------------------------
Step "Creating .env"
if (Test-Path ".env") {
    Ok ".env already exists, keeping it."
} else {
    $secret = (& $venvPython -c "import secrets; print(secrets.token_hex(32))").Trim()
    $lines = @(
        "SECRET_KEY=$secret",
        "DATABASE_URL=postgresql+psycopg://" + $PgUser + ":" + $PgPassword + "@localhost/" + $PgDatabase
    )
    $content = ($lines -join "`n") + "`n"
    [System.IO.File]::WriteAllText("$PWD\.env", $content, [System.Text.UTF8Encoding]::new($false))
    Ok ".env created (SECRET_KEY generated)"
}

# --- 5. Create role and database ------------------------------------
Step "Connecting to PostgreSQL"
Write-Host "    Enter the password for user '$PostgresSuperUser' (the one you set during PostgreSQL install)." -ForegroundColor Yellow
$secure = Read-Host "    postgres password" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$pgPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$env:PGPASSWORD = $pgPass
$null = & $psql -U $PostgresSuperUser -h localhost -d postgres -c "SELECT 1;" 2>&1
if ($LASTEXITCODE -ne 0) {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    Fail "Cannot connect to PostgreSQL as '$PostgresSuperUser'. Check the password and that the service is running."
}
Ok "Connected."

# Create role if not exists (single statement, no DO block)
$roleExists = & $psql -U $PostgresSuperUser -h localhost -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PgUser';"
if ("$roleExists".Trim() -eq "1") {
    Ok "Role '$PgUser' already exists."
} else {
    & $psql -U $PostgresSuperUser -h localhost -d postgres -c "CREATE ROLE $PgUser LOGIN PASSWORD '$PgPassword';"
    if ($LASTEXITCODE -ne 0) {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        Fail "Could not create role $PgUser"
    }
    Ok "Role '$PgUser' created."
}

# Create database if not exists
$dbExists = & $psql -U $PostgresSuperUser -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PgDatabase';"
if ("$dbExists".Trim() -eq "1") {
    Ok "Database '$PgDatabase' already exists."
} else {
    & $psql -U $PostgresSuperUser -h localhost -d postgres -c "CREATE DATABASE $PgDatabase OWNER $PgUser;"
    if ($LASTEXITCODE -ne 0) {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        Fail "Could not create database $PgDatabase"
    }
    Ok "Database '$PgDatabase' created."
}

# Grant schema public (PostgreSQL 15+)
$grantSql = "GRANT ALL ON SCHEMA public TO $PgUser; ALTER SCHEMA public OWNER TO $PgUser;"
& $psql -U $PostgresSuperUser -h localhost -d $PgDatabase -c $grantSql 2>&1 | Out-Null

Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

# --- 6. Apply schema ------------------------------------------------
Step "Applying schema.sql"
$env:PGPASSWORD = $PgPassword
$env:PGCLIENTENCODING = "UTF8"
& $psql -U $PgUser -h localhost -d $PgDatabase -f "schema.sql"
$schemaExit = $LASTEXITCODE
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:\PGCLIENTENCODING -ErrorAction SilentlyContinue

if ($schemaExit -ne 0) {
    Warn "psql returned code $schemaExit. If objects already existed, this is fine."
} else {
    Ok "Schema applied."
}

# --- 7. Verify tables -----------------------------------------------
Step "Verifying tables"
$env:PGPASSWORD = $PgPassword
$raw = & $psql -U $PgUser -h localhost -d $PgDatabase -tAc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

$list = @()
if ($raw) {
    $list = @($raw -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
}
Write-Host "    Tables found: $($list.Count)" -ForegroundColor DarkGray
foreach ($t in $list) { Write-Host "      - $t" -ForegroundColor DarkGray }

$must = @("users","organizations","employees","buildings","systems","building_systems","maintenance","requests")
$missing = @($must | Where-Object { $_ -notin $list })
if ($missing.Count -gt 0) {
    Fail "Missing tables: $($missing -join ', '). Check schema.sql."
}
Ok "All 8 tables present."

# --- 8. Done --------------------------------------------------------
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Run the app:" -ForegroundColor White
Write-Host "      .\.venv\Scripts\Activate.ps1"
Write-Host "      python app.py"
Write-Host ""
Write-Host "  Open: http://127.0.0.1:5000" -ForegroundColor White
Write-Host "  Login: admin" -ForegroundColor White
Write-Host "  Password: 1" -ForegroundColor White
Write-Host ""
Write-Host "  Change the password after first login." -ForegroundColor Yellow
Write-Host ""

$answer = Read-Host "Start the app now? (y/n)"
if ($answer -match "^(y|Y)") {
    Write-Host ""
    Write-Host "Running python app.py (Ctrl+C to stop)..." -ForegroundColor Cyan
    Write-Host ""
    & $venvPython app.py
} else {
    Read-Host "Press Enter to exit"
}