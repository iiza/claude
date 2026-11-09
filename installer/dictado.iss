; Instalador por usuario: NO pide permisos de administrador.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7B0B6B52-6C1E-4D7B-9C55-1E3A0D8F4A21}
AppName=Dictado
AppVersion={#AppVersion}
AppPublisher=Dictado
DefaultDirName={localappdata}\Programs\Dictado
DefaultGroupName=Dictado
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Dictado-Setup
SetupIconFile=..\build\dictado.ico
UninstallDisplayIcon={app}\Dictado.exe
UninstallDisplayName=Dictado
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=force

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar Dictado automáticamente al entrar en Windows"; GroupDescription: "Opciones:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Dictado\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{userprograms}\Dictado"; Filename: "{app}\Dictado.exe"
Name: "{userdesktop}\Dictado"; Filename: "{app}\Dictado.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Dictado"; ValueData: """{app}\Dictado.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Dictado.exe"; Description: "{cm:LaunchProgram,Dictado}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Dictado.exe"; Flags: runhidden; RunOnceId: "KillDictado"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Dictado');
end;
