param(
    [int]$Port = 7872,
    [switch]$Check,
    [switch]$Detach
)

# ModelBus 控制台启动器：默认前台（要看日志），-Detach 才隐藏窗口并把输出落到 .work/。
$ErrorActionPreference = "Stop"
$py = (Get-Command python -ErrorAction Stop).Source
$entry = Join-Path $PSScriptRoot "server.py"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ($Check) {
    & $py $entry --check
    exit $LASTEXITCODE
}

if ($Detach) {
    $work = Join-Path $root ".work"
    if (-not (Test-Path -LiteralPath $work)) {
        New-Item -ItemType Directory -Path $work -Force | Out-Null
    }
    $out = Join-Path $work "console.stdout.log"
    $err = Join-Path $work "console.stderr.log"
    Start-Process -FilePath $py -ArgumentList @($entry, "--port", "$Port") `
        -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    Write-Output "console detached on 127.0.0.1:$Port (stdout: $out, access-log stderr: $err)"
    exit 0
}

& $py $entry --port $Port
exit $LASTEXITCODE
