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
        velocity = source.get('velocity', 64)
        if not isinstance(velocity, (int, float)) or not math.isfinite(velocity) or not 0 <= velocity <= 127:
            raise ValueError('Invalid note velocity')
        note['velocity'] = round(velocity)
        note['vibrato'] = {'type': 0, 'duration': 0}
        note['singingSkill'] = {'duration': 0, 'weight': {'pre': 64, 'post': 64}}
        note['exp'] = {'accent': 50, 'decay': 50, 'bendDepth': 0,
                       'bendLength': 0, 'opening': 127}
        for name, limits in {'opening': (0, 127), 'accent': (0, 100), 'decay': (0, 100)}.items():
            value = source.get('expressions', {}).get(name, note['exp'][name])
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not limits[0] <= value <= limits[1]:
                raise ValueError('Invalid note expression: ' + name)
            note['exp'][name] = round(value)
        if set(source.get('expressions', {})) - {'opening', 'accent', 'decay'}:
            raise ValueError('Unsupported note expression')
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
        sensitivity = curve.get('sensitivity', 12)
        sensitivities = sensitivity if isinstance(sensitivity, list) else [sensitivity] * len(curve['f0'])
        if len(sensitivities) != len(curve['f0']):
            raise ValueError('PBS/F0 frame counts differ')
        pbs_events = {}
        previous_pbs = None
        index = 0
        for frame, frequency in enumerate(curve['f0']):
            if not math.isfinite(frequency) or frequency < 0:
                raise ValueError('Invalid F0 value')
            pbs = sensitivities[frame]
            if not isinstance(pbs, (int, float)) or not math.isfinite(pbs) or not 0 <= pbs <= 24 or pbs != round(pbs):
                raise ValueError('Invalid pitch bend sensitivity')
            position_tick = round(frame * period * .96)
            if pbs != previous_pbs:
                pbs_events[position_tick] = pbs
                previous_pbs = pbs
            while index < len(notes) and position_tick >= part['notes'][index]['pos'] + part['notes'][index]['duration']:
                index += 1
            bend = 0
            if index < len(notes) and position_tick >= part['notes'][index]['pos'] and frequency > 0:
                deviation = 69 + 12 * math.log2(frequency / 440) - notes[index]['tone']
                if pbs == 0 and abs(deviation) > .0001:
                    raise ValueError('PBS 0 cannot represent the edited pitch deviation')
                bend = round(deviation / pbs * 8192) if pbs else 0
                if not -8192 <= bend <= 8191:
                    raise ValueError('Pitch deviation exceeds the selected PBS range')
            events[position_tick] = bend
        part['controllers'] = [
            {'name': 'pitchBendSens', 'events': [{'pos': pos, 'value': value} for pos, value in sorted(pbs_events.items())]},
            {'name': 'pitchBend', 'events': [{'pos': pos, 'value': value} for pos, value in sorted(events.items())]},
        ]
    # Typed controller curves, independent of the optional pitch curve.
    controllers = part.setdefault('controllers', [])
    limits = {name: (0, 127) for name in ('brightness', 'breathiness', 'clearness',
              'growl', 'portamento', 'dynamics', 'air')}
    limits.update(character=(-64, 63), exciter=(-64, 63))
    for name, data in request.get('controller_curves', {}).items():
        if name not in limits:
            raise ValueError('Unsupported controller: ' + name)
        period = float(data['frame_period_ms'])
        if not math.isfinite(period) or period <= 0:
            raise ValueError('Invalid controller frame period')
        events = {}
        previous = None
        for frame, value in enumerate(data['values']):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not limits[name][0] <= value <= limits[name][1]:
                raise ValueError('Invalid controller value: ' + name)
            value = round(value)
            if value != previous:
                events[round(frame * period * .96)] = value
                previous = value
        if not events:
            raise ValueError('Empty controller curve: ' + name)
        controllers.append({'name': name, 'events': [
            {'pos': pos, 'value': value} for pos, value in sorted(events.items())]})
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
