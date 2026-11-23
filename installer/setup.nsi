Unicode True

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "WordFunc.nsh"
!include "WinVer.nsh"
!include "x64.nsh"

!define PRODUCT "Starlit DeskDownloader"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\StarlitDeskDownloader"
!define CHROME_KEY "Software\Google\Chrome\NativeMessagingHosts\com.starlit.deskdownloader"
!define HOST_MANIFEST "com.starlit.deskdownloader.json"
!define SHORTCUT "$SMPROGRAMS\Hızlı İndir.lnk"

Name "${PRODUCT}"
OutFile "${SETUP_FILE}"
InstallDir "$LOCALAPPDATA\Programs\${PRODUCT}"
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
CRCCheck force
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=1055 "ProductName" "${PRODUCT}"
VIAddVersionKey /LANG=1055 "FileDescription" "Hızlı İndir Windows Kurulumu"
VIAddVersionKey /LANG=1055 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1055 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1055 "LegalCopyright" "Starlit DeskDownloader contributors"

Var AppDir
Var PreviousAppDir
Var InstallRoot
Var IsUpgrade

!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$AppDir\HizliIndir.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Hızlı İndir’i aç"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Turkish"

!include "${PAYLOAD_INCLUDE}"

; Attempt a write handle without changing the file. Windows rejects it while
; the executable image is mapped. Never terminate the user's active download.
!macro RequireClosed Directory
  !insertmacro CheckExecutable "${Directory}\HizliIndir.exe"
  !insertmacro CheckExecutable "${Directory}\HizliIndirBrowserHost.exe"
!macroend

!macro CheckExecutable FilePath
  ${If} ${FileExists} "${FilePath}"
    System::Call 'kernel32::CreateFileW(w "${FilePath}", i 0x40000000, i 7, p 0, i 3, i 0x80, p 0) p.r0'
    ${If} $0 == -1
      MessageBox MB_OK|MB_ICONEXCLAMATION "Hızlı İndir çalışıyor veya dosyaya erişilemiyor. Bildirim alanındaki Hızlı İndir simgesinden Çıkış’ı seçip tekrar dene." /SD IDOK
      SetErrorLevel 5
      Abort
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
  ${EndIf}
!macroend

; Unlike the NSIS GetFullPathName command, the Win32 API also resolves a new directory.
!macro NormalizePath Variable
  System::Call 'kernel32::GetFullPathNameW(w "${Variable}", i ${NSIS_MAX_STRLEN}, w .r1, p 0) i.r0'
  ${If} $0 == 0
  ${OrIf} $0 >= ${NSIS_MAX_STRLEN}
    MessageBox MB_OK|MB_ICONSTOP "Kurulum klasörünün yolu geçersiz." /SD IDOK
    SetErrorLevel 4
    Abort
  ${EndIf}
  StrCpy ${Variable} $1
!macroend

