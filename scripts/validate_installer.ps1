param([Parameter(Mandatory)][string]$Path,[Parameter(Mandatory)][string]$ExpectedSha)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing installer: $Path" }
if ($Path -notmatch '\.paf\.exe$') { throw 'Not a PortableApps-style installer filename' }
$actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
if ($actual -ine $ExpectedSha) { throw "Installer checksum mismatch $actual != $ExpectedSha" }
$stream = [IO.File]::OpenRead($Path)
try {
    $reader = [IO.BinaryReader]::new($stream)
    if ($reader.ReadUInt16() -ne 0x5A4D) { throw 'Not a Windows MZ executable' }
    $stream.Position = 0x3c
    $offset = $reader.ReadInt32()
    if ($offset -lt 64 -or $offset -ge ($stream.Length - 4)) { throw 'Invalid Windows PE header offset' }
    $stream.Position = $offset
    if ($reader.ReadUInt32() -ne 0x4550) { throw 'Not a Windows PE executable' }
} finally { $stream.Dispose() }
$seven = @('C:\Program Files\7-Zip\7z.exe', 'C:\Program Files (x86)\7-Zip\7z.exe') | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $seven) {
    $command = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($command) { $seven = $command.Source }
}
if (-not $seven) { throw '7-Zip missing: cannot inspect installer archive' }
& $seven t -bso0 -bsp0 $Path | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'NSIS installer archive integrity failed' }
Write-Host "STATIC-VALIDATED installer $Path SHA256 $actual. NOT an interactive install test."
