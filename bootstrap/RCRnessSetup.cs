using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

[assembly: AssemblyTitle("RCRness Setup")]
[assembly: AssemblyDescription("ROM-free owned-input setup host for RCRness")]
[assembly: AssemblyCompany("RCRness contributors")]
[assembly: AssemblyProduct("RCRness Setup")]
[assembly: AssemblyVersion("0.1.3.0")]
[assembly: AssemblyFileVersion("0.1.3.0")]

namespace RCRnessSetup
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length == 1 && String.Equals(args[0], "--self-test",
                StringComparison.OrdinalIgnoreCase))
            {
                return RunSelfTest();
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupForm(args));
            return 0;
        }

        private static int RunSelfTest()
        {
            try
            {
                bool foundBuild = false;
                bool foundSetup = false;
                Assembly assembly = Assembly.GetExecutingAssembly();
                using (Stream resource = assembly.GetManifestResourceStream("RCRness.SourceKit.zip"))
                {
                    if (resource == null) { return 10; }
                    using (ZipArchive archive = new ZipArchive(resource, ZipArchiveMode.Read, false))
                    {
                        foreach (ZipArchiveEntry entry in archive.Entries)
                        {
                            string name = entry.FullName.Replace('\\', '/');
                            string lower = name.ToLowerInvariant();
                            if (lower.EndsWith("/build.ps1")) { foundBuild = true; }
                            if (lower.EndsWith("/setup-and-build.ps1")) { foundSetup = true; }
                            if (lower.Contains("/generated/") || lower.Contains("/captures/") ||
                                lower.EndsWith(".nes") || lower.EndsWith(".bin") ||
                                lower.EndsWith(".sav") || lower.EndsWith(".srm") ||
                                lower.EndsWith(".state") || lower.EndsWith(".exe") ||
                                lower.EndsWith(".dll") || lower.EndsWith(".pdb") ||
                                lower.EndsWith(".obj"))
                            {
                                return 11;
                            }
                        }
                    }
                }
                if (!foundBuild || !foundSetup) { return 12; }

                string testRoot = Path.Combine(Path.GetTempPath(),
                    "RCRness-setup-self-test-" + Guid.NewGuid().ToString("N"));
                try
                {
                    string older = Path.Combine(testRoot, "source-v0.1.2", "build-public");
                    string newer = Path.Combine(testRoot, "source-v0.1.3", "build-public");
                    Directory.CreateDirectory(older);
                    Directory.CreateDirectory(newer);
                    string olderExe = Path.Combine(older, "RCRness.exe");
                    string newerExe = Path.Combine(newer, "RCRness.exe");
                    File.WriteAllBytes(olderExe, new byte[] { 1 });
                    File.WriteAllBytes(newerExe, new byte[] { 2 });
                    File.SetLastWriteTimeUtc(olderExe, DateTime.UtcNow.AddMinutes(-1));
                    File.SetLastWriteTimeUtc(newerExe, DateTime.UtcNow);
                    string expectedRom = Path.Combine(testRoot, "owned-input.nes");
                    File.WriteAllText(Path.Combine(testRoot, "source-v0.1.3", "last-rom.txt"),
                        expectedRom, Encoding.UTF8);
                    if (!String.Equals(SetupForm.FindPreviousGameExe(testRoot), newerExe,
                        StringComparison.OrdinalIgnoreCase)) { return 14; }
                    if (!String.Equals(SetupForm.RememberedRomForBuild(newerExe), expectedRom,
                        StringComparison.OrdinalIgnoreCase)) { return 15; }
                }
                finally
                {
                    if (Directory.Exists(testRoot))
                    {
                        Directory.Delete(testRoot, true);
                    }
                }
                return 0;
            }
            catch
            {
                return 13;
            }
        }
    }

    internal sealed class SetupForm : Form
    {
        private const string SetupVersion = "0.1.3";
        private const string SourceResource = "RCRness.SourceKit.zip";
        private const string ExpectedRomSha256 =
            "B95F8DEF04C0012604B7CC68CF4ED8F49B2DFE4BEDA6182051DE4B2423BEA7B1";

        private readonly Button selectButton;
        private readonly Button playButton;
        private readonly Button rebuildButton;
        private readonly Button folderButton;
        private readonly ProgressBar progress;
        private readonly TextBox log;
        private readonly Label status;
        private readonly string initialRom;
        private bool busy;

        public SetupForm(string[] args)
        {
            initialRom = args.Length > 0 ? args[0] : null;

            Text = "RCRness Setup";
            ClientSize = new Size(720, 470);
            MinimumSize = new Size(620, 400);
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Segoe UI", 9F);
            AllowDrop = true;

            Label title = new Label();
            title.Text = "RCRness owned-input builder";
            title.Font = new Font("Segoe UI Semibold", 18F, FontStyle.Bold);
            title.AutoSize = true;
            title.Location = new Point(24, 20);
            Controls.Add(title);

            Label explanation = new Label();
            explanation.Text =
                "This setup host contains no game ROM or generated game code. " +
                "Choose your legally obtained River City Ransom (USA) NES ROM. " +
                "RCRness will verify it, obtain the open build tools, compile the game locally, and launch it.";
            explanation.Location = new Point(27, 62);
            explanation.Size = new Size(660, 55);
            explanation.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            Controls.Add(explanation);

            selectButton = new Button();
            selectButton.Text = "Select ROM and Build";
            selectButton.Location = new Point(28, 126);
            selectButton.Size = new Size(180, 36);
            selectButton.Click += delegate { ChooseRomAndBuild(); };
            Controls.Add(selectButton);

            playButton = new Button();
            playButton.Text = "Play Previous Build";
            playButton.Location = new Point(28, 126);
            playButton.Size = new Size(180, 36);
            playButton.Click += delegate { PlayPreviousBuild(); };
            playButton.Visible = false;
            Controls.Add(playButton);

            rebuildButton = new Button();
            rebuildButton.Text = "Rebuild";
            rebuildButton.Location = new Point(220, 126);
            rebuildButton.Size = new Size(130, 36);
            rebuildButton.Click += delegate { RebuildPrevious(); };
            rebuildButton.Visible = false;
            Controls.Add(rebuildButton);

            folderButton = new Button();
            folderButton.Text = "Open Build Folder";
            folderButton.Location = new Point(220, 126);
            folderButton.Size = new Size(155, 36);
            folderButton.Click += delegate { OpenBuildFolder(); };
            Controls.Add(folderButton);

            status = new Label();
            status.Text = "Ready. You can also drag a .nes file onto this window.";
            status.Location = new Point(29, 176);
            status.Size = new Size(650, 22);
            status.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            Controls.Add(status);

            progress = new ProgressBar();
            progress.Location = new Point(29, 201);
            progress.Size = new Size(660, 18);
            progress.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            Controls.Add(progress);

            log = new TextBox();
            log.Location = new Point(29, 232);
            log.Size = new Size(660, 210);
            log.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            log.Multiline = true;
            log.ReadOnly = true;
            log.ScrollBars = ScrollBars.Vertical;
            log.Font = new Font("Consolas", 9F);
            log.BackColor = Color.FromArgb(24, 24, 24);
            log.ForeColor = Color.Gainsboro;
            Controls.Add(log);

            DragEnter += OnDragEnter;
            DragDrop += OnDragDrop;
            Shown += OnShown;
        }

        private void OnShown(object sender, EventArgs e)
        {
            BeginInvoke((MethodInvoker)delegate
            {
                if (!String.IsNullOrWhiteSpace(initialRom))
                {
                    StartBuild(initialRom);
                }
                else if (FindPreviousGameExe() != null)
                {
                    UpdateBuildActions();
                    SetStatus("Previous build found. Play it now or rebuild from your ROM.");
                    AppendLog("A completed local build is ready. No rebuild is needed to play it.");
                }
                else
                {
                    ChooseRomAndBuild();
                }
            });
        }

        private void OnDragEnter(object sender, DragEventArgs e)
        {
            if (!busy && e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                e.Effect = DragDropEffects.Copy;
            }
        }

        private void OnDragDrop(object sender, DragEventArgs e)
        {
            if (busy)
            {
                return;
            }
            string[] files = e.Data.GetData(DataFormats.FileDrop) as string[];
            if (files != null && files.Length > 0)
            {
                StartBuild(files[0]);
            }
        }

        private void ChooseRomAndBuild()
        {
            if (busy)
            {
                return;
            }

            using (OpenFileDialog picker = new OpenFileDialog())
            {
                picker.Title = "Select River City Ransom (USA) NES ROM";
                picker.Filter = "NES ROM (*.nes)|*.nes|All files (*.*)|*.*";
                picker.CheckFileExists = true;
                picker.Multiselect = false;
                if (picker.ShowDialog(this) == DialogResult.OK)
                {
                    StartBuild(picker.FileName);
                }
            }
        }

        private void RebuildPrevious()
        {
            string gameExe = FindPreviousGameExe();
            string rememberedRom = RememberedRomForBuild(gameExe);
            if (!String.IsNullOrWhiteSpace(rememberedRom) && File.Exists(rememberedRom))
            {
                StartBuild(rememberedRom);
            }
            else
            {
                ChooseRomAndBuild();
            }
        }

        private void PlayPreviousBuild()
        {
            string gameExe = FindPreviousGameExe();
            if (String.IsNullOrWhiteSpace(gameExe) || !File.Exists(gameExe))
            {
                UpdateBuildActions();
                SetStatus("No completed build was found. Select your ROM to build RCRness.");
                return;
            }

            string rememberedRom = RememberedRomForBuild(gameExe);
            AppendLog("Launching the existing private build without rebuilding...");
            LaunchGame(gameExe,
                !String.IsNullOrWhiteSpace(rememberedRom) && File.Exists(rememberedRom)
                    ? rememberedRom : null);
            SetStatus("Previous build launched. No compilation was needed.");
        }

        private async void StartBuild(string romPath)
        {
            if (busy)
            {
                return;
            }

            if (!File.Exists(romPath))
            {
                MessageBox.Show(this, "The selected ROM could not be found.",
                    "RCRness Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            SetBusy(true);
            try
            {
                SetStatus("Verifying ROM...");
                AppendLog("Verifying the selected ROM without uploading or copying it...");
                string actualHash = await Task.Run(delegate { return Sha256File(romPath); });
                if (!String.Equals(actualHash, ExpectedRomSha256,
                    StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException(
                        "This is not the supported River City Ransom (USA) ROM.\r\n\r\n" +
                        "Expected SHA-256:\r\n" + ExpectedRomSha256 + "\r\n\r\n" +
                        "Selected file SHA-256:\r\n" + actualHash);
                }
                AppendLog("ROM verified successfully.");

                DialogResult consent = MessageBox.Show(this,
                    "RCRness will download a pinned, hash-verified portable compiler, " +
                    "CMake, and Ninja (about 231 MiB total). They stay in your local " +
                    "RCRness folder and do not install Visual Studio or a Windows SDK. " +
                    "If Git is missing, setup may install Git through WinGet and accept " +
                    "its package agreements.\r\n\r\nContinue with the local build?",
                    "Download compact build tools", MessageBoxButtons.YesNo,
                    MessageBoxIcon.Information);
                if (consent != DialogResult.Yes)
                {
                    AppendLog("Build cancelled before installing or changing tools.");
                    return;
                }

                string sourceRoot = ExtractSourceKit();
                string setupScript = Path.Combine(sourceRoot, "setup-and-build.ps1");
                if (!File.Exists(setupScript))
                {
                    throw new FileNotFoundException("The embedded build kit is incomplete.", setupScript);
                }

                SetStatus("Preparing portable tools and building RCRness...");
                progress.Style = ProgressBarStyle.Marquee;
                int exitCode = await RunBuild(setupScript, romPath, sourceRoot);
                progress.Style = ProgressBarStyle.Blocks;
                if (exitCode != 0)
                {
                    throw new InvalidOperationException(
                        "The local build did not complete (exit code " + exitCode + "). " +
                        "Review the log above. If Windows requested a restart, restart and run this setup again.");
                }

                string gameExe = Path.Combine(sourceRoot, "build-public", "RCRness.exe");
                if (!File.Exists(gameExe))
                {
                    throw new FileNotFoundException("The build completed but RCRness.exe was not found.", gameExe);
                }

                File.WriteAllText(Path.Combine(sourceRoot, "last-rom.txt"),
                    Path.GetFullPath(romPath), Encoding.UTF8);
                SetStatus("Build complete. Launching RCRness...");
                AppendLog("Build complete. Launching the locally generated game...");
                LaunchGame(gameExe, romPath);
                progress.Value = 100;
                SetStatus("RCRness is ready and has been launched.");
            }
            catch (Exception ex)
            {
                progress.Style = ProgressBarStyle.Blocks;
                AppendLog("ERROR: " + ex.Message);
                SetStatus("Setup did not complete.");
                MessageBox.Show(this, ex.Message, "RCRness Setup",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                SetBusy(false);
            }
        }

        private string ExtractSourceKit()
        {
            string installRoot = CurrentInstallRoot();
            Directory.CreateDirectory(installRoot);

            SetStatus("Preparing the clean source kit...");
            AppendLog("Preparing the ROM-free source kit in " + installRoot);

            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream resource = assembly.GetManifestResourceStream(SourceResource))
            {
                if (resource == null)
                {
                    throw new InvalidOperationException("The embedded source kit is missing.");
                }
                using (ZipArchive archive = new ZipArchive(resource, ZipArchiveMode.Read, false))
                {
                    foreach (ZipArchiveEntry entry in archive.Entries)
                    {
                        string relative = StripFirstPathComponent(entry.FullName);
                        if (String.IsNullOrEmpty(relative))
                        {
                            continue;
                        }

                        string destination = SafeDestination(installRoot, relative);
                        if (entry.FullName.EndsWith("/", StringComparison.Ordinal))
                        {
                            Directory.CreateDirectory(destination);
                            continue;
                        }

                        string parent = Path.GetDirectoryName(destination);
                        if (!String.IsNullOrEmpty(parent))
                        {
                            Directory.CreateDirectory(parent);
                        }
                        using (Stream input = entry.Open())
                        using (FileStream output = new FileStream(destination, FileMode.Create,
                            FileAccess.Write, FileShare.None))
                        {
                            input.CopyTo(output);
                        }
                    }
                }
            }
            return installRoot;
        }

        private Task<int> RunBuild(string setupScript, string romPath, string sourceRoot)
        {
            TaskCompletionSource<int> completion = new TaskCompletionSource<int>();
            Process process = new Process();
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(Environment.SystemDirectory,
                "WindowsPowerShell", "v1.0", "powershell.exe");
            start.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File " +
                QuoteArgument(setupScript) + " -Rom " + QuoteArgument(Path.GetFullPath(romPath)) +
                " -AcceptToolLicenses";
            start.WorkingDirectory = sourceRoot;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.StandardOutputEncoding = Encoding.UTF8;
            start.StandardErrorEncoding = Encoding.UTF8;

            process.StartInfo = start;
            process.EnableRaisingEvents = true;
            process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data != null) { AppendLog(e.Data); }
            };
            process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data != null) { AppendLog(e.Data); }
            };
            process.Exited += delegate
            {
                int code = process.ExitCode;
                process.Dispose();
                completion.TrySetResult(code);
            };

            AppendLog("Starting the local toolchain and game build...");
            if (!process.Start())
            {
                process.Dispose();
                throw new InvalidOperationException("Windows PowerShell could not be started.");
            }
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            return completion.Task;
        }

        private void SetBusy(bool value)
        {
            busy = value;
            selectButton.Enabled = !value;
            playButton.Enabled = !value;
            rebuildButton.Enabled = !value;
            AllowDrop = !value;
            if (!value)
            {
                UpdateBuildActions();
            }
        }

        private void SetStatus(string value)
        {
            if (InvokeRequired)
            {
                BeginInvoke((MethodInvoker)delegate { SetStatus(value); });
                return;
            }
            status.Text = value;
        }

        private void AppendLog(string value)
        {
            if (InvokeRequired)
            {
                BeginInvoke((MethodInvoker)delegate { AppendLog(value); });
                return;
            }
            log.AppendText(value + Environment.NewLine);
        }

        private void OpenBuildFolder()
        {
            string gameExe = FindPreviousGameExe();
            string folder = gameExe == null
                ? CurrentInstallRoot() : Path.GetDirectoryName(gameExe);
            Directory.CreateDirectory(folder);
            Process.Start(new ProcessStartInfo("explorer.exe", QuoteArgument(folder)));
        }

        private void UpdateBuildActions()
        {
            bool hasBuild = FindPreviousGameExe() != null;
            selectButton.Visible = !hasBuild;
            playButton.Visible = hasBuild;
            rebuildButton.Visible = hasBuild;
            folderButton.Location = hasBuild ? new Point(362, 126) : new Point(220, 126);
        }

        private static string RCRnessDataRoot()
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "RCRness");
        }

        private static string CurrentInstallRoot()
        {
            return Path.Combine(RCRnessDataRoot(), "source-v" + SetupVersion);
        }

        private static string FindPreviousGameExe()
        {
            return FindPreviousGameExe(RCRnessDataRoot());
        }

        internal static string FindPreviousGameExe(string dataRoot)
        {
            if (!Directory.Exists(dataRoot))
            {
                return null;
            }

            string newest = null;
            DateTime newestTime = DateTime.MinValue;
            foreach (string sourceRoot in Directory.GetDirectories(dataRoot, "source-v*"))
            {
                string candidate = Path.Combine(sourceRoot, "build-public", "RCRness.exe");
                if (!File.Exists(candidate))
                {
                    continue;
                }
                DateTime written = File.GetLastWriteTimeUtc(candidate);
                if (newest == null || written > newestTime)
                {
                    newest = candidate;
                    newestTime = written;
                }
            }
            return newest;
        }

        internal static string RememberedRomForBuild(string gameExe)
        {
            if (String.IsNullOrWhiteSpace(gameExe))
            {
                return null;
            }
            DirectoryInfo buildDirectory = Directory.GetParent(gameExe);
            DirectoryInfo sourceDirectory = buildDirectory == null
                ? null : buildDirectory.Parent;
            if (sourceDirectory == null)
            {
                return null;
            }
            string marker = Path.Combine(sourceDirectory.FullName, "last-rom.txt");
            if (!File.Exists(marker))
            {
                return null;
            }
            string value = File.ReadAllText(marker, Encoding.UTF8).Trim();
            return String.IsNullOrWhiteSpace(value) ? null : value;
        }

        private static void LaunchGame(string gameExe, string romPath)
        {
            ProcessStartInfo game = new ProcessStartInfo();
            game.FileName = gameExe;
            game.Arguments = String.IsNullOrWhiteSpace(romPath)
                ? String.Empty : QuoteArgument(Path.GetFullPath(romPath));
            game.WorkingDirectory = Path.GetDirectoryName(gameExe);
            game.UseShellExecute = true;
            Process.Start(game);
        }

        private static string Sha256File(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
            {
                byte[] hash = sha.ComputeHash(stream);
                StringBuilder text = new StringBuilder(hash.Length * 2);
                foreach (byte value in hash)
                {
                    text.Append(value.ToString("X2"));
                }
                return text.ToString();
            }
        }

        private static string StripFirstPathComponent(string path)
        {
            string normalized = path.Replace('\\', '/');
            int slash = normalized.IndexOf('/');
            return slash < 0 ? String.Empty : normalized.Substring(slash + 1);
        }

        private static string SafeDestination(string root, string relative)
        {
            string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) +
                Path.DirectorySeparatorChar;
            string destination = Path.GetFullPath(Path.Combine(fullRoot,
                relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!destination.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidDataException("Unsafe path in embedded source kit: " + relative);
            }
            return destination;
        }

        private static string QuoteArgument(string value)
        {
            if (value == null) { return "\"\""; }
            StringBuilder result = new StringBuilder();
            result.Append('"');
            int backslashes = 0;
            foreach (char character in value)
            {
                if (character == '\\')
                {
                    backslashes++;
                }
                else if (character == '"')
                {
                    result.Append('\\', backslashes * 2 + 1);
                    result.Append('"');
                    backslashes = 0;
                }
                else
                {
                    result.Append('\\', backslashes);
                    result.Append(character);
                    backslashes = 0;
                }
            }
            result.Append('\\', backslashes * 2);
            result.Append('"');
            return result.ToString();
        }
    }
}
