param(
    [ValidateRange(1, 1440)]
    [int]$IntervalMinutes = 10,
    [string]$DailyAt = "09:00"
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Create the project virtual environment first: $venvPython was not found."
}
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Copy .env.example to .env and set SCHEDULED_TOPIC before installing scheduled tasks."
}
$topicLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*SCHEDULED_TOPIC\s*=\s*\S+' } | Select-Object -First 1
if (-not $topicLine) {
    throw "Set a non-empty SCHEDULED_TOPIC in .env before installing scheduled tasks."
}
try {
    $dailyTime = [TimeSpan]::Parse($DailyAt)
} catch {
    throw "DailyAt must be a time such as 09:00 or 18:30."
}
if ($dailyTime.Ticks -lt 0 -or $dailyTime -ge (New-TimeSpan -Days 1)) {
    throw "DailyAt must be between 00:00 and 23:59."
}

$processAction = New-ScheduledTaskAction `
    -Execute $venvPython `
    -Argument "-m story_video_automation.cli process-pending" `
    -WorkingDirectory $projectRoot
$processTrigger = New-ScheduledTaskTrigger -Daily -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 1)
$processSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$botSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName "AI Automation Process Pending Jobs" `
    -Action $processAction `
    -Trigger $processTrigger `
    -Settings $processSettings `
    -Principal $principal `
    -Description "Poll asynchronous video jobs, finish previews, and send approval notifications." `
    -Force | Out-Null

$dailyStart = [DateTime]::Today.Add($dailyTime)
$dailyAction = New-ScheduledTaskAction `
    -Execute $venvPython `
    -Argument "-m story_video_automation.cli scheduled-run" `
    -WorkingDirectory $projectRoot
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $dailyStart
Register-ScheduledTask `
    -TaskName "AI Automation Create Scheduled Video" `
    -Action $dailyAction `
    -Trigger $dailyTrigger `
    -Settings $processSettings `
    -Principal $principal `
    -Description "Create a story video job from SCHEDULED_TOPIC; approval is still required." `
    -Force | Out-Null

$botAction = New-ScheduledTaskAction `
    -Execute $venvPython `
    -Argument "-m story_video_automation.cli telegram-bot" `
    -WorkingDirectory $projectRoot
$botTrigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
Register-ScheduledTask `
    -TaskName "AI Automation Telegram Approval Bot" `
    -Action $botAction `
    -Trigger $botTrigger `
    -Settings $botSettings `
    -Principal $principal `
    -Description "Receive Telegram approval decisions and upload only approved videos." `
    -Force | Out-Null

Write-Host "Scheduled workflow polling every $IntervalMinutes minute(s)."
Write-Host "Daily story job scheduled for $DailyAt."
Write-Host "The Telegram bot starts when this Windows user signs in."
