# Verification matrix and Windows acceptance checklist

| Test | Current evidence | How to run / expectation |
|---|---|---|
| ShareX source storage paths | SOURCE-INSPECTED | v22.3.0 PersonalPathManager/AppPaths/Program/FileTypeRegistration |
| Official 22.3.0 release SHA-256 | SOURCE-INSPECTED (published, not downloaded locally) | Expected vendor asset hash in release body |
| Shared action interfaces | SOURCE-INSPECTED | Exact pinned action.yml versions + local script on Actions |
| Builder Python syntax | STATIC-VALIDATED (authoring environment) | `python -m compileall -q scripts` |
| Workflow YAML parse | STATIC-VALIDATED (authoring environment) | YAML structure check; not a GitHub Actions run |
| Real root launcher compilation | NOT YET VERIFIED | Windows GitHub Actions `dotnet publish` NativeAOT |
| Controlled empty-directory/crash test | NOT YET VERIFIED | CI `ShareXPortable.exe --self-test` |
| Official asset download and verification | NOT YET VERIFIED | CI downloader |
| Independently validated ZIP | NOT YET VERIFIED | CI `validate_and_zip.py` |
| Shared custom NSIS installer produced | NOT YET VERIFIED | CI uses exact v1.0.0 SHA |
| Installer real install/reinstall upgrade | NOT YET VERIFIED | Manual Windows test (do not infer from `7z t`) |
| Shared Publisher dry-run/live release | NOT YET VERIFIED | GitHub Actions output after validations |
| ShareX GUI/tray/captures | NOT YET VERIFIED | Windows desktop test |
| Shell/host trace containment | NOT YET VERIFIED | ProcMon + registry/startup snapshots |
| Context-menu, toast notification, Explorer integration | NOT YET VERIFIED | Manual desktop inspection; do not enable in production first |
| Source-built direct native app | NOT APPLICABLE | PORTABLEAPPS mode intentionally uses official upstream binary |
| Native auto startup manager | NOT APPLICABLE | Not requested; startup intentionally not created |

## Manual Windows acceptance (use a disposable VM and dummy data)

1. **First launch**: unpack ZIP to a path with spaces and Unicode letters; double-click root `ShareXPortable.exe`; verify ShareX loads and a blank `App/ShareX/ShareX` profile is created. Confirm tray icon is active.
2. **Captures**: screenshot region, full monitor, editor, annotation, OCR, GIF/video recording. Exit via tray and verify screenshots/history/logs under `Data/ShareX` and not Documents/ShareX.
3. **CLI**: run root EXE with `-silent`; test `-RectangleRegion` on a desktop; test file-path forwarding only with a harmless local file and with uploads disabled. `-multi` must be rejected.
4. **Persistence**: change hotkeys and uploader dummy settings; exit/relaunch; verify data. Make nested **empty** directories inside active `App/ShareX/ShareX`; exit; verify exact paths inside `Data/ShareX`.
5. **Installed coexistence**: with the installed ShareX running, launch portable and expect a safe refusal. Exit installed ShareX, then launch portable. After exiting, installed app settings, Desktop/Documents folder and shortcuts must be untouched.
6. **Host diff**: compare before/during/after `%APPDATA%`, `%LOCALAPPDATA%`, LocalLow, `%PROGRAMDATA%`, Startup, Start Menu, HKCU file associations, Explorer send-to, toast history and taskbar records. Do not remove unrelated artifacts. If owned unexplained writes exist, audit them before deployment.
7. **Crash recovery**: after modifying a controlled dummy file, simulate killing the root launcher (not the app) and normally exit ShareX. Relaunch root launcher and exit again; journal must clear and no data disappear. Test dual-profile collision and ensure both copies remain untouched. Do not test on personal profiles.
8. **Upgrade**: exit via tray and verify profile idle; back up Data; reinstall using the shared installer. Confirm previous screenshots/settings retained and no stale application binaries remain. Repeat on a version upgrade if both stable versions work.
9. **Rollback**: restore older app binaries with older matching Data backup; test screenshots and history. Never assume schema rollback compatibility.
10. **Relocation**: after clean exit, move entire tree to another folder/drive, launch, repeat. On FAT/exFAT/NTFS, verify directory renames and read/write permissions as appropriate. Do not move live profile.
11. **Shell integrations/notifications**: compare installed ShareX shortcuts and registrations, ensure no newly created automatic entries. For any user-enabled SendTo/Startup/context-menu integration, document that it is a deliberate host change and cannot be automatically recovered here. Toast click-to-open remains unverified until tested.
12. **Installer**: test actual click-through install/reinstall from `.paf.exe` on a disposable VM. Do not infer successful install from a passing installer archive checksum/7z test.

The controlled C# self-test does **not** launch ShareX's actual interactive executable and does **not** validate Windows API behavior beyond synthetic filesystem operations.
