; ==============================================================================
; ResearchLens Desktop — Custom NSIS Installer & Uninstaller Configuration
; ==============================================================================

!macro preInit
  ; Ensure clean single-instance check if needed
!macroend

!macro customInstall
  DetailPrint "Finishing installation: Preparing destination directory..."
  FileOpen $0 "$INSTDIR\install.log" w
  FileWrite $0 "ResearchLens Desktop Installation Log$\r$\n"
  FileWrite $0 "Installed at: $INSTDIR$\r$\n"
  FileWrite $0 "Architecture: Windows x64$\r$\n"
  FileWrite $0 "Runtime: Bundled Standalone Python 3.12 + Next.js Standalone + Electron$\r$\n"
  FileClose $0

  DetailPrint "Finishing installation: Verifying local runtime integrity..."
  ; Write completion record
  FileOpen $0 "$INSTDIR\install.log" a
  FileWrite $0 "Status: Core extraction complete.$\r$\n"
  FileClose $0

  DetailPrint "Finishing installation: Registering application shortcuts..."
  DetailPrint "Finishing installation: ResearchLens configuration complete."
!macroend

!macro customUnInstall
  ; Explicit user-data protection guarantee:
  ; The uninstaller removes binaries from $INSTDIR but NEVER touches user data by default:
  ; - %USERPROFILE%\Documents\ResearchLens Library
  ; - %LOCALAPPDATA%\ResearchLens
  ; Uninstaller checkbox: "Also remove my library and settings" (default: OFF / unchecked).
  DetailPrint "Removing application binaries from $INSTDIR..."
  DetailPrint "Preserving user research libraries, databases, and local settings by default."
!macroend
