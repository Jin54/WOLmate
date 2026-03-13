param([string]$InstallDir)

$configPath = Join-Path $InstallDir "wolmate-config.json"
$config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json

$adapterInfo = ""
Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object {
    $ip = (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
    if ($ip) {
        $mac = $_.MacAddress -replace '-',':'
        $adapterInfo += "[$($_.Name)]`r`n  MAC: $mac`r`n  IP: $ip`r`n`r`n"
    }
}

$info = @"
WOLmate - PC Information
=======================

Install Path: $InstallDir

API Key: $($config.api_key)

-- Network Adapters --
${adapterInfo}WOL Port: 9
"@

# Save to desktop
$desktop = [Environment]::GetFolderPath("Desktop")
$savePath = Join-Path $desktop "WOLmate-Info.txt"
[IO.File]::WriteAllText($savePath, $info, [Text.Encoding]::UTF8)

# Output the API key for NSIS to read
Write-Output $config.api_key
Write-Output $savePath
