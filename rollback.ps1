<#
.SYNOPSIS
    Rollback script for the Learning System.
    Disables all feature flags and preserves generated artifacts.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== JARVIS Learning System Rollback ===" -ForegroundColor Yellow

# 1. Disable feature flag
$flagFile = Join-Path $root "feature_flags\learning_system.yaml"
if (Test-Path $flagFile) {
    # Rewrite with everything disabled
    $content = @"

# Feature Flag: Learning System (ROLLBACK — all disabled)
enabled: false
shadow_mode: true
owner: admin
risk_level: standard
rollout_percentage: 0
flow_instrumentation: false
action_discovery: false
pattern_extractor: false
adapter_generator: false
adapter_generation: false
confidence_engine: false
intent_graph: false
critic_engine: false
causal_memory: false
human_loop: false
audit_log: false
auto_execute_threshold: 0.92
human_confirm_threshold: 0.70
destructive_threshold: 0.99
"@
    Set-Content -Path $flagFile -Value $content -Encoding UTF8
    Write-Host "[OK] Feature flags disabled." -ForegroundColor Green
} else {
    Write-Host "[SKIP] Feature flag file not found." -ForegroundColor Gray
}

# 2. Preserve generated artifacts (do NOT delete)
$artifactDirs = @(
    "data\action_templates",
    "data\audit",
    "data\approvals",
    "data\traces",
    "data\intent_logs"
)
foreach ($dir in $artifactDirs) {
    $full = Join-Path $root $dir
    if (Test-Path $full) {
        Write-Host "[PRESERVED] $dir (not deleted)" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "Rollback complete. Learning system is now DISABLED." -ForegroundColor Green
Write-Host "Generated artifacts are preserved for manual inspection." -ForegroundColor Gray
Write-Host "Restart JARVIS to apply changes." -ForegroundColor Yellow
