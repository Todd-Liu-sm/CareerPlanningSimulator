// Installer stub for the game.
//
// Built by tools/build.ps1 with the .NET Framework csc.exe that ships with
// Windows. The game payload (a zip) is appended to this executable at build
// time as a trailing "overlay" after a magic marker, so the result is a single
// self-contained setup .exe -- no external packer needed.
//
// On run it:
//   1. finds the overlay by scanning for the magic marker
//   2. extracts it to %LOCALAPPDATA%\<GameName>
//   3. drops a desktop + start-menu shortcut pointing at the game exe
//   4. offers to launch
//
// Why not IExpress: it silently fails with /Q (exit 1, no output) and its SED
// format mishandles non-ASCII paths, which this project's folder name has.
//
// Compile (see build.ps1):
//   csc /target:winexe /out:setup.exe /r:System.IO.Compression.FileSystem.dll installer_stub.cs

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

internal static class Installer
{
    // Trailer layout: [payload bytes][8-byte little-endian payload length][16-byte magic]
    private static readonly byte[] Magic = Encoding.ASCII.GetBytes("CSIMPAYLOADv1\0\0\0");

    // Injected by build.ps1 via /define or by rewriting these constants.
    private const string GameName = "__GAME_NAME__";
    private const string GameExe = "__GAME_EXE__";
    private const string PayloadZip = "__PAYLOAD_ZIP__";

    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();

        try
        {
            string installDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                GameName);

            DialogResult go = MessageBox.Show(
                "即将安装到：\n" + installDir + "\n\n继续吗？",
                GameName + " 安装程序",
                MessageBoxButtons.OKCancel,
                MessageBoxIcon.Information);

            if (go != DialogResult.OK)
            {
                return;
            }

            if (Directory.Exists(installDir))
            {
                DialogResult overwrite = MessageBox.Show(
                    "已经装过一份了。要覆盖安装吗？\n\n选\"否\"就只启动已有的版本。",
                    GameName,
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Question);

                if (overwrite == DialogResult.No)
                {
                    Launch(installDir);
                    return;
                }

                try { Directory.Delete(installDir, true); }
                catch (Exception) { /* locked files: fall through and overwrite in place */ }
            }

            string zipPath = ExtractPayload();
            if (zipPath == null)
            {
                MessageBox.Show(
                    "安装包损坏：找不到内嵌的游戏数据。\n请重新下载。",
                    GameName, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            Directory.CreateDirectory(installDir);

            // Some players run this from a temp dir, so copy the zip next to the
            // install target before extracting (ExtractToDirectory needs a real file).
            string localZip = Path.Combine(installDir, "__payload.zip");
            File.Copy(zipPath, localZip, true);
            ZipFile.ExtractToDirectory(localZip, installDir);
            try { File.Delete(localZip); } catch (Exception) { }

            string exePath = Path.Combine(installDir, GameExe);
            if (!File.Exists(exePath))
            {
                MessageBox.Show(
                    "解压完成，但没找到 " + GameExe + "。\n请手动打开：" + installDir,
                    GameName, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                Process.Start("explorer.exe", installDir);
                return;
            }

            string shortcutNote = MakeShortcuts(exePath, installDir);

            DialogResult play = MessageBox.Show(
                "安装完成。" + shortcutNote + "\n\n现在就玩吗？",
                GameName,
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information);

            if (play == DialogResult.Yes)
            {
                Launch(installDir);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "安装出错了：\n\n" + ex.Message,
                GameName, MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static void Launch(string installDir)
    {
        string exePath = Path.Combine(installDir, GameExe);
        if (File.Exists(exePath))
        {
            Process.Start(new ProcessStartInfo(exePath) { WorkingDirectory = installDir });
        }
        else
        {
            Process.Start("explorer.exe", installDir);
        }
    }

    private static string MakeShortcuts(string exePath, string installDir)
    {
        string made = "";
        try
        {
            string desktop = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                GameName + ".lnk");
            CreateShortcut(desktop, exePath, installDir);
            made = "\n已在桌面创建快捷方式。";
        }
        catch (Exception)
        {
            // Shortcut creation can be blocked; the game is installed either way.
        }
        return made;
    }

    private static void CreateShortcut(string linkPath, string targetPath, string workingDir)
    {
        // Late-bound WScript.Shell so this compiles without COM interop refs.
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null) { return; }

        object shell = Activator.CreateInstance(shellType);
        object shortcut = shellType.InvokeMember(
            "CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { linkPath });

        Type linkType = shortcut.GetType();
        linkType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
        linkType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workingDir });
        linkType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath + ",0" });
        linkType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
    }

    /// <summary>Find the appended zip; returns a path to it, or null.</summary>
    private static string ExtractPayload()
    {
        if (PayloadZip.Length > 0 && File.Exists(PayloadZip))
        {
            return PayloadZip;   // build-time override, handy for testing
        }

        string self = Assembly.GetExecutingAssembly().Location;
        using (FileStream fs = File.OpenRead(self))
        {
            long length = fs.Length;
            if (length < Magic.Length + 8) { return null; }

            // Read the trailer.
            fs.Seek(-(Magic.Length + 8), SeekOrigin.End);
            byte[] trailer = new byte[Magic.Length + 8];
            fs.Read(trailer, 0, trailer.Length);

            for (int i = 0; i < Magic.Length; i++)
            {
                if (trailer[8 + i] != Magic[i]) { return null; }
            }

            long payloadLength = BitConverter.ToInt64(trailer, 0);
            long payloadStart = length - Magic.Length - 8 - payloadLength;
            if (payloadStart < 0) { return null; }

            string temp = Path.Combine(Path.GetTempPath(), GameName + "-payload.zip");
            fs.Seek(payloadStart, SeekOrigin.Begin);

            using (FileStream outFs = File.Create(temp))
            {
                byte[] buffer = new byte[81920];
                long remaining = payloadLength;
                while (remaining > 0)
                {
                    int want = (int)Math.Min(buffer.Length, remaining);
                    int got = fs.Read(buffer, 0, want);
                    if (got <= 0) { break; }
                    outFs.Write(buffer, 0, got);
                    remaining -= got;
                }
            }

            return temp;
        }
    }
}