Function .onInit
  SetShellVarContext current
  ${IfNot} ${RunningX64}
  ${OrIfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "Bu kurulum 64 bit Windows 10 veya 11 gerektirir." /SD IDOK
    SetErrorLevel 4
    Abort
  ${EndIf}

  !insertmacro NormalizePath $INSTDIR
  StrCpy $AppDir "$INSTDIR\app-${APP_VERSION}"
  ReadRegStr $PreviousAppDir HKCU "${UNINSTALL_KEY}" "ApplicationPath"
  ${If} $PreviousAppDir != ""
    !insertmacro NormalizePath $PreviousAppDir
    ${GetParent} "$PreviousAppDir" $0
    ${If} $0 != $INSTDIR
      MessageBox MB_OK|MB_ICONSTOP "Hızlı İndir başka bir klasörde kurulu. Önce o kurulumu kaldır." /SD IDOK
      SetErrorLevel 4
      Abort
    ${EndIf}
    ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "DisplayVersion"
    ${VersionCompare} "$0" "${APP_VERSION}" $1
    ${If} $1 == 1
      MessageBox MB_OK|MB_ICONEXCLAMATION "Hızlı İndir’in daha yeni bir sürümü zaten kurulu." /SD IDOK
      SetErrorLevel 4
      Abort
    ${EndIf}
  ${EndIf}
  ${If} $PreviousAppDir != $AppDir
  ${AndIf} ${FileExists} "$AppDir\*.*"
    MessageBox MB_OK|MB_ICONSTOP "Kurulum klasöründe başka dosyalar var. Bu klasöre yazılmadı." /SD IDOK
    SetErrorLevel 4
    Abort
  ${EndIf}
FunctionEnd

Section "Hızlı İndir"
  ${If} $PreviousAppDir != ""
    !insertmacro RequireClosed "$PreviousAppDir"
  ${EndIf}
  ClearErrors
  !insertmacro InstallPayload
  SetOutPath "$AppDir"
  WriteUninstaller "$AppDir\Uninstall.exe"
  IfErrors payload_failed

  CreateShortcut "${SHORTCUT}" "$AppDir\HizliIndir.exe"
  WriteRegStr HKCU "${CHROME_KEY}" "" "$AppDir\${HOST_MANIFEST}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Hızlı İndir (Starlit DeskDownloader)"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${PRODUCT}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "ApplicationPath" "$AppDir"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$AppDir\HizliIndir.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$AppDir\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$AppDir\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" ${PAYLOAD_KIB}
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  IfErrors install_failed

  ${If} $PreviousAppDir != ""
  ${AndIf} $PreviousAppDir != $AppDir
  ${AndIf} ${FileExists} "$PreviousAppDir\Uninstall.exe"
    ClearErrors
    ExecWait '"$PreviousAppDir\Uninstall.exe" /S /UPGRADE _?=$PreviousAppDir' $0
    ${IfNot} ${Errors}
    ${AndIf} $0 == 0
      Delete "$PreviousAppDir\Uninstall.exe"
      RMDir "$PreviousAppDir"
    ${Else}
      DetailPrint "Önceki sürümün bütün dosyaları kaldırılamadı: $PreviousAppDir"
    ${EndIf}
  ${EndIf}
  Goto install_done

  payload_failed:
    ${If} $PreviousAppDir != $AppDir
      SetOutPath "$TEMP"
      !insertmacro RemoveFiles "$AppDir"
      !insertmacro RemoveEmptyDirs "$AppDir"
      Delete "$AppDir\Uninstall.exe"
      RMDir "$AppDir"
    ${EndIf}
  install_failed:
    MessageBox MB_OK|MB_ICONSTOP "Kurulum tamamlanamadı. Disk alanını ve klasör izinlerini kontrol edip tekrar dene." /SD IDOK
    SetErrorLevel 6
    Abort
  install_done:
SectionEnd

Function un.onInit
  SetShellVarContext current
  !insertmacro NormalizePath $INSTDIR
  ${GetFileName} "$INSTDIR" $0
  ${If} $0 != "app-${APP_VERSION}"
    SetErrorLevel 4
    Abort
  ${EndIf}
  ${GetParent} "$INSTDIR" $InstallRoot
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} "$0" "/UPGRADE" $1
  StrCpy $IsUpgrade 0
  ${IfNot} ${Errors}
    StrCpy $IsUpgrade 1
  ${EndIf}
  !insertmacro RequireClosed "$INSTDIR"
FunctionEnd

Section "Uninstall"
  SetOutPath "$TEMP"
  ClearErrors
  !insertmacro RemoveFiles "$INSTDIR"
  ${If} ${Errors}
    MessageBox MB_OK|MB_ICONSTOP "Bazı dosyalara erişilemedi. Hızlı İndir’i kapatıp kaldırmayı tekrar dene." /SD IDOK
    SetErrorLevel 6
    Abort
  ${EndIf}
  !insertmacro RemoveEmptyDirs "$INSTDIR"

  ${If} $IsUpgrade == 0
    ReadRegStr $0 HKCU "${CHROME_KEY}" ""
    ${If} $0 == "$INSTDIR\${HOST_MANIFEST}"
      DeleteRegValue HKCU "${CHROME_KEY}" ""
      DeleteRegKey /ifempty HKCU "${CHROME_KEY}"
    ${EndIf}
    ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "ApplicationPath"
    ${If} $0 == $INSTDIR
      Delete "${SHORTCUT}"
      DeleteRegKey HKCU "${UNINSTALL_KEY}"
    ${EndIf}
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
    RMDir "$InstallRoot"
  ${EndIf}
SectionEnd
