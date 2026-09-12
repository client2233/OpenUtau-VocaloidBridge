using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using OpenUtau.Classic;
using OpenUtau.Core;
using OpenUtau.Core.Enunu;
using OpenUtau.Core.Render;
using OpenUtau.Core.Ustx;

static class ExpressionSmoke {
    public static void Run(string dll, string config, string root, int port, string voiceFile) {
        System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance);
        DocManager.Inst.PostOnUIThread = _ => { };
        typeof(DocManager).GetField("mainScheduler", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(DocManager.Inst, TaskScheduler.Default);
        var type = AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.GetFullPath(dll))
            .GetType("OpenUtau.Plugin.VocaloidBridge.BridgeRenderer", true)!;
        var renderer = (IRenderer)Activator.CreateInstance(type, config, port)!;
        var project = new UProject();
        OpenUtau.Core.Format.Ustx.AddDefaultExpressions(project);
        foreach (var exp in renderer.GetSuggestedExpressions(null!, null!)) project.RegisterExpression(exp);
        project.tempos.Clear(); project.tempos.Add(new UTempo { position = 0, bpm = 120 });
        project.tempos.Add(new UTempo { position = 2640, bpm = 90 });
        project.timeAxis.BuildSegments(project);
        var location = Path.Combine(root, "singer"); Directory.CreateDirectory(location);
        File.WriteAllText(Path.Combine(location, "character.txt"), "");
        File.WriteAllText(Path.Combine(location, "character.yaml"), "name: Test\nsinger_type: enunu\ntext_file_encoding: utf-8\n");
        File.WriteAllText(Path.Combine(location, "enuconfig.yaml"), "feature_type: melf0\nsample_rate: 44100\nframe_period: 5\ntable_path: lyrics.table\nquestion_path: phonemes.hed\nextensions:\n  wav_synthesizer: synthe\n");
        File.WriteAllText(Path.Combine(location, "lyrics.table"), "ni3 ni3\n");
        File.WriteAllText(Path.Combine(location, "phonemes.hed"), "QS \"phonemes\" {*-ni3+*}\n");
        File.Copy(voiceFile, Path.Combine(location, "bridge.voice.json"), true);
        var singer = new EnunuSinger(new Voicebank { File = Path.Combine(location, "character.txt"), BasePath = root, Name = "Test", SingerType = USingerType.Enunu });
        singer.EnsureLoaded();
        var track = new UTrack { Singer = singer, RendererSettings = new URenderSettings { renderer = "ENUNU", Renderer = renderer } };
        project.tracks.Add(track);
        var part = new UVoicePart { position = 1920, trackNo = 0 };
        var note = project.CreateNote(60,480,480); note.lyric = "ni3";
        note.ExtendedDuration = 480; note.phonemeIndexes = [0];
        part.notes.Add(note); project.parts.Add(part);
        note.SetExpression(project, track, "vel", [130f]);
        note.Validate(new ValidateOptions(), project, track, part);
        var phone = new UPhoneme { position = 480, phoneme = "ni3", Parent = note };
        phone.Validate(new ValidateOptions(), project, track, part, note);
        if (phone.Error) throw new Exception("Fixture phone validation failed");
        part.phonemes.Add(phone);
        void Curve(string abbr, int value) {
            part.curves.RemoveAll(c => c.abbr == abbr);
            part.curves.Add(new UCurve(project.expressions[abbr]) { xs = [480,960], ys = [value,value] });
        }
        note.SetExpression(project, track, "gen", [10f]);note.SetExpression(project, track, "bre", [10f]);
        Curve("tenc",100); Curve("genc",40); Curve("brec",40);Curve("vpbs",6); Curve("vdyn",90);
        Curve("vcle",50); Curve("vgwl",30); Curve("vpor",70);
        Curve("vair",40); Curve("vexc",20);
        Curve("vope",100); Curve("vacc",20); Curve("vdec",80);
        RenderPhrase Phrase() => (RenderPhrase)typeof(RenderPhrase).GetConstructors(BindingFlags.Instance | BindingFlags.NonPublic)
            .Single(c => c.GetParameters().Length == 4).Invoke([project, track, part, part.phonemes]);
        JsonDocument Payload(RenderPhrase phrase) => JsonDocument.Parse(JsonSerializer.Serialize(
            type.GetMethod("CreateRequest", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(renderer, [phrase])));
        var phrase = Phrase();
        using var data = Payload(phrase);
        var first = data.RootElement.GetProperty("notes")[0];
        if (first.GetProperty("velocity").GetInt32() != 83) throw new Exception("VEL was quantized by UST");
        if (Math.Abs(first.GetProperty("duration_ms").GetDouble() - phone.DurationMs) > .001) throw new Exception("Tempo map was lost");
        int frame = (int)Math.Round(first.GetProperty("position_ms").GetDouble() / 5);
        var curves = data.RootElement.GetProperty("controller_curves");
        foreach (var (name,value) in new (string,int)[] {("brightness",127),("character",-32),("breathiness",64),("dynamics",90),
            ("clearness",50),("growl",30),("portamento",70),("air",40),("exciter",20)}) {
            if (curves.GetProperty(name).GetProperty("values")[frame].GetInt32() != value) throw new Exception("Incorrect curve: " + name);
        }
        if (first.GetProperty("expressions").GetProperty("opening").GetInt32() != 100) throw new Exception("Opening not forwarded");
        if(data.RootElement.GetProperty("pitch_curve").GetProperty("sensitivity")[frame].GetInt32()!=6) throw new Exception("PBS curve missing");
        var f0 = data.RootElement.GetProperty("pitch_curve").GetProperty("f0");
        if (f0[0].GetDouble() != 0 || Math.Abs(f0[frame].GetDouble()-261.625565) > .01) throw new Exception("Pitch alignment failed");
        using var cancellation = new CancellationTokenSource();
        var audio = renderer.Render(phrase, new Progress(1), 0, cancellation, false).GetAwaiter().GetResult();
        if (audio.samples.Length != (int)Math.Round(f0.GetArrayLength()*5.0/1000*44100) || !audio.samples.Any(x=>Math.Abs(x)>.001)) throw new Exception("Invalid render result");
        var cached = renderer.Render(phrase, new Progress(1), 0, cancellation, false).GetAwaiter().GetResult();
        if (!audio.samples.SequenceEqual(cached.samples)) throw new Exception("Cache changed waveform");
        note.SetExpression(project, track, "vol", [50f]);
        var quieter = renderer.Render(Phrase(), new Progress(1), 0, cancellation, false).GetAwaiter().GetResult();
        if (!quieter.samples.SequenceEqual(audio.samples.Select(x=>x*.5f))) throw new Exception("VOL output gain failed");
        Curve("tenc",-100);
        var changed = renderer.Render(Phrase(), new Progress(1), 0, cancellation, false).GetAwaiter().GetResult();
        if (changed.samples.SequenceEqual(quieter.samples)) throw new Exception("BRI edit reused stale cache");
        File.WriteAllText(config + ".service.local.json", JsonSerializer.Serialize(new { Ready = false, Pid = 0 }));
        Curve("tenc",0);
        var watch = System.Diagnostics.Stopwatch.StartNew();
        try { renderer.Render(Phrase(), new Progress(1), 0, cancellation, false).GetAwaiter().GetResult(); throw new Exception("Stopped bridge accepted uncached request"); }
        catch (InvalidOperationException) { if (watch.Elapsed.TotalSeconds > 2) throw new Exception("Stopped bridge blocked render"); }
        if (part.notes.Count!=1 || note.position!=480 || note.duration!=480 || note.lyric!="ni3") throw new Exception("Renderer changed notes");
        // Verify the same public attachment path used by the menu on a real
        // manager, with no parts needing a phonemizer background worker.
        var manager = DocManager.Inst;
        typeof(DocManager).GetField("mainThread", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(manager, Thread.CurrentThread);
        var queue = new System.Collections.Concurrent.ConcurrentQueue<Action>();
        manager.PostOnUIThread = action => queue.Enqueue(action);
        void Pump() { int i=0; while(queue.TryDequeue(out var action)) { if (++i>100) throw new Exception("Attachment notification loop"); action(); } }
        var active = manager.Project;
        OpenUtau.Core.Format.Ustx.AddDefaultExpressions(active);
        var owned = new UTrack { Singer=singer, RendererSettings=new URenderSettings { renderer="ENUNU", Renderer=new EnunuRenderer() } };
        var foreignLocation=Path.Combine(root,"foreign");Directory.CreateDirectory(foreignLocation);
        foreach(var file in Directory.EnumerateFiles(location).Where(p=>Path.GetFileName(p)!="bridge.voice.json"))
            File.Copy(file,Path.Combine(foreignLocation,Path.GetFileName(file)),true);
        var foreignSinger = new EnunuSinger(new Voicebank { File=Path.Combine(foreignLocation,"character.txt"),BasePath=root,Name="Foreign",SingerType=USingerType.Enunu });
        foreignSinger.EnsureLoaded();
        var foreign = new UTrack { Singer=foreignSinger,RendererSettings=new URenderSettings { renderer="ENUNU",Renderer=new EnunuRenderer() } };
        active.tracks.Add(owned);active.tracks.Add(foreign);
        var attachment = type.Assembly.GetType("OpenUtau.Plugin.VocaloidBridge.BridgeAttachment",true)!;
        attachment.GetMethod("Enable",BindingFlags.Static|BindingFlags.NonPublic)!.Invoke(null,[config,manager]);Pump();
        if(owned.RendererSettings.Renderer.GetType()!=type || foreign.RendererSettings.Renderer.GetType()!=typeof(EnunuRenderer))
            throw new Exception("Attachment replaced an unrelated renderer or failed to activate");
        if(renderer.GetSuggestedExpressions(singer,owned.RendererSettings).Any(e=>!active.expressions.ContainsKey(e.abbr)))
            throw new Exception("Expression definitions not installed");
        manager.Undo();Pump();
        if(active.expressions.ContainsKey("vcle")) throw new Exception("Expression installation fought undo");
        manager.Redo();Pump();
        if(!active.expressions.ContainsKey("vcle")) throw new Exception("Expression redo failed");
        var added = new UTrack { Singer=singer,RendererSettings=new URenderSettings { renderer="ENUNU",Renderer=new EnunuRenderer() } };
        active.tracks.Add(added);manager.ExecuteCmd(new ValidateProjectNotification());Pump();
        if(added.RendererSettings.Renderer.GetType()!=type) throw new Exception("New bridge track was not attached");
        added.Singer=foreignSinger;manager.ExecuteCmd(new ValidateProjectNotification());Pump();
        if(added.RendererSettings.Renderer.GetType()!=typeof(EnunuRenderer)) throw new Exception("Switching to foreign singer retained bridge renderer");
        Console.WriteLine("PASS: public renderer attachment, foreign-track isolation, expression undo/redo and new-track activation");
        Console.WriteLine("PASS: installed Core builds native phrases with all controller/note curves, precise VEL, tempo map and aligned pitch");
        Console.WriteLine("PASS: full socket rendering, WAV size, cache reuse/invalidation, VOL gain and stopped-backend failure");
    }
}
