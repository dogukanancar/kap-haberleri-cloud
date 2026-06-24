# Supabase kurulum yardimcisi
# Kullanim: .\scripts\setup_supabase.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== KAP Haberleri Cloud - Supabase kurulumu ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host ".env olusturuldu (.env.example kopyalandi)." -ForegroundColor Yellow
    } else {
        Write-Error ".env dosyasi yok. Once .env.example'dan .env olusturun."
    }
}

$dbLine = Get-Content ".env" | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
if (-not $dbLine -or $dbLine -match 'DATABASE_URL=\s*$' -or $dbLine -match 'PROJECT_REF') {
    Write-Host "ADIM GEREKLI: .env dosyasini acin ve DATABASE_URL satirina Supabase connection string yazin." -ForegroundColor Red
    Write-Host ""
    Write-Host "Supabase: Project Settings -> Database -> Connection string"
    Write-Host "  1) init_db icin: Direct connection (port 5432)"
    Write-Host "  2) Sonra Session pooler (port 5432) ile degistirin"
    Write-Host ""
    Write-Host "Ornek format:"
    Write-Host '  DATABASE_URL=postgresql://postgres.xxxxx:SIFRE@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require'
    Write-Host ""
    notepad .env
    Read-Host "DATABASE_URL kaydettikten sonra Enter'a basin"
}

Write-Host "Baglanti test ediliyor..." -ForegroundColor Cyan
python scripts/check_db.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Baglanti basarisiz. Direct connection URI ile tekrar deneyin." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Semalar uygulaniyor (init_db)..." -ForegroundColor Cyan
python scripts/init_db.py
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
python scripts/check_db.py

Write-Host ""
Write-Host "=== Yerel kurulum tamam ===" -ForegroundColor Green
Write-Host ""
Write-Host "Simdi sizin yapmaniz gerekenler:"
Write-Host "  1. GitHub -> kap-haberleri-cloud -> Settings -> Secrets -> Actions"
Write-Host "  2. DATABASE_URL secret'ini Supabase Session pooler URI ile guncelleyin"
Write-Host "  3. Panel: streamlit run app.py  (veya run_panel.bat)"
Write-Host "  4. Ayarlar sayfasindan filtreleri ve CDS/Brand ayarlarini yeniden kaydedin"
Write-Host "  5. GitHub Actions -> KAP Worker -> Run workflow ile test edin"
