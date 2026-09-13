"""Regression check for contributed Japanese support and existing Chinese descriptors."""
import json,subprocess,sys,tempfile
from pathlib import Path
from japanese import phonemes,aliases as japanese_aliases
from pinyin import aliases as pinyin_aliases
from worker import make_sequence

assert phonemes('ｻｸﾗ')==phonemes('サクラ')==phonemes('sakura')
assert phonemes("n'ya")=='n j a'
for lyric in ('ー','んー','っー','ーあ'):
    try:phonemes(lyric)
    except ValueError:pass
    else:raise AssertionError('Context-free long mark accepted: '+lyric)

def score(lyrics,lang=0,gap=False):
    return dict(protocol=1,comp_id='test',lang_id=lang,notes=[dict(position_ms=i*500+(500 if gap and i else 0),duration_ms=500,tone=60,lyric=lyric,velocity=64) for i,lyric in enumerate(lyrics)])
def phones(request):return [n['phoneme'] for n in make_sequence(request)['tracks'][0]['parts'][0]['notes']]
assert phones(score(['く','ー','-','ー']))==['k M','M','-','M']
assert phones(score(['ni3','hao3'],4))==['n i','x AU']
for request in (score(['ー']),score(['ん','ー']),score(['く','ー'],gap=True),score(['sa'],1)):
    try:make_sequence(request)
    except ValueError:pass
    else:raise AssertionError('Invalid language/long-mark context accepted')
request=score(['anything'],1);request['notes'][0]['phoneme']='s a'
assert phones(request)==['s a']

root=Path(__file__).resolve().parents[1]
def tables(spellings):return {'lyrics.table':'\n'.join(f'{x} {x}' for x in spellings)+'\n','phonemes.hed':'QS "phonemes" {'+','.join(f'*-{x}+*' for x in spellings)+'}\n'}
with tempfile.TemporaryDirectory() as tmp:
    data=Path(tmp);vf=data/'voices.json';vf.write_text(json.dumps({'voices':[{'name':'CN','comp_id':'cn','lang_id':4},{'name':'JP','comp_id':'jp','lang_id':0}]}))
    command=[sys.executable,str(root/'enunu/prepare_singers.py'),'--voices',str(vf),'--data-dir',str(data)]
    subprocess.run(command,check=True,capture_output=True)
    cn=data/'Singers/VOCALOID-Wine-CN';jp=data/'Singers/VOCALOID-Wine-JP'
    original={f:(cn/f).read_bytes() for f in tables(pinyin_aliases()+['-'])}
    assert 'ー ー' in (jp/'lyrics.table').read_text()
    assert 'さ さ' in (jp/'lyrics.table').read_text()
    assert 'ni3 ni3' not in (jp/'lyrics.table').read_text()
    meta=jp/'character.yaml';meta.write_text(meta.read_text()+'portrait: "custom.webp"\n');metadata=meta.read_bytes()
    # Both pre-merge Chinese-only tables and incoming mixed tables can be upgraded.
    incoming=pinyin_aliases()+[x for x in japanese_aliases() if x!='ー']+['-']
    for old in (pinyin_aliases()+['-'],incoming):
        for f,text in tables(old).items():(jp/f).write_text(text)
        subprocess.run(command+['--update'],check=True,capture_output=True)
        assert (jp/'lyrics.table').read_text()==tables(japanese_aliases()+['-'])['lyrics.table']
        assert meta.read_bytes()==metadata
        assert (jp/'lyrics.table.before-pinyin').exists()
        assert all((cn/f).read_bytes()==v for f,v in original.items())
    custom=jp/'lyrics.table';custom.write_text('custom custom\n')
    result=subprocess.run(command+['--update'],capture_output=True)
    assert result.returncode!=0 and custom.read_text()=='custom custom\n'
print('PASS: Japanese conversion/long-mark context, explicit other languages, unchanged Chinese tables, safe old/mixed table upgrades and custom portrait preservation')
