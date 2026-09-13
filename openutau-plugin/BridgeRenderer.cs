using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using NetMQ;
using NetMQ.Sockets;
using OpenUtau.Core;
using OpenUtau.Core.Enunu;
using OpenUtau.Core.Render;
using OpenUtau.Core.Ustx;

namespace OpenUtau.Plugin.VocaloidBridge;

// Installed on bridge-owned ENUNU tracks through URenderSettings.Renderer.
// Keeping the existing renderer id lets normal track validation retain it.
internal sealed class BridgeRenderer(string config, int port = 15556) : IRenderer {
    private static readonly SemaphoreSlim renderGate = new(1, 1);
    private readonly EnunuRenderer layoutRenderer = new();
    public USingerType SingerType => USingerType.Enunu;
    public bool SupportsRenderPitch => false; // No measured engine F0 is available.
    public override string ToString() => "ENUNU";
    public static readonly UExpressionDescriptor[] Expressions = [
        Curve("dynamics", "dyn", 64),
        Curve("brightness", "bri", 64),
        Curve("breathiness", "bre", 0),
        new("character", "chr", -64, 63, 0) { type = UExpressionType.Curve },
        new("pitch bend sensitivity", "pbs", 0, 24, 12) { type = UExpressionType.Curve },
        Curve("clearness", "cle", 0),
        Curve("air", "air", 0),
        new("exciter", "exc", -64, 63, 0) { type = UExpressionType.Curve },
        Curve("growl", "gwl", 0),
        Curve("portamento", "por", 64),
        Curve("opening", "ope", 127),
        new("accent", "acc", 0, 100, 50) { type = UExpressionType.Curve },
        new("decay", "dec", 0, 100, 50) { type = UExpressionType.Curve },
        new("velocity", "vel", 0, 127, 64),
    ];
    internal static readonly string[] LegacyExpressions = ["vdyn", "vpbs", "vcle", "vair", "vexc", "vgwl", "vpor", "vope", "vacc", "vdec"];
    private static UExpressionDescriptor Curve(string name, string abbr, int value) =>
        new(name, abbr, 0, 127, value) { type = UExpressionType.Curve };
    public bool SupportsExpression(UExpressionDescriptor descriptor) =>
        descriptor.abbr == "pitd" || Expressions.Any(exp => exp.abbr == descriptor.abbr);
    public UExpressionDescriptor[] GetSuggestedExpressions(USinger singer, URenderSettings settings) => Expressions;
    public RenderResult Layout(RenderPhrase phrase) => layoutRenderer.Layout(phrase);
    public RenderPitchResult LoadRenderedPitch(RenderPhrase phrase) => null!;

