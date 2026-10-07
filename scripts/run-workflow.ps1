param(
    [ValidateSet("process-pending", "telegram-bot")]
    [string]$Command = "process-pending"
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction Stop
    $pythonExe = $pythonCommand.Source
}

Set-Location -LiteralPath $projectRoot
& $pythonExe -m story_video_automation.cli $Command
exit $LASTEXITCODE
