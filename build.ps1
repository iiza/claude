# Compila Dictado para Windows (no requiere permisos de administrador).
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Resultado: dist\Dictado\Dictado.exe (y dist\Dictado-Setup.exe si Inno Setup está instalado)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller==6.22.3

New-Item -ItemType Directory -Force build | Out-Null
python -c "from dictado.icons import save_ico; save_ico('build/dictado.ico')"
if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el icono" }

python -m PyInstaller --noconfirm --clean --windowed `
    --name Dictado `
    --icon build/dictado.ico `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all onnxruntime `
    --collect-all sounddevice `
    --collect-all _sounddevice_data `
    --hidden-import pynput.keyboard._win32 `
    --hidden-import pynput.mouse._win32 `
    --hidden-import pystray._win32 `
    dictado_main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }

$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($p in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                     "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}
if ($iscc) {
    $version = python -c "import dictado; print(dictado.__version__)"
    & $iscc "/DAppVersion=$version" installer\dictado.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló" }
} else {
    Write-Host "Inno Setup no encontrado: se omite el instalador (dist\Dictado sigue siendo usable tal cual)."
}
