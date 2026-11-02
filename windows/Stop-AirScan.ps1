$ErrorActionPreference = 'Stop'
$scanProjectRoot = Split-Path -Parent $PSScriptRoot
$scanPidFile = Join-Path $scanProjectRoot '.runtime\bridge.pid'
if (-not (Test-Path -LiteralPath $scanPidFile)) { return }
$scanBridgeId = [int](Get-Content -LiteralPath $scanPidFile)
$scanCommand = Get-CimInstance Win32_Process -Filter "ProcessId=$scanBridgeId" -ErrorAction SilentlyContinue
$scanExpectedScript = Join-Path $scanProjectRoot 'airscan_bridge.py'
if ($scanCommand -and $scanCommand.CommandLine -like ('*' + $scanExpectedScript + '*')) {
    Stop-Process -Id $scanBridgeId
    Write-Output 'Stopped this project AirScan bridge.'
} elseif ($scanCommand) {
    throw 'PID belongs to another process; it was not stopped.'
}
