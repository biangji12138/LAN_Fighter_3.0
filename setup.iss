; LAN Fighter 3.0  Inno Setup 脚本
; 用法：先运行 build_exe_windows.bat，再用 Inno Setup Compiler 打开此文件 Compile

#define MyAppName "LAN Fighter"
#define MyAppVersion "3.0"
#define MyAppPublisher "LAN Fighter Team"
#define MyAppExeName "LANFighter.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableDirPage=no
OutputDir=installer
OutputBaseFilename=LANFighter_Setup_v3.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式:"

[Files]
Source: "dist\LANFighter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "正在安装 VC++ 运行库..."; Flags: postinstall
Filename: "{app}\{#MyAppExeName}"; Description: "启动 LAN Fighter"; Flags: nowait postinstall skipifsilent

[Code]
var
  VcRedistNeeded: Boolean;

function VcRedistInstalled: Boolean;
begin
  Result := RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64');
end;

function InitializeSetup: Boolean;
begin
  VcRedistNeeded := not VcRedistInstalled;
  Result := True;
end;