using OpenUtau.Core;
using OpenUtau.Core.Ustx;

namespace OpenUtau.Plugin.VocaloidBridge;

// Activate only after opening this plugin. No global renderer replacement,
// no reflection, and no replacement of unrelated ENUNU voicebanks.
internal sealed class BridgeAttachment(string config, DocManager manager) : ICmdSubscriber {
    private static readonly Dictionary<string, BridgeAttachment> active = new();
    private readonly BridgeRenderer renderer = new(config);
    private UProject? preparedProject;
    private bool pending;

    internal static void Enable(string config, DocManager manager) {
        if (!active.TryGetValue(config, out var attachment)) {
            attachment = new BridgeAttachment(config, manager);
            active.Add(config, attachment);
            manager.AddSubscriber(attachment);
        }
        attachment.Attach();
    }
    public void OnNext(UCommand command, bool isUndo) {
        // Queue changes outside command publication/validation and coalesce the
        // command burst. A new singer/loaded project can need activation too.
        if (pending) return;
        pending = true;
        manager.PostOnUIThread(() => {
            pending = false;
            Attach();
        });
    }
    private void Attach() {
        var project = manager.Project;
        bool changed = false;
        foreach (var track in project.tracks) {
            bool owned = track.Singer is { Found: true, SingerType: USingerType.Enunu } singer
                && track.RendererSettings.renderer == "ENUNU"
                && File.Exists(Path.Combine(singer.Location, "bridge.voice.json"));
            if (owned && track.RendererSettings.Renderer != renderer) {
                track.RendererSettings.Renderer = renderer;
                changed = true;
            } else if (!owned && track.RendererSettings.Renderer == renderer) {
                // Singer changes within the same ENUNU renderer id otherwise
                // retain this object during normal URenderSettings validation.
                track.RendererSettings.Renderer = new OpenUtau.Core.Enunu.EnunuRenderer();
                changed = true;
            }
        }
        if (project.tracks.Any(t => t.RendererSettings.Renderer == renderer) && preparedProject != project) {
            preparedProject = project;
            // Replace matching abbreviations and retire the old V-prefixed
            // duplicates. Keep unrelated native/custom expressions intact.
            var definitions = project.expressions.Values
                .Where(e => !BridgeRenderer.LegacyExpressions.Contains(e.abbr)
                    && !BridgeRenderer.Expressions.Any(x => x.abbr == e.abbr))
                .Concat(BridgeRenderer.Expressions.Select(e => e.Clone())).ToArray();
            manager.StartUndoGroup();
            manager.ExecuteCmd(new ConfigureExpressionsCommand(project, definitions));
            manager.EndUndoGroup();
            changed = true;
        }
        if (changed) {
            manager.ExecuteCmd(new ValidateProjectNotification());
            manager.ExecuteCmd(new PreRenderNotification());
        }
    }
}
