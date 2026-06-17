# GitHub Actions worker'larini harici zamanlayici (cron-job.org) veya manuel test icin tetikler.
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

$headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}
$body = (@{ ref = $Ref } | ConvertTo-Json)

$workflows = @(
    "kap_worker.yml",
    "cds_brand_worker_poll.yml"
)

foreach ($workflow in $workflows) {
    $uri = "https://api.github.com/repos/$Owner/$Repo/actions/workflows/$workflow/dispatches"
    $response = Invoke-WebRequest -Uri $uri -Method Post -Headers $headers -Body $body -ContentType "application/json"
    if ($response.StatusCode -eq 204) {
        Write-Host "$workflow tetiklendi."
    } else {
        Write-Host "$workflow beklenmeyen yanit: $($response.StatusCode)"
    }
}

Write-Host "Actions sekmesinden calismalari takip edin."
