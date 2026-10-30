; Inno Setup script for VoxScribe.
; Build the app first (PyInstaller -> dist\VoxScribe\), then compile
; this with ISCC.exe to produce a single setup.exe installer in installer_output\.

#define MyAppName "VoxScribe"
#define MyAppVersion "1.8.3"
#define MyAppExeName "VoxScribe.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=VoxScribe
AppPublisherURL=https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=VoxScribe
VersionInfoDescription=VoxScribe Setup
VersionInfoProductName=VoxScribe
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=VoxScribe-Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=app\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
; No admin rights required for a per-user install.
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\VoxScribe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
