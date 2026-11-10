$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$folder = (Resolve-Path 'work/stage/QBZDownloaderPortable/App/AppInfo').Path
$original = [System.Drawing.Image]::FromFile((Join-Path $folder 'appicon-source.png'))
try {
    foreach ($dimension in @(16,32)) {
        $bitmap = [System.Drawing.Bitmap]::new($dimension,$dimension)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.DrawImage($original,0,0,$dimension,$dimension)
            } finally { $graphics.Dispose() }
            $bitmap.Save((Join-Path $folder "appicon_$dimension.png"),[System.Drawing.Imaging.ImageFormat]::Png)
        } finally { $bitmap.Dispose() }
    }
} finally { $original.Dispose() }
Remove-Item -LiteralPath (Join-Path $folder 'appicon-source.png') -Force
