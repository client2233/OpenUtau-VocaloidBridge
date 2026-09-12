"""Windows worker. JSON requests on disk, JSON replies on stdout."""
import argparse
import copy
import json
import math
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.pinyin import phonemes


def make_sequence(request):
    """MVP: explicit VOCALOID phonemes, ms timing encoded at 120 BPM."""
    notes = request['notes']
    if not notes:
        raise ValueError('At least one note is required')
    template = Path(__file__).with_name('sequence.template.json')
    seq = json.loads(template.read_text(encoding='utf-8'))
    comp = request['comp_id']
    lang = request.get('lang_id', 4)
    seq['voices'] = [{'compID': comp, 'name': request.get('voice_name', comp)}]
    seq['masterTrack']['tempo']['global']['isEnabled'] = False
    seq['masterTrack']['tempo']['events'] = [{'pos': 0, 'value': 12000}]
    part = seq['tracks'][0]['parts'][0]
    part['pos'] = 0
    prototype = copy.deepcopy(part['notes'][0])
    part['voice'] = {'compID': comp, 'langID': lang}
    part['notes'] = []
    previous_end = 0
    for source in notes:
        position = round(source['position_ms'] * .96)
        # Quantize absolute endpoints together; rounding the duration separately
        # can make adjacent frame-based notes overlap by one tick.
        duration = round((source['position_ms'] + source['duration_ms']) * .96) - position
        tone = source['tone']
        phoneme = source.get('phoneme')
        if phoneme is None and lang == 4:
            phoneme = phonemes(source.get('lyric', ''))
        if position < previous_end or duration < 1 or not 0 <= tone <= 127:
            raise ValueError('Invalid or overlapping note timing/pitch')
        if not isinstance(phoneme, str) or not phoneme.strip():
            raise ValueError('An explicit VOCALOID phoneme is required')
        note = copy.deepcopy(prototype)
        note.update(pos=position, duration=duration, number=tone,
                    lyric=source.get('lyric', phoneme), phoneme=phoneme,
                    langID=lang, isProtected=True)
        note['vibrato'] = {'type': 0, 'duration': 0}
        note['singingSkill'] = {'duration': 0, 'weight': {'pre': 64, 'post': 64}}
        note['exp'] = {'accent': 50, 'decay': 50, 'bendDepth': 0,
                       'bendLength': 0, 'opening': 127}
        part['notes'].append(note)
        previous_end = position + duration
    part['duration'] = previous_end + 1920
    seq['masterTrack']['loop'] = {'isEnabled': False, 'begin': 0, 'end': part['duration']}
    curve = request.get('pitch_curve')
    if curve is not None:
        period = float(curve['frame_period_ms'])
        if not math.isfinite(period) or period <= 0:
            raise ValueError('Invalid pitch frame period')
        events = {}
        index = 0
        for frame, frequency in enumerate(curve['f0']):
            if not math.isfinite(frequency) or frequency < 0:
                raise ValueError('Invalid F0 value')
            position_tick = round(frame * period * .96)
            while index < len(notes) and position_tick >= part['notes'][index]['pos'] + part['notes'][index]['duration']:
                index += 1
            bend = 0
            if index < len(notes) and position_tick >= part['notes'][index]['pos'] and frequency > 0:
                deviation = 69 + 12 * math.log2(frequency / 440) - notes[index]['tone']
                bend = round(deviation / 12 * 8192)
                if not -8192 <= bend <= 8191:
                    raise ValueError('Pitch deviation exceeds 12-semitone range')
            events[position_tick] = bend
        part['controllers'] = [
            {'name': 'pitchBendSens', 'events': [{'pos': 0, 'value': 12}]},
            {'name': 'pitchBend', 'events': [{'pos': pos, 'value': value} for pos, value in sorted(events.items())]},
        ]
    return seq


def run(args):
    api = Path(args.api_dir).resolve()
    if not (api/'v6api/__init__.py').is_file():
        raise ValueError('The selected API directory must contain v6api/__init__.py')
    sys.path.insert(0,str(api))
    os.environ['VOCALOID_PATH'] = args.vocaloid_dir
    os.environ['VOCALOID_COMMON_PATH'] = args.common_dir
    from v6api import v6loader
    from v6api.VDM.VDM import VIS_VDM
    from v6api.VDM.VoiceBank import VIS_VoiceBank
    from v6api.DSE.DSE import VIS_DSE
    from v6api.VSM.VSM import VIS_VSM
    from v6api.VSM.Sequence import VIS_Sequence
    from v6api.VSM.Track import VIS_Track
    from v6api.VSM.Part import VIS_Part
    if not v6loader.set_dll_directory():
        raise RuntimeError('Cannot configure DLL directory')
    vdm, dse, vsm, seq = None, None, None, None
    initialized = False
    try:
        vdm = VIS_VDM()
        status = vdm.Create()
        if status.value != 0 or not vdm.GetPointer():
            raise RuntimeError(f'VDM initialization status {status.value}')
        if args.command == 'list':
            reader = VIS_VoiceBank()
            result = []
            count = vdm._VIS_VDM__get_VoiceBanks_Count(False)
            for index in range(count):
                handle = vdm._VIS_VDM__get_VoiceBank_ByIndex(index, False)
                result.append(dict(comp_id=reader.Get_CompID(handle),
                                   name=reader.Get_VoiceName(handle),
                                   lang_id=reader.Get_DefaultLangID(handle)))
            return dict(ok=True, protocol=1, voices=result)
        request = json.loads(Path(args.request).read_text(encoding='utf-8'))
        if request.get('protocol') != 1:
            raise ValueError('Unsupported protocol version')
        if not vdm.GetVoiceBankByCompID(request['comp_id'], False):
            raise ValueError('Traditional voicebank not available')
        score = make_sequence(request)
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        dse = VIS_DSE()
        if not dse.Create() or not dse.Initialize(vdm.GetPointer()):
            raise RuntimeError('DSE initialization failed')
        initialized = True
        vsm = VIS_VSM()
        if not vsm.Create() or not vsm.SetVDM(vdm.GetPointer()):
            raise RuntimeError('VSM initialization failed')
        if not vsm.SetDSE(dse.GetPointer()):
            raise RuntimeError('DSE manager binding failed')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'sequence.json'
            path.write_text(json.dumps(score, ensure_ascii=False), encoding='utf-8')
            ptr = vsm.OpenSequenceVSQX(str(path))
            if not ptr:
                raise RuntimeError(f'Open sequence failed: {vsm.LastError()}')
            seq = VIS_Sequence(ptr)
            track = VIS_Track(seq.Get_Track(0))
            part = VIS_Part(track.Get_Part(0))
            status = part.Render(str(output))
            if status != 0 or not output.is_file():
                raise RuntimeError(f'Render failed: {status}')
        return dict(ok=True, protocol=1, output=str(output))
    finally:
        if seq is not None:
            seq.CloseSequence()
        if vsm is not None and vsm.GetPointer():
            vsm.Destroy()
        if dse is not None and dse.GetPointer():
            if initialized:
                dse.Terminate()
            dse.Destroy()
        if vdm is not None and vdm.GetPointer():
            vdm.Destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['list', 'render'])
    parser.add_argument('--api-dir', required=True)
    parser.add_argument('--vocaloid-dir', required=True)
    parser.add_argument('--common-dir', required=True)
    parser.add_argument('--request')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=True), flush=True)
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps(dict(ok=False, error=str(error))), flush=True)
        sys.exit(1)
