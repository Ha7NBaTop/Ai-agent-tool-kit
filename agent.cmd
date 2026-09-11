@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0"
python -B -m controlled_agent.cli %*
set "agentExit=%errorlevel%"
popd
exit /b %agentExit%