    // All curves are already immutable snapshots built by OpenUtau, sampled in
    // ticks every 5 ticks. Convert through the time axis to 5 ms engine frames.
    internal object CreateRequest(RenderPhrase phrase) {
        var layout = Layout(phrase);
        var startMs = layout.positionMs - layout.leadingMs;
        var frames = (int)Math.Round(layout.estimatedLengthMs / 5);
        var voice = JsonSerializer.Deserialize<Voice>(File.ReadAllText(Path.Combine(phrase.singer.Location, "bridge.voice.json")))!;
        var phones = phrase.phones;
        var notes = phones.Select(phone => new {
            position_ms = phone.positionMs - startMs,
            duration_ms = phone.durationMs,
            tone = phone.tone,
            lyric = phone.phoneme,
            velocity = Math.Clamp((int)Math.Round(phone.velocity * 100), 0, 127),
            expressions = new {
                opening = (int)Math.Round(Sample(Custom("ope"), phone.positionMs, 127)),
                accent = (int)Math.Round(Sample(Custom("acc"), phone.positionMs, 50)),
                decay = (int)Math.Round(Sample(Custom("dec"), phone.positionMs, 50)),
            },
        }).ToArray();
        float Sample(float[]? curve, double ms, float defaultValue) {
            if (curve is not { Length: > 0 }) return defaultValue;
            double index = (phrase.timeAxis.MsPosToTickPos(ms) - (phrase.position - phrase.leading)) / 5.0;
            index = Math.Clamp(index, 0, curve.Length - 1);
            int left = (int)index, right = Math.Min(left + 1, curve.Length - 1);
            return (float)(curve[left] + (curve[right] - curve[left]) * (index - left));
        }
        float[]? Custom(string abbr) => phrase.curves?.FirstOrDefault(c => c.Item1 == abbr)?.Item2;
        var controllers = new Dictionary<string, object>();
        void Controller(string name, float[]? curve, float defaultValue, int min = 0, int max = 127) {
            controllers[name] = new { frame_period_ms = 5, values = Enumerable.Range(0, frames)
                .Select(i => Math.Clamp((int)Math.Round(Sample(curve, startMs + i * 5, defaultValue)), min, max)).ToArray() };
        }
        Controller("brightness", Custom("bri"), 64);
        Controller("character", Custom("chr"), 0, -64, 63);
        Controller("breathiness", Custom("bre"), 0);
        Controller("clearness", Custom("cle"), 0);
        Controller("growl", Custom("gwl"), 0);
        Controller("air", Custom("air"), 0);
        Controller("exciter", Custom("exc"), 0, -64, 63);
        Controller("portamento", Custom("por"), 64);
        // Core converts DYN to linear gain before passing the phrase. Undo
        // that conversion to recover the backend's native 0..127 controller.
        var dynamics = phrase.dynamics?.Select(x => x <= 0 ? 0f : (float)(200 * Math.Log10(x))).ToArray();
        Controller("dynamics", dynamics, 64);
        var f0 = new double[frames];
        int phoneIndex = 0;
        for (int i = 0; i < frames; i++) {
            double ms = startMs + i * 5;
            while (phoneIndex < phones.Length && ms >= phones[phoneIndex].endMs) phoneIndex++;
            if (phoneIndex < phones.Length && ms >= phones[phoneIndex].positionMs) {
                double cents = Sample(phrase.pitches, ms, phones[phoneIndex].tone * 100);
                f0[i] = 440 * Math.Pow(2, (cents / 100 - 69) / 12);
            }
        }
        return new { protocol = 1, comp_id = voice.comp_id, lang_id = voice.lang_id, notes,
            pitch_curve = new { frame_period_ms = 5, f0, sensitivity = Enumerable.Range(0, frames)
                .Select(i => (int)Math.Round(Math.Clamp(Sample(Custom("pbs"), startMs + i * 5, 12), 0, 24))).ToArray() }, controller_curves = controllers };
    }
    private sealed class Voice {
        public string comp_id { get; set; } = "";
        public int lang_id { get; set; }
    }

