using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Web;
using System.Windows.Forms;

namespace RepairLauncher
{
    static class Program
    {
        // ===== Adjustable settings =====
        static readonly string[] AllowedHosts = { "10.103.127.177" };
        static readonly string[] AllowedExts  = { ".exe", ".bat", ".cmd" };
        const bool EnableCacheFallbackExe = true;
        const bool EnableCacheFallbackBat = false; // usually batch depends on side files
        static readonly string LogDir  = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "RepairLauncher");
        static readonly string CacheDir = Path.Combine(LogDir, "cache");

        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                Directory.CreateDirectory(LogDir);
                Log("==== start ====");

                if (args == null || args.Length == 0)
                    throw new Exception("No URL argument.");

                var raw = args[0];
                Log("raw=" + raw);

                // repairtool://  -> strip scheme -> UrlDecode -> / to \\ -> add leading \\
                var pathPart = System.Text.RegularExpressions.Regex.Replace(raw, @"^(?i)repairtool://", "");
                pathPart = HttpUtility.UrlDecode(pathPart ?? "");
                pathPart = pathPart.Replace('/', '\\').TrimStart('\\');
                var unc = "\\\\" + pathPart;

                // host segment
                var afterHost = unc.IndexOf('\\', 2);
                if (afterHost < 0) throw new Exception("Incomplete path:\n" + unc);
                var nasHost = unc.Substring(2, afterHost - 2);

                if (!AllowedHosts.Contains(nasHost, StringComparer.OrdinalIgnoreCase))
                    throw new Exception("Host not allowed: " + nasHost);

                var ext = Path.GetExtension(unc).ToLowerInvariant();
                if (!AllowedExts.Contains(ext))
                    throw new Exception("Extension not allowed: " + ext);

                var workDir = Path.GetDirectoryName(unc) ?? "\\\\";
                Log(string.Format("target={0} host={1} ext={2}", unc, nasHost, ext));

                bool started = false;
                if (File.Exists(unc))
                {
                    try
                    {
                        switch (ext)
                        {
                            case ".exe":
                                Start(unc, workDir, null);
                                break;
                            case ".bat":
                            case ".cmd":
                                Start("cmd.exe", workDir, "/c \"" + unc + "\"");
                                break;
                        }
                        Log("started from NAS");
                        started = true;
                    }
                    catch (Exception ex)
                    {
                        Log("start from NAS failed: " + ex.ToString());
                    }
                }
                else
                {
                    Log("not found on NAS");
                }

                if (!started)
                {
                    if (ext == ".exe" && EnableCacheFallbackExe)
                    {
                        Directory.CreateDirectory(CacheDir);
                        var local = Path.Combine(CacheDir, Path.GetFileName(unc));
                        File.Copy(unc, local, true);
                        Start(local, CacheDir, null);
                        Log("started from cache: " + local);
                    }
                    else if ((ext == ".bat" || ext == ".cmd") && EnableCacheFallbackBat)
                    {
                        throw new Exception("Cannot start (.bat/.cmd fallback disabled).");
                    }
                    else
                    {
                        throw new Exception("File not found or cannot start from NAS.");
                    }
                }
            }
            catch (Exception ex)
            {
                Log("fatal: " + ex.ToString());
                try { MessageBox.Show("Start failed: " + ex.Message, "RepairLauncher", MessageBoxButtons.OK, MessageBoxIcon.Error); } catch { }
            }
        }

        static void Start(string file, string workingDir, string args)
        {
            var psi = new ProcessStartInfo(file);
            psi.WorkingDirectory = workingDir ?? "";
            psi.UseShellExecute = false;
            psi.CreateNoWindow = false;
            if (!string.IsNullOrEmpty(args)) psi.Arguments = args;
            Process.Start(psi);
        }

        static void Log(string s)
        {
            try
            {
                File.AppendAllText(Path.Combine(LogDir, "launcher.log"),
                    "[" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "] " + s + "\r\n", Encoding.UTF8);
            }
            catch { /* ignore */ }
        }
    }
}
