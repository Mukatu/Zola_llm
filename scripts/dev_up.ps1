#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Démarre l'atelier de dev HYBRIDE ZolaOS d'un coup : box (:8000) + cortex (:8001)
  + Postgres/Redis/MinIO, migrations, semence (admin + cabinet + client + tunnel),
  et frontend. Reproductible — remplace tout montage manuel.

.DESCRIPTION
  L'atelier tourne par défaut en **staging** (login réel, comme la prod ; cookies
  non-Secure pour marcher sur http://localhost). Le tunnel box→cortex est câblé
  automatiquement (credential de box généré par la semence). Le LLM (Ollama) n'est
  pas démarré ici (cf. rappel final / lanceur de démarrage de session).

.PARAMETER Dev
  Bascule l'atelier en APP_ENV=dev (auto-login, itération rapide) au lieu de staging.

.EXAMPLE
  pwsh scripts/dev_up.ps1
  pwsh scripts/dev_up.ps1 -Dev
#>

[CmdletBinding()]
param(
  [string]$BgeM3Path = "C:\Users\duqat\bge-m3",
  [int]$ApiPort = 8000,
  [int]$CortexPort = 8001,
  [int]$FrontendPort = 3000,
  [switch]$Dev
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($m) { Write-Host "▶ $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "⚠ $m" -ForegroundColor Yellow }

function Set-EnvVar($key, $val) {
  $envPath = Join-Path $root ".env"
  $lines = if (Test-Path $envPath) { @(Get-Content $envPath) } else { @() }
  $found = $false
  $out = foreach ($l in $lines) {
    if ($l -match "^\s*$key=") { $found = $true; "$key=$val" } else { $l }
  }
  if (-not $found) { $out = @($out) + "$key=$val" }
  Set-Content -Path $envPath -Value $out -Encoding UTF8
}

# --- 1. Docker ------------------------------------------------------------
Info "Vérification de Docker…"
docker info *> $null 2>&1
if ($LASTEXITCODE -ne 0) {
  $dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dd) {
    Warn "Docker arrêté — démarrage de Docker Desktop…"
    Start-Process $dd
    for ($i = 0; $i -lt 60; $i++) { Start-Sleep 3; docker info *> $null 2>&1; if ($LASTEXITCODE -eq 0) { break } }
  }
  docker info *> $null 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Docker indisponible. Démarre Docker Desktop puis relance." }
}
Ok "Docker actif."

# --- 2. Réglages de l'atelier (staging par défaut) ------------------------
$appEnv = if ($Dev) { "dev" } else { "staging" }
Set-EnvVar "APP_ENV" $appEnv
Set-EnvVar "AUTH_COOKIE_SECURE" "false"   # cookies OK sur http://localhost
Set-EnvVar "TUNNEL_CORTEX_URL" "ws://zolaos-cortex:8000/v1/tunnel/connect"
Ok "Atelier en mode '$appEnv' (login réel; -Dev pour l'auto-login)."

# --- 3. Override local : modèle d'embeddings (box + cortex) ---------------
$composeArgs = @("-f", "docker-compose.yml", "-f", "docker-compose.dev.yml")
if (Test-Path $BgeM3Path) {
  $mount = ($BgeM3Path -replace '\\', '/')
  @"
# Généré par scripts/dev_up.ps1 — NON versionné. Monte bge-m3 sur box ET cortex.
name: zolaos
services:
  app:
    volumes: [ "${mount}:/opt/bge-m3:ro" ]
    environment: { EMBEDDING_MODEL: /opt/bge-m3, HF_HUB_OFFLINE: "1" }
  cortex:
    volumes: [ "${mount}:/opt/bge-m3:ro" ]
    environment: { EMBEDDING_MODEL: /opt/bge-m3, HF_HUB_OFFLINE: "1" }
"@ | Set-Content -Path (Join-Path $root "docker-compose.local.yml") -Encoding UTF8
  $composeArgs += @("-f", "docker-compose.local.yml")
  Ok "Embeddings bge-m3 montés (RAG activé)."
} else {
  Warn "bge-m3 introuvable à $BgeM3Path — RAG sémantique désactivé."
}

# --- 4. Lève box + cortex -------------------------------------------------
Info "Démarrage box (:$ApiPort) + cortex (:$CortexPort) + services…"
& docker compose @composeArgs up -d app cortex
if ($LASTEXITCODE -ne 0) { throw "Échec du démarrage de la stack." }

function Wait-Health($url, $name) {
  for ($i = 0; $i -lt 30; $i++) {
    try { $null = Invoke-WebRequest $url -TimeoutSec 2 -UseBasicParsing; Ok "$name prêt."; return } catch {}
    Start-Sleep 3
  }
  Warn "$name pas prêt — voir 'docker logs'."
}
Wait-Health "http://localhost:$ApiPort/health" "Box"
Wait-Health "http://localhost:$CortexPort/health" "Cortex"

# --- 5. Migrations --------------------------------------------------------
Info "Application des migrations…"
& docker compose @composeArgs exec -T app python -m alembic upgrade head 2>&1 | Select-Object -Last 1

# --- 6. Semence hybride + câblage du tunnel -------------------------------
Info "Semence (admin + cabinet + client + credential de box)…"
$seed = & docker compose @composeArgs exec -T app python scripts/dev_seed.py 2>$null
$boxTenant = ($seed | Select-String '^BOX_TENANT_ID=(.+)$').Matches.Groups[1].Value
$boxCred   = ($seed | Select-String '^BOX_CREDENTIAL=(.+)$').Matches.Groups[1].Value
if ($boxTenant -and $boxCred) {
  Set-EnvVar "ZOLAOS_BOX_TENANT_ID" $boxTenant
  Set-EnvVar "ZOLAOS_BOX_CREDENTIAL" $boxCred
  Ok "Semence OK. Recréation de la box pour activer le tunnel…"
  & docker compose @composeArgs up -d --force-recreate app | Out-Null
  Wait-Health "http://localhost:$ApiPort/health" "Box (tunnel)"
  Start-Sleep 3
  $connected = (docker logs zolaos-cortex --since 30s 2>&1 | Select-String "tunnel.box_connected").Count
  if ($connected -gt 0) { Ok "Tunnel box→cortex connecté." } else { Warn "Tunnel pas encore connecté — 'docker logs zolaos-cortex'." }
} else {
  Warn "Semence incomplète — tunnel non câblé."
}

# --- 7. Frontend (login réel) ---------------------------------------------
$feBusy = $false
try { $null = Invoke-WebRequest "http://localhost:$FrontendPort" -TimeoutSec 2 -UseBasicParsing; $feBusy = $true } catch {}
if ($feBusy) { Ok "Frontend déjà en marche." }
else {
  Info "Démarrage du frontend (nouvelle fenêtre)…"
  $feCmd = "`$env:NEXT_PUBLIC_API_BASE='http://localhost:$ApiPort'; npm run dev"
  Start-Process pwsh -WorkingDirectory (Join-Path $root "frontend") -ArgumentList '-NoExit', '-Command', $feCmd
  Ok "Frontend en compilation → http://localhost:$FrontendPort"
}

# --- 8. LLM ---------------------------------------------------------------
try { $null = Invoke-WebRequest "http://localhost:11435/v1/models" -TimeoutSec 2 -UseBasicParsing; Ok "LLM détecté (:11435)." }
catch { Warn "LLM absent (:11435) — l'assistant et les audits ne répondront pas. Lancer Ollama (cf. lanceur de démarrage de session, ou `ollama serve` sur 11435)." }

# --- 9. Récapitulatif -----------------------------------------------------
Write-Host ""
Write-Host "──────────────────────────────────────────────" -ForegroundColor DarkGray
Ok "Atelier ZolaOS hybride prêt (mode $appEnv)."
Write-Host "  Box (client)   : http://localhost:$ApiPort" -ForegroundColor White
Write-Host "  Cortex (cabinet): http://localhost:$CortexPort" -ForegroundColor White
Write-Host "  Frontend       : http://localhost:$FrontendPort" -ForegroundColor White
if (-not $Dev) {
  Write-Host "  Login          : admin@polaris.cg / Dev-Local-2026!  (staging = login réel)" -ForegroundColor White
}
Write-Host "──────────────────────────────────────────────" -ForegroundColor DarkGray
