// Independent ShareX Portable launcher. License: MIT (see LICENSE-LAUNCHER.txt).
// The application itself remains under ShareX's upstream GPL license.
// In-package directory moves are SAME-VOLUME ATOMIC, never host AppData harvesting.
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Runtime.InteropServices;

internal static class Program
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr owner, string text, string caption, uint type);
    private const string ProfileName = "ShareX";
    private const string JournalName = "profile-active.txt";
    private static readonly StringComparison PathCompare = StringComparison.OrdinalIgnoreCase;

    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        string runtime = Path.Combine(root, "App", "ShareX");
        string exe = Path.Combine(runtime, "ShareX.exe");
        string data = Path.Combine(root, "Data", ProfileName);
        string live = Path.Combine(runtime, ProfileName);
        string guard = Path.Combine(root, "Data", "TraceGuard");
        string journal = Path.Combine(guard, JournalName);

        if (args.Length == 1 && args[0] == "--self-test")
        {
            return SelfTest();
        }
        if (args.Length == 1 && args[0] == "--diagnose")
        {
            try
            {
                Directory.CreateDirectory(guard);
                File.AppendAllText(Path.Combine(guard, "diagnostics.txt"),
                    $"{DateTimeOffset.Now:O} root={root} app={(File.Exists(exe) ? "present" : "missing")} data={Directory.Exists(data)} live={Directory.Exists(live)} journal={File.Exists(journal)}{Environment.NewLine}", Encoding.UTF8);
                return 0;
            }
            catch { return 1; }
        }
        if (args.Any(a => a.Equals("-multi", StringComparison.OrdinalIgnoreCase) ||
                          a.Equals("-m", StringComparison.OrdinalIgnoreCase)))
        {
            Fail(guard, "ShareX -multi is unsafe with this single shared portable profile.");
            return 2;
        }
        if (!File.Exists(exe))
        {
            Fail(guard, "Missing App\\ShareX\\ShareX.exe; restore application files without replacing Data.");
            return 2;
        }
        string identity = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Path.GetFullPath(root).ToUpperInvariant())))[..24];
        using Mutex mutex = new(false, "Local\\ShareXPortable_" + identity);
        bool locked = false;
        try
        {
            try { locked = mutex.WaitOne(0); }
            catch (AbandonedMutexException) { locked = true; }
            if (!locked)
            {
                Fail(guard, "A launcher is already managing this portable directory. Use the existing tray icon.");
                return 3;
            }
            if (FindShareXProcesses(exe, out string reason))
            {
                Fail(guard, "ShareX is already running (possibly an installed copy). Exit it before starting this portable copy. " + reason);
                return 4;
            }
            Directory.CreateDirectory(guard);
            if (!PrepareProfile(data, live, journal))
            {
                Fail(guard, "Both Data\\ShareX and App\\ShareX\\ShareX exist or recovery state is inconsistent. No data was deleted. See Data\\TraceGuard and reconcile manually.");
                return 5;
            }
            // -portable has highest precedence in ShareX's PersonalPathManager.
            // This also prevents its automatic file-type registration.
            ProcessStartInfo psi = new(exe)
            {
                WorkingDirectory = runtime,
                UseShellExecute = false
            };
            psi.ArgumentList.Add("-portable");
            foreach (string arg in args)
            {
                if (!arg.Equals("-portable", StringComparison.OrdinalIgnoreCase) &&
                    !arg.Equals("-p", StringComparison.OrdinalIgnoreCase))
                    psi.ArgumentList.Add(arg);
            }
            using Process child = Process.Start(psi) ?? throw new IOException("ShareX process could not be started");
            child.WaitForExit(); // ShareX tray lifetime normally keeps this process alive.

            // ShareX can restart itself. Wait for the same packaged binary to leave,
            // without killing or taking ownership of any other processes.
            int quiet = 0;
            for (int i = 0; i < 120; i++)
            {
                bool running = IsPackagedShareXRunning(exe, out bool uncertain);
                if (uncertain) throw new IOException("Cannot safely establish whether a ShareX process has finished; profile left in App for recovery.");
                quiet = running ? 0 : quiet + 1;
                if (quiet >= 3) break;
                Thread.Sleep(1000);
            }
            if (quiet < 3) throw new IOException("ShareX still active after 120 seconds; profile left untouched for recovery.");
            if (!ReturnProfile(data, live, journal))
                throw new IOException("Profile return conflict. No copy was overwritten. See Data\\TraceGuard.");
            return 0;
        }
        catch (Exception ex)
        {
            Fail(guard, ex.ToString() + "\nProfile files remain untouched if return was unsafe. Restart through this launcher for recovery.");
            return 6;
        }
        finally { if (locked) mutex.ReleaseMutex(); }
    }

    private static bool PrepareProfile(string data, string live, string journal)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(data)!);
        Directory.CreateDirectory(Path.GetDirectoryName(live)!);
        if (IsReparse(data) || IsReparse(live)) return false;
        bool d = Directory.Exists(data), l = Directory.Exists(live);
        if (d && l) return false;
        if (l && !d)
        {
            // Only resume an in-progress move that THIS launcher recorded.
            return File.Exists(journal) && File.ReadAllText(journal, Encoding.UTF8).Trim() == "profile-active-v1";
        }
        if (!d && !l)
        {
            if (File.Exists(journal)) return false;
            Directory.CreateDirectory(data);
            d = true;
        }
        if (!d) return false;
        // If a previous process completed the return, journal may still exist.
        // No source profile exists in App, so safe to clear a stale owned journal.
        if (File.Exists(journal)) File.Delete(journal);
        AtomicWrite(journal, "profile-active-v1\n");
        Directory.Move(data, live); // Keeps every empty directory and all content.
        return true;
    }

    private static bool ReturnProfile(string data, string live, string journal)
    {
        if (IsReparse(data) || IsReparse(live)) return false;
        bool d = Directory.Exists(data), l = Directory.Exists(live);
        if (d && l) return false;
        if (l && !d)
        {
            Directory.Move(live, data);
        }
        else if (!d && !l) return false;
        // Data exists and App profile does not: successful prior return.
        if (File.Exists(journal)) File.Delete(journal);
        return true;
    }

    private static bool IsReparse(string path) =>
        (File.Exists(path) || Directory.Exists(path)) &&
        (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0;

    private static void AtomicWrite(string path, string content)
    {
        string temp = path + ".new";
        if (File.Exists(temp)) File.Delete(temp);
        File.WriteAllText(temp, content, new UTF8Encoding(false));
        File.Move(temp, path, true);
    }

    private static bool FindShareXProcesses(string packagedExe, out string reason)
    {
        reason = "";
        foreach (Process p in Process.GetProcessesByName("ShareX"))
        {
            try
            {
                string? file = p.MainModule?.FileName;
                if (file == null) { reason = "A process path could not be read."; return true; }
                reason = file.Equals(packagedExe, PathCompare) ? "Packaged ShareX already running." : "Another ShareX installation is active.";
                return true;
            }
            catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
            {
                reason = "An existing ShareX process path is inaccessible.";
                return true;
            }
            finally { p.Dispose(); }
        }
        return false;
    }

    private static bool IsPackagedShareXRunning(string packagedExe, out bool uncertain)
    {
        uncertain = false;
        foreach (Process p in Process.GetProcessesByName("ShareX"))
        {
            try
            {
                if (p.MainModule?.FileName?.Equals(packagedExe, PathCompare) == true) return true;
            }
            catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
            { uncertain = true; }
            finally { p.Dispose(); }
        }
        return false;
    }

    private static void Fail(string guard, string message)
    {
        try
        {
            Directory.CreateDirectory(guard);
            File.AppendAllText(Path.Combine(guard, "launcher-errors.log"),
                $"[{DateTimeOffset.Now:O}] {message}{Environment.NewLine}", Encoding.UTF8);
        }
        catch { /* never discard the original error because logging failed */ }
        // Avoid a hidden modal dialog in automation. Errors are in Data/TraceGuard.
        // Real user failures also receive a Windows native dialog.
        if (!string.Equals(Environment.GetEnvironmentVariable("SHAREX_PORTABLE_HEADLESS"), "1", StringComparison.Ordinal))
            MessageBox(IntPtr.Zero, message, "ShareX Portable", 0x00000010U);
    }

    private static int SelfTest()
    {
        string temp = Path.Combine(Path.GetTempPath(), "ShareXPortableTest-" + Guid.NewGuid().ToString("N"));
        string data = Path.Combine(temp, "Data", "ShareX");
        string live = Path.Combine(temp, "App", "ShareX", "ShareX");
        string guard = Path.Combine(temp, "Data", "TraceGuard");
        string journal = Path.Combine(guard, JournalName);
        try
        {
            Directory.CreateDirectory(guard);
            Directory.CreateDirectory(Path.Combine(data, "empty", "nested", "empty"));
            File.WriteAllText(Path.Combine(data, "keep.txt"), "keep", Encoding.UTF8);
            if (!PrepareProfile(data, live, journal)) throw new Exception("prepare failed");
            if (!Directory.Exists(Path.Combine(live, "empty", "nested", "empty"))) throw new Exception("empty directory lost");
            // Simulates a dead launcher: active journal + live profile, no Data profile.
            if (!PrepareProfile(data, live, journal)) throw new Exception("crash recovery failed");
            if (!ReturnProfile(data, live, journal)) throw new Exception("return failed");
            if (!File.Exists(Path.Combine(data, "keep.txt"))) throw new Exception("file lost");
            if (!Directory.Exists(Path.Combine(data, "empty", "nested", "empty"))) throw new Exception("empty tree lost");
            if (File.Exists(journal)) throw new Exception("journal not cleared");
            Directory.CreateDirectory(live);
            if (PrepareProfile(data, live, journal)) throw new Exception("dual profile not blocked");
            File.WriteAllText(Path.Combine(guard, "selftest.txt"), "PASS\n", Encoding.UTF8);
            return 0;
        }
        catch (Exception ex)
        {
            try { Directory.CreateDirectory(guard); File.WriteAllText(Path.Combine(guard, "selftest.txt"), "FAIL: " + ex, Encoding.UTF8); } catch { }
            return 1;
        }
        finally { try { Directory.Delete(temp, true); } catch { } }
    }
}
