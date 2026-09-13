"""Compile both render entry points against small interface fixtures, not a real fork.
Run: python openutau-plugin/test_compatibility.py --dotnet /path/to/sdk/dotnet
"""
import argparse,subprocess,tempfile
from pathlib import Path
from xml.sax.saxutils import escape
p=argparse.ArgumentParser();p.add_argument('--dotnet',default='dotnet');p.add_argument('--openutau-dir',default='/opt/openutau');args=p.parse_args()
r=Path(__file__).resolve().parents[1];core=Path(args.openutau_dir).resolve()
with tempfile.TemporaryDirectory(prefix='renderer-interface-check-') as folder:
    for events in (False,True):
        test=Path(folder)/('new' if events else 'old');test.mkdir()
        const='OPENUTAU_RENDER_EVENTS' if events else ''
        (test/'Check.csproj').write_text(f'''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework><OutputType>Exe</OutputType><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable><NoWarn>0436</NoWarn><DefineConstants>{const}</DefineConstants></PropertyGroup><ItemGroup><Compile Include="{escape(str(r/'openutau-plugin/BridgeRenderer.cs'))}" Link="BridgeRenderer.cs"/><Reference Include="OpenUtau.Core"><HintPath>{escape(str(core/'OpenUtau.Core.dll'))}</HintPath></Reference><Reference Include="NetMQ"><HintPath>{escape(str(core/'NetMQ.dll'))}</HintPath></Reference></ItemGroup></Project>''')
        tail=', RenderPhraseEvents? events' if events else ''
        (test/'Interface.cs').write_text('''namespace OpenUtau.Core.Render;
public interface IRenderer {
 Task<RenderResult> Render(RenderPhrase phrase, Progress progress, int trackNo,
 System.Threading.CancellationTokenSource cancellation, bool isPreRender'''+tail+''');
}
''')
        # Reflection confirms the conditional build exposes only the intended entry points.
        expected='5,6' if events else '5'
        (test/'Program.cs').write_text('''using System.Reflection;
var counts=typeof(OpenUtau.Plugin.VocaloidBridge.BridgeRenderer).GetMethods(BindingFlags.Public|BindingFlags.Instance).Where(m=>m.Name=="Render").Select(m=>m.GetParameters().Length).OrderBy(n=>n);
if(string.Join(",",counts)!="'''+expected+'''")throw new Exception("Incorrect renderer overloads");
Console.WriteLine("PASS: renderer overloads '''+expected+'''");
''')
        result=subprocess.run([args.dotnet,'build',str(test/'Check.csproj'),'-c','Release'],capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        result=subprocess.run([args.dotnet,str(test/'bin/Release/net10.0/Check.dll')],capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        print(result.stdout.strip())
print('PASS: 5/6-parameter fixtures; this does not certify a specific fork')
