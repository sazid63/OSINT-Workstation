; OSINT Toolkit Inno Setup script
; Standalone Windows installer for the PyInstaller one-folder build.
;
; Prerequisites: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Build: pyinstaller one-folder first (see packaging/README.md), then compile
; this .iss with Inno Setup.

#define AppName "OSINT Toolkit"
#define AppVersion "0.1.0"
#define AppPublisher "The OSINT Toolkit Authors"
#define AppURL "https://github.com/sazid63/OSINT-Toolkit"
#define AppExeName "OSINT-Toolkit.exe"
; Portable: paths are relative to this script's folder (packaging/).
; Build the PyInstaller one-folder output into ..\dist\OSINT-Toolkit first.
#define SourceFolder SourcePath + "..\dist\OSINT-Toolkit"
#define OutputDir SourcePath + "..\dist"
#define OutputBaseFilename "OSINT-Toolkit-Setup-" + AppVersion

[Setup]
AppId={{B5F0423A-9D59-4F3E-9CB5-2DF73AFC6158}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=""
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Leave user data intact under %LOCALAPPDATA%\OSINT Toolkit
; (no files deleted here intentionally)
