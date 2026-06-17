# GitHub Actions worker'i harici zamanlayici (cron-job.org) veya manuel test icin tetikler.
# KAP Worker icinde CDS ve Brand de calisir (paneldeki saat gelince gonderir).
# Kullanim: $env:GITHUB_TOKEN = "ghp_..." ; .\scripts\trigger_github_worker.ps1

param(
    [string]$Owner = "dogukanancar",
    [string]$Repo = "kap-haberleri-cloud",
    [string]$Ref = "main"
)

$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Error "GITHUB_TOKEN ortam degiskeni tanimli degil."
    exit 1
}

$uri = "https://api.github.com/repos/$Owner/$Repo/actions/workflows/kap_worker.yml/dispatches"
$body = @{ ref = $Ref } | ConvertTo-Json

$response = Invoke-WebRequest -Uri $uri -Method Post `
    -Headers @{
        Authorization = "Bearer $token"
        Accept = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
    } `
    -Body $body `
    -ContentType "application/json"

if ($response.StatusCode -eq 204) {
    Write-Host "KAP Worker tetiklendi (CDS + Brand dahil). Actions sekmesinden takip edin."
} else {
    Write-Host "Beklenmeyen yanit: $($response.StatusCode)"
}
