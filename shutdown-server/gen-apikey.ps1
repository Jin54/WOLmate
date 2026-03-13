param([string]$InstallDir)

$key = -join ((48..57)+(65..70) | Get-Random -Count 16 | ForEach-Object {[char]$_})
@{api_key=$key} | ConvertTo-Json | Set-Content -Path (Join-Path $InstallDir "wolmate-config.json") -Encoding UTF8
