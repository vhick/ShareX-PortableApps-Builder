$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$app = Join-Path (Get-Location) 'work/staging/ShareXPortable/App/ShareX/ShareX.exe'
$info = Join-Path (Get-Location) 'work/staging/ShareXPortable/App/AppInfo'
if (!(Test-Path -LiteralPath $app -PathType Leaf)) { throw 'No verified ShareX.exe to extract official icon from' }
Add-Type -AssemblyName System.Drawing
$ico = [System.Drawing.Icon]::ExtractAssociatedIcon($app)
if ($null -eq $ico) { throw 'ShareX executable has no extractable official icon' }
try {
  $stream = [IO.File]::Create((Join-Path $info 'appicon.ico'))
  try { $ico.Save($stream) } finally { $stream.Dispose() }
  foreach ($size in @(16,32)) {
    $source = $ico.ToBitmap()
    try {
      $bitmap = [System.Drawing.Bitmap]::new($size, $size)
      try {
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
          $graphics.Clear([System.Drawing.Color]::Transparent)
          $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
          $graphics.DrawImage($source, 0, 0, $size, $size)
        } finally { $graphics.Dispose() }
        $bitmap.Save((Join-Path $info "appicon_$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
      } finally { $bitmap.Dispose() }
    } finally { $source.Dispose() }
  }
} finally { $ico.Dispose() }
Write-Host 'Extracted authentic upstream ShareX icon (ICO, PNG16, PNG32).'