    public Task<RenderResult> Render(RenderPhrase phrase, Progress progress, int trackNo,
            CancellationTokenSource cancellation, bool isPreRender, RenderPhraseEvents? events = null) {
        var token = cancellation.Token;
        return Task.Run(async () => {
        bool acquired = false;
        try {
            await renderGate.WaitAsync(token);
            acquired = true;
            token.ThrowIfCancellationRequested();
            var request = JsonSerializer.Serialize(CreateRequest(phrase));
            // Include both the complete expression payload and backend settings;
            // edits and backend changes must never reuse a stale waveform.
            var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes("2\n" + config + "\n" + File.ReadAllText(config) + "\n" + request))).ToLowerInvariant();
            var path = Path.Combine(PathManager.Inst.CachePath, "vbridge-" + key + ".wav");
            Directory.CreateDirectory(PathManager.Inst.CachePath);
            phrase.AddCacheFile(path);
            if (!File.Exists(path)) {
                if (!BackendReady()) throw new InvalidOperationException("桥接未启动，请打开 VOCALOID / Wine 设置并启动桥接。");
                var input = path + ".request.local.json";
                try {
                    File.WriteAllText(input, request);
                    using var socket = new RequestSocket();
                    socket.Options.Linger = TimeSpan.Zero;
                    socket.Connect($"tcp://127.0.0.1:{port}");
                    socket.SendFrame(JsonSerializer.Serialize(new[] { "render", input, path }));
                    using var settings = JsonDocument.Parse(File.ReadAllText(config));
                    int seconds = settings.RootElement.GetProperty("timeout_seconds").GetInt32() + 10;
                    var watch = Stopwatch.StartNew();
                    while (true) {
                        token.ThrowIfCancellationRequested();
                        if (socket.TryReceiveFrameString(TimeSpan.FromMilliseconds(100), out var text)) {
                            using var reply = JsonDocument.Parse(text);
                            var error = reply.RootElement.GetProperty("error");
                            if (error.ValueKind != JsonValueKind.Null) throw new InvalidOperationException(error.GetString());
                            break;
                        }
                        if (!BackendReady()) throw new InvalidOperationException("桥接已停止。");
                        if (watch.Elapsed.TotalSeconds > seconds) throw new TimeoutException("桥接渲染超时。");
                    }
                } finally { File.Delete(input); }
            }
            token.ThrowIfCancellationRequested();
            var result = Layout(phrase);
            result.samples = ReadWave(path);
            progress.Complete(phrase.phones.Length, $"Track {trackNo + 1}: VOCALOID");
            return result;
        } catch (OperationCanceledException) when (token.IsCancellationRequested) {
            // Match native ENUNU: superseded renders complete without audio.
            // Older Core waits synchronously and reports canceled Tasks as failures.
            return new RenderResult();
        } finally { if (acquired) renderGate.Release(); }
        });
    }

    private bool BackendReady() {
        try {
            using var state = JsonDocument.Parse(File.ReadAllText(config + ".service.local.json"));
            if (!state.RootElement.GetProperty("Ready").GetBoolean()) return false;
            using var process = Process.GetProcessById(state.RootElement.GetProperty("Pid").GetInt32());
            return !process.HasExited;
        } catch (IOException) { return false; }
          catch (JsonException) { return false; }
          catch (ArgumentException) { return false; }
          catch (InvalidOperationException) { return false; }
    }
    private static float[] ReadWave(string path) {
        using var reader = new BinaryReader(File.OpenRead(path));
        if (new string(reader.ReadChars(4)) != "RIFF") throw new InvalidDataException("Not a RIFF wave");
        reader.ReadUInt32();
        if (new string(reader.ReadChars(4)) != "WAVE") throw new InvalidDataException("Not a WAVE file");
        bool validFormat = false;
        while (reader.BaseStream.Position + 8 <= reader.BaseStream.Length) {
            string chunk = new(reader.ReadChars(4));
            uint size = reader.ReadUInt32();
            long end = reader.BaseStream.Position + size;
            if (end > reader.BaseStream.Length) throw new InvalidDataException("Truncated WAV");
            if (chunk == "fmt ") {
                if (size < 16 || reader.ReadUInt16() != 1 || reader.ReadUInt16() != 1 || reader.ReadUInt32() != 44100)
                    throw new InvalidDataException("Expected mono PCM at 44100 Hz");
                reader.ReadUInt32(); reader.ReadUInt16();
                if (reader.ReadUInt16() != 16) throw new InvalidDataException("Expected 16-bit PCM");
                validFormat = true;
            } else if (chunk == "data") {
                if (!validFormat || size % 2 != 0) throw new InvalidDataException("Invalid WAV data");
                var samples = new float[size / 2];
                for (int i = 0; i < samples.Length; i++) samples[i] = reader.ReadInt16() / 32768f;
                return samples;
            }
            reader.BaseStream.Position = end + size % 2;
        }
        throw new InvalidDataException("Missing WAV data");
    }
}
