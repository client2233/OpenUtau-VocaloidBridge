using System.Diagnostics;
using System.Text.Json;
using OpenUtau.Core;
using OpenUtau.Core.Editing;
using OpenUtau.Core.Ustx;

namespace OpenUtau.Plugin.VocaloidBridge;

// Loaded by stock BatchEdit discovery; enables the public track renderer adapter.
public sealed class VocaloidBridgeSettings : BatchEdit {
    private static readonly HashSet<string> watchedConfigs = new();

    public string Name => "VOCALOID / Wine 设置";

    public void Run(UProject project, UVoicePart part, List<UNote> selectedNotes, DocManager docManager) {
        var folder = Path.GetDirectoryName(typeof(VocaloidBridgeSettings).Assembly.Location)!;
        var path = Path.Combine(folder, "bridge-launcher.json");
        var settings = JsonSerializer.Deserialize<LauncherSettings>(File.ReadAllText(path))
            ?? throw new InvalidDataException("Invalid bridge-launcher.json");
        BridgeAttachment.Enable(settings.BackendConfig, docManager);
        WatchBackend(settings.BackendConfig, docManager);
        var script = Path.Combine(settings.ProjectDirectory, "enunu", "configure.py");
        if (!File.Exists(script)) throw new FileNotFoundException("VOCALOID bridge settings script not found", script);
        var info = new ProcessStartInfo(settings.LinuxPython) {
            WorkingDirectory = settings.ProjectDirectory,
            UseShellExecute = false,
        };
        info.ArgumentList.Add(script);
        info.ArgumentList.Add("--config");
        info.ArgumentList.Add(settings.BackendConfig);
        info.ArgumentList.Add("--voices");
        info.ArgumentList.Add(settings.VoicesFile);
        info.ArgumentList.Add("--parent-pid");
        info.ArgumentList.Add(Environment.ProcessId.ToString());
        using var child = Process.Start(info)
            ?? throw new InvalidOperationException("Unable to start VOCALOID bridge settings");
        // Leave the piano roll editable while the settings helper runs. Notes are unchanged.
    }

    private static void WatchBackend(string config, DocManager manager) {
        lock (watchedConfigs) {
            if (!watchedConfigs.Add(config)) return;
        }
        _ = Task.Run(async () => {
            int lastReadyPid = 0;
            var path = config + ".service.local.json";
            while (true) {
                try {
                    if (File.Exists(path)) {
                        var state = JsonSerializer.Deserialize<ServiceState>(File.ReadAllText(path));
                        if (state is { Ready: true } && state.Pid > 0 && state.Pid != lastReadyPid) {
                            using var process = Process.GetProcessById(state.Pid);
                            if (!process.HasExited) {
                                lastReadyPid = state.Pid;
                                manager.PostOnUIThread(() => manager.ExecuteCmd(new PreRenderNotification()));
                            }
                        }
                    }
                } catch (IOException) {
                    // Atomic replacement can race a read; retry on the next poll.
                } catch (JsonException) {
                } catch (InvalidOperationException) {
                    // Server may exit between opening its handle and querying it.
                } catch (ArgumentException) {
                    // A stale state file can refer to an exited server.
                }
                await Task.Delay(250);
            }
        });
    }

    private sealed class ServiceState {
        public bool Ready { get; set; }
        public int Pid { get; set; }
    }

    private sealed class LauncherSettings {
        public string LinuxPython { get; set; } = "/usr/bin/python3";
        public string ProjectDirectory { get; set; } = "";
        public string BackendConfig { get; set; } = "";
        public string VoicesFile { get; set; } = "";
    }
}
