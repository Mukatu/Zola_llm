#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Démarre la stack de dev ZolaOS d'un coup : Docker (app + embeddings bge-m3),
  frontend pré-authentifié, token de dev, et rappel Ollama pour les fonctions IA.

.DESCRIPTION
  - Vérifie Docker (le démarre si besoin) puis lève la stack avec le modèle
    d'embeddings local monté (RAG opérationnel).
  - Forge un JWT de dev (scope commons:curate) pour un utilisateur existant.
  - Lance le frontend Next.js pré-authentifié (nouvelle fenêtre), sauf s'il tourne déjà.
  - Signale si le LLM (Ollama, port 11435) est absent — nécessaire pour Assistant,
    Traduction, Brief BI et Rédaction de contrat.

  Le LLM n'est PAS démarré par ce script (serveur bloquant, modèle volumineux,
  choix machine) : les commandes exactes sont rappelées à la fin.

.PARAMETER BgeM3Path
  Dossier hôte du modèle bge-m3 (monté en lecture seule dans le conteneur).
  Défaut : C:\Users\duqat\bge-m3 (copie téléchargée). Si absent, la stack démarre
  sans RAG sémantique (les fonctions déterministes restent OK).

.PARAMETER UserEmail
  E-mail de l'utilisateur pour lequel forger le token (défaut : premier utilisateur).

.EXAMPLE
  pwsh scripts/dev_up.ps1
#>

[CmdletBinding()]
param(
  [string]$BgeM3Path = "C:\Users\duqat\bge-m3",
  [string]$UserEmail = "",
  [int]$ApiPort = 8000,
  [int]$FrontendPort = 3000,
  [int]$TokenHours = 12
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($m) { Write-Host "▶ $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "⚠ $m" -ForegroundColor Yellow }

# --- 1. Docker en marche ? ------------------------------------------------
Info "Vérification de Docker…"
docker info *> $null 2>&1
if ($LASTEXITCODE -ne 0) {
  $dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dd) {
    Warn "Docker arrêté — démarrage de Docker Desktop…"
    Start-Process $dd
    for ($i = 0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 3
      docker info *> $null 2>&1
      if ($LASTEXITCODE -eq 0) { break }
    }
  }
  docker info *> $null 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Docker indisponible. Démarre Docker Desktop puis relance." }
}
Ok "Docker actif."

# --- 2. Override local : monte le modèle d'embeddings ---------------------
$composeArgs = @("-f", "docker-compose.yml", "-f", "docker-compose.dev.yml")
if (Test-Path $BgeM3Path) {
  $localYml = Join-Path $root "docker-compose.local.yml"
  $mount = ($BgeM3Path -replace '\\', '/')
  @"
# Généré par scripts/dev_up.ps1 — NON versionné. Monte le modèle d'embeddings
# bge-m3 local et pointe l'app dessus (RAG hors-ligne, aucune dépendance réseau).
name: zolaos
services:
  app:
    volumes:
      - ${mount}:/opt/bge-m3:ro
    environment:
      EMBEDDING_MODEL: /opt/bge-m3
      HF_HUB_OFFLINE: "1"
"@ | Set-Content -Path $localYml -Encoding UTF8
  $composeArgs += @("-f", "docker-compose.local.yml")
  Ok "Modèle d'embeddings monté depuis $BgeM3Path (RAG activé)."
} else {
  Warn "bge-m3 introuvable à $BgeM3Path — démarrage SANS RAG sémantique (déterministe OK)."
}

# --- 3. Lève la stack -----------------------------------------------------
Info "Démarrage des conteneurs (app + postgres + redis + minio)…"
& docker compose @composeArgs up -d app
if ($LASTEXITCODE -ne 0) { throw "Échec du démarrage de la stack." }

Info "Attente de la santé de l'app…"
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
  $s = (docker inspect -f '{{.State.Health.Status}}' zolaos-app 2>$null)
  if ($s -eq "healthy") { $healthy = $true; break }
  Start-Sleep -Seconds 3
}
if (-not $healthy) { Warn "L'app n'est pas 'healthy' — vérifie 'docker logs zolaos-app'." }
else { Ok "Backend prêt sur http://localhost:$ApiPort" }

