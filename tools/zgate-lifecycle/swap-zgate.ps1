#requires -Version 5.1
# 兼容入口：旧 swap-zgate.ps1 用 Start-Process 拉起，进程落在会话树里会被回收。
# 现在统一转交 deploy-zgate.ps1（-SkipBuild 时直接用已就绪的候选产物）。
# 若传 -NewExe，则先把它复制成 zgate.candidate.exe 再换版。
[CmdletBinding()]
param([string]$NewExe = '', [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$pathsFile = Join-Path $here 'zgate-paths.ps1'
if (Test-Path $pathsFile) { . $pathsFile }
if ($NewExe) {
    if (-not $ZgateHome) { throw '未找到 ZgateHome：先跑 install-lifecycle.ps1' }
    if (-not (Test-Path $NewExe)) { throw ('找不到 {0}' -f $NewExe) }
    Copy-Item -LiteralPath $NewExe -Destination (Join-Path $ZgateHome 'zgate.candidate.exe') -Force
}
$argList = @()
if ($SkipBuild -or $NewExe) { $argList += '-SkipBuild' }
& (Join-Path $here 'deploy-zgate.ps1') @argList
exit $LASTEXITCODE
