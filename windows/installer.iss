; Inno Setup script: turns the PyInstaller folder into TranslatorSetup.exe.
; No admin rights needed: installs for the current user only.

#define AppName "Translator"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F5C2A71-4B7E-4C1D-9E0A-6C1B2D3E4F50}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Translator
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=TranslatorSetup
SetupIconFile=translator.ico
UninstallDisplayIcon={app}\Translator.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Open Translator in the tray when Windows starts"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\Translator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Translator.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Translator.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Translator"; ValueData: """{app}\Translator.exe"" --minimized"; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Translator.exe"; Description: "Open Translator now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM Translator.exe /F"; Flags: runhidden; RunOnceId: "KillTranslator"