# --- 4. Token de dev ------------------------------------------------------
Info "Forge d'un token de dev (scope commons:curate, ${TokenHours} h)…"
$uidSql = if ($UserEmail) { "select id from core.users where email='$UserEmail' limit 1;" }
          else { "select id from core.users limit 1;" }
$uid = (docker exec zolaos-postgres psql -U postgres -d zolaos -tA -c $uidSql 2>$null).Trim()
$token = ""
if ($uid) {
  $py = "import os,time; from zolaos.core.settings import get_settings; from zolaos.core.security import create_access_token; s=get_settings(); print(create_access_token(os.environ['ZO_UID'], settings=s, extra_claims={'scopes':['commons:curate'],'exp':int(time.time())+${TokenHours}*3600}))"
  $token = (docker exec -e ZO_UID=$uid zolaos-app python -c $py 2>$null).Trim()
}
if ($token) { Ok "Token forgé (utilisateur $uid)." } else { Warn "Impossible de forger le token (aucun utilisateur ?)." }

# --- 5. Frontend ----------------------------------------------------------
$feBusy = $false
try { $null = Invoke-WebRequest "http://localhost:$FrontendPort" -TimeoutSec 2 -UseBasicParsing; $feBusy = $true } catch {}
if ($feBusy) {
  Ok "Frontend déjà en marche sur http://localhost:$FrontendPort"
} else {
  Info "Démarrage du frontend (nouvelle fenêtre)…"
  $feDir = Join-Path $root "frontend"
  $feCmd = "`$env:NEXT_PUBLIC_API_BASE='http://localhost:$ApiPort'; `$env:NEXT_PUBLIC_API_TOKEN='$token'; npm run dev"
  Start-Process pwsh -WorkingDirectory $feDir -ArgumentList '-NoExit', '-Command', $feCmd
  Ok "Frontend en cours de compilation → http://localhost:$FrontendPort (quelques secondes)."
}

# --- 6. LLM (Ollama) ------------------------------------------------------
$llmUp = $false
try { $null = Invoke-WebRequest "http://localhost:11435/v1/models" -TimeoutSec 2 -UseBasicParsing; $llmUp = $true } catch {}
Write-Host ""
if ($llmUp) {
  Ok "LLM détecté sur le port 11435 — fonctions IA disponibles."
} else {
  Warn "LLM absent (port 11435) : Assistant / Traduction / Brief BI / Rédaction indisponibles."
  Write-Host "  Pour l'activer, dans un terminal SÉPARÉ :" -ForegroundColor Yellow
  Write-Host "    ollama pull llama3:8b" -ForegroundColor Gray
  Write-Host "    ollama cp llama3:8b llama3-8b" -ForegroundColor Gray
  Write-Host "    `$env:OLLAMA_HOST='0.0.0.0:11435'; ollama serve" -ForegroundColor Gray
  Write-Host "  (CPU sans GPU : ~20-50 s par réponse, fonctionnel pour une démo.)" -ForegroundColor DarkGray
}

# --- 7. Récapitulatif -----------------------------------------------------
Write-Host ""
Write-Host "──────────────────────────────────────────────" -ForegroundColor DarkGray
Ok "Stack ZolaOS prête."
Write-Host "  Backend  : http://localhost:$ApiPort" -ForegroundColor White
Write-Host "  Frontend : http://localhost:$FrontendPort" -ForegroundColor White
if ($token) {
  Write-Host "  Token 12h (déjà injecté dans le frontend). Pour la console navigateur :" -ForegroundColor White
  Write-Host "    localStorage.setItem('zo_token','$token'); location.reload();" -ForegroundColor DarkGray
}
Write-Host "──────────────────────────────────────────────" -ForegroundColor DarkGray
