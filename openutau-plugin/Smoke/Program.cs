using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Text.Json;
using OpenUtau.Core;
using OpenUtau.Core.Editing;
using OpenUtau.Core.Ustx;

AssemblyLoadContext.Default.Resolving += (_, name) => {
    var path = Path.Combine(Environment.GetEnvironmentVariable("OPENUTAU_DIR") ?? "/opt/openutau", name.Name + ".dll");
    return File.Exists(path) ? AssemblyLoadContext.Default.LoadFromAssemblyPath(path) : null;
};
Run(args[0]);

[MethodImpl(MethodImplOptions.NoInlining)]
static void Run(string logFile) {
    System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance);
    var manager = DocManager.Inst;
    typeof(DocManager).GetField("mainThread", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!.SetValue(manager, Thread.CurrentThread);
    manager.SearchAllPlugins();
    var type = manager.ExternalBatchEditTypes.Single(t => t.FullName == "OpenUtau.Plugin.VocaloidBridge.VocaloidBridgeSettings");
    var edit = (BatchEdit)Activator.CreateInstance(type)!;
    var project = new UProject();
    var part = new UVoicePart();
    var note = UNote.Create(); note.lyric = "ni"; note.position=480; note.duration=480; note.tone=60;
    part.notes.Add(note); var selected = new List<UNote>{note};
    int retries = 0;
    var uiQueue = new System.Collections.Concurrent.ConcurrentQueue<Action>();
    manager.PostOnUIThread = action => uiQueue.Enqueue(action);
    manager.AddSubscriber(new RetryObserver(() => Interlocked.Increment(ref retries)));
    void Pump() { while (uiQueue.TryDequeue(out var action)) action(); }
    edit.Run(project, part, selected, manager);
    var deadline = DateTime.UtcNow.AddSeconds(5);
    while (!File.Exists(logFile) && DateTime.UtcNow < deadline) Thread.Sleep(20);
    var argv = JsonSerializer.Deserialize<string[]>(File.ReadAllText(logFile))!;
    if (argv.Length != 7 || argv[1] != "--config" || argv[3] != "--voices"
        || argv[5] != "--parent-pid" || argv[6] != Environment.ProcessId.ToString()) throw new Exception("Incorrect launcher arguments");
    if (part.notes.Count != 1 || part.notes.First()!=note || note.position!=480 || note.duration!=480 || note.lyric!="ni")
        throw new Exception("Plugin changed the score");
    var stateFile = Path.Combine(Path.GetDirectoryName(logFile)!, "project with spaces", "bridge", "config.local.json.service.local.json");
    Directory.CreateDirectory(Path.GetDirectoryName(stateFile)!);
    File.WriteAllText(stateFile, JsonSerializer.Serialize(new { Ready = true, Pid = Environment.ProcessId }));
    deadline = DateTime.UtcNow.AddSeconds(5);
    while (Volatile.Read(ref retries) == 0 && DateTime.UtcNow < deadline) { Pump(); Thread.Sleep(20); }
    if (retries != 1) throw new Exception("Backend ready did not schedule retry");
    Thread.Sleep(600);
    if (retries != 1) throw new Exception("Repeated state reads duplicated retry");
    using var generation = Process.Start(new ProcessStartInfo("/usr/bin/sleep", "30") { UseShellExecute = false })!;
    File.WriteAllText(stateFile, JsonSerializer.Serialize(new { Ready = true, Pid = generation.Id }));
    deadline = DateTime.UtcNow.AddSeconds(5);
    while (Volatile.Read(ref retries) < 2 && DateTime.UtcNow < deadline) { Pump(); Thread.Sleep(20); }
    generation.Kill(); generation.WaitForExit();
    if (retries != 2) throw new Exception("Backend restart did not schedule retry");
    Console.WriteLine("PASS: backend ready/restart schedules UI render retry exactly once per service generation");
    Console.WriteLine("PASS: installed stock Core discovered DLL, created menu command, launched helper with exact arguments and left notes unchanged");
}

sealed class RetryObserver(Action received) : ICmdSubscriber {
    public void OnNext(UCommand cmd, bool isUndo) { if (cmd is PreRenderNotification) received(); }
}
