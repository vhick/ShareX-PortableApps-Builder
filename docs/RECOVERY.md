# Data recovery, relocation, upgrades and rollback

## Normal session

Resting: `ShareXPortable/Data/ShareX/` contains settings, history, screenshots and empty directories. `App/ShareX/ShareX/` does **not** exist.

While ShareX runs from the root launcher: profile is atomically moved from `Data/ShareX` into `App/ShareX/ShareX`. A recovery journal exists at `Data/TraceGuard/profile-active.txt`.

After ShareX exits from its **tray Exit** command and remains closed, the launcher atomically returns the folder to `Data/ShareX` and clears the journal. If children, app restarts or inaccessible running processes cannot be cleared, the launcher leaves data in place and logs a warning instead of risking overwrite. **Do not move or update a package until the journal is gone.**

## After Windows crash or terminated launcher

1. Do not install an update, replace `App`, launch `App/ShareX/ShareX.exe`, or delete anything yet.
2. Make a backup copy of the **entire** `ShareXPortable` directory, including `App`, `Data` and `Data/TraceGuard`.
3. Ensure no ShareX process is running (including an installed ShareX copy). Close it normally; avoid terminating an active recording.
4. If `App/ShareX/ShareX` exists, `Data/ShareX` is absent, and `Data/TraceGuard/profile-active.txt` exists, run **the root `ShareXPortable.exe`** again. The launcher recognizes its prior journal and reuses the working profile without overwriting files.
5. Exit ShareX through its tray menu. Verify `Data/ShareX` exists and `App/ShareX/ShareX` is absent. Inspect `Data/TraceGuard/launcher-errors.log` if it did not recover.
6. If **both** profile directories exist, or the journal is missing but the App profile exists, the launcher deliberately refuses. Restore from the backup or compare files manually; **never delete one copy without inspecting it**. Do not run the shared installer until resolved.

### Critical shared-installer caveat

Pinned NSIS v1.0.0 swaps out the old **entire App directory** during upgrade and preserves only `Data`. If the launcher crashed while the actual active profile was in `App/ShareX/ShareX`, running the installer first could discard those latest changes. **Recovery-before-upgrade is mandatory**; the installer currently cannot enforce the inactive-profile precondition. This is a design limitation to verify carefully, NOT a tested safe-crash-upgrade guarantee.

## Upgrade safely

1. Close ShareX using tray **Exit**. Confirm no ShareX background process/recording remains.
2. Confirm `Data/ShareX` exists, there is NO `App/ShareX/ShareX`, and there is NO `Data/TraceGuard/profile-active.txt`.
3. Copy `Data` to a safe separate backup directory (encrypted appropriately if it contains service tokens/uploads).
4. For ZIP users, extract the new ZIP to a **new temporary location**. Copy its `ShareXPortable.exe`, `App`, and `Other` into the existing portable root, leaving the existing `Data` untouched. Remove obsolete `App` only once the backup is secured and ShareX is closed. Better: use the separate independent installer, which manages version-specific replacements.
5. Start through the root launcher. Test screenshot, history, uploaders and tray functions.
6. If it fails, restore the previous binaries from a known-good older ZIP and **matching backup Data**. A new ShareX database/config may not be backwards compatible.

## Relocation / accounts / host coexistence

The launcher determines the root from its own EXE path; both directories are on the same drive, so its directory move works on USB/external drives that allow directory renames. Move/copy the entire package only when stopped and the profile is back in `Data`. An installed ShareX copy uses the same upstream single-instance mechanism and may conflict; exit the installed instance before launching portable. No installed app folders or profiles are modified by this kit. Credentials stored using Windows user/machine-specific encryption may not work on another account or PC.

Do not enable ShareX's built-in **Run at Startup**, **SendTo**, or **Explorer Integration** controls unless willing to create persistent host entries. In particular, current source StartupManager uses `Environment.ProcessPath` for its shortcut, which is the inner ShareX.exe, not the wrapper. Portable hotkey registration may conflict with installed ShareX even after the other instance exits (OS stale hotkeys); investigate rather than forcibly removing registry keys.
