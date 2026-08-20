; Inno Setup script for SRE Book Builder.
;
; Build from the repository root:
;     py packaging/vendor_tesseract.py
;     py -m PyInstaller packaging/srebook.spec --noconfirm
;     "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
;
; Installs per-user by default so archive staff do not need an administrator,
; which is the usual obstacle to getting a tool onto a library workstation.
; Machine-wide install is still offered for IT to deploy centrally.

#define AppName "SRE Book Builder"
#define AppVersion "0.1.0"
#define AppPublisher "Upper Snake River Valley Historical Society"
#define AppExe "SREBookBuilder.exe"

[Setup]
AppId={{8B3F2C41-9E7A-4D62-B5A1-7C4E0F1D2A93}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=SREBookBuilder-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExe}
; Per-user unless the operator chooses otherwise: no administrator needed.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; The frozen application.
Source: "..\dist\SREBookBuilder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Tesseract, laid down beside the exe rather than routed through PyInstaller,
; which would duplicate 130 MB of its DLLs. srebook.core.ocr looks here first.
Source: "..\srebook\vendor\tesseract\*"; DestDir: "{app}\vendor\tesseract"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The OCR cache the app writes next to each issue is not ours to remove, but
; anything we created under {app} is.
Type: filesandordirs; Name: "{app}\vendor"
