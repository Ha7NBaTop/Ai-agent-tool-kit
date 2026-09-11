# Run from any directory; pass arguments unchanged. No global settings altered.
$ErrorActionPreference = 'Stop'
$agentPreviousBytecode = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location -LiteralPath $PSScriptRoot
try {
    & python -B -m controlled_agent.cli @args
    $agentExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONDONTWRITEBYTECODE = $agentPreviousBytecode
}
exit $agentExit
