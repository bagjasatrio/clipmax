using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;

namespace ClipMaxLauncher
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                
                // Priority 1: pythonw.exe in .venv (zero console window)
                string pythonw = Path.Combine(baseDir, ".venv", "Scripts", "pythonw.exe");
                string python = Path.Combine(baseDir, ".venv", "Scripts", "python.exe");
                
                string targetPython = File.Exists(pythonw) ? pythonw : (File.Exists(python) ? python : null);
                
                if (targetPython == null)
                {
                    MessageBox.Show(
                        "Python virtual environment (.venv) tidak ditemukan di direktori:\n" + baseDir + "\n\nHarap jalankan setup virtual environment terlebih dahulu.",
                        "ClipMax Launcher Error",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                string scriptPath = Path.Combine(baseDir, "run.py");
                if (!File.Exists(scriptPath))
                {
                    MessageBox.Show(
                        "File entry point 'run.py' tidak ditemukan di:\n" + baseDir,
                        "ClipMax Launcher Error",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                string arguments = "\"" + scriptPath + "\"";
                if (args != null && args.Length > 0)
                {
                    arguments += " " + string.Join(" ", args);
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = targetPython;
                psi.Arguments = arguments;
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Gagal meluncurkan ClipMax:\n" + ex.Message,
                    "ClipMax Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }
}
