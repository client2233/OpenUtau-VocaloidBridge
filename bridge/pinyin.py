"""Single-syllable Mandarin pinyin -> VOCALOID Chinese phonemes.

Symbols: Yamaha VOCALOID6 Reference Manual, Chinese phonetic table, pp.86-88.
https://rsc-net.vocaloid.com/assets/pdf_files/bb/VOCALOID_Reference_Manual_ENG.pdf
No lexical tones are imposed: the score and its pitch curve control sung pitch.
"""
import unicodedata

INITIALS = dict(zip(
    'b p m f d t n l g k h j q x zh ch sh r z c s'.split(),
    r'p p_h m f t t_h n l k k_h x ts\ ts\_h s\ ts` ts`_h s` z` ts ts_h s'.split()))
FINALS = dict(zip(
    'a o e i u v er ai ei ao ou ia ie ua uo ve iao iou uai uei an en in ian uan uen vn van ang eng ing iang uang ueng ong iong'.split(),
    'a o 7 i u y @` aI ei AU @U ia iE_r ua uo yE_r iAU i@U uaI uei a_n @_n i_n iE_n ua_n u@_n y_n y{_n AN @N iN iAN uAN u@N UN iUN'.split()))
# Explicit syllable inventory rejects impossible initial/final combinations.
GROUPS = {
    '': 'a ai an ang ao e ei en er o ou',
    'b': 'a ai an ang ao ei en eng i ian iao ie in ing o u',
    'p': 'a ai an ang ao ei en eng i ian iao ie in ing o ou u',
    'm': 'a ai an ang ao e ei en eng i ian iao ie in ing iu o ou u',
    'f': 'a an ang ei en eng o ou u',
    'd': 'a ai an ang ao e ei en eng i ia ian iao ie ing iu ong ou u uan ui un uo',
    't': 'a ai an ang ao e eng i ian iao ie ing ong ou u uan ui un uo',
    'n': 'a ai an ang ao e ei en eng i ian iang iao ie in ing iu ong ou u uan uo v ve',
    'l': 'a ai an ang ao e ei eng i ia ian iang iao ie in ing iu ong ou u uan un uo v ve',
    'g': 'a ai an ang ao e ei en eng ong ou u ua uai uan uang ui un uo',
    'k': 'a ai an ang ao e ei en eng ong ou u ua uai uan uang ui un uo',
    'h': 'a ai an ang ao e ei en eng ong ou u ua uai uan uang ui un uo',
    'j': 'i ia ian iang iao ie in ing iong iu u uan ue un',
    'q': 'i ia ian iang iao ie in ing iong iu u uan ue un',
    'x': 'i ia ian iang iao ie in ing iong iu u uan ue un',
    'zh': 'a ai an ang ao e ei en eng i ong ou u ua uai uan uang ui un uo',
    'ch': 'a ai an ang ao e en eng i ong ou u ua uai uan uang ui un uo',
    'sh': 'a ai an ang ao e ei en eng i ou u ua uai uan uang ui un uo',
    'r': 'an ang ao e en eng i ong ou u ua uan ui un uo',
    'z': 'a ai an ang ao e ei en eng i ong ou u uan ui un uo',
    'c': 'a ai an ang ao e en eng i ong ou u uan ui un uo',
    's': 'a ai an ang ao e en eng i ong ou u uan ui un uo',
    'y': 'a an ang ao e i in ing ong ou u uan ue un',
    'w': 'a ai an ang ei en eng o u',
}
SYLLABLES = {initial + final for initial, finals in GROUPS.items() for final in finals.split()}
# Standalone eng is excluded: this Luo Tianyi bank returned silence for @N alone.
# Standalone i/u are useful vowel-only lyrics, as in the original prototype.
SYLLABLES.update(('i', 'u', 'v'))


def normalize(lyric):
    text = lyric.strip().lower().replace('u:', 'v').replace('ü', 'v')
    text = unicodedata.normalize('NFD', text).replace('u\u0308', 'v')
    text = ''.join(ch for ch in text
                   if not unicodedata.combining(ch))
    if text and text[-1] in '012345':
        text = text[:-1]
    return text


def phonemes(lyric):
    syllable = normalize(lyric)
    if syllable not in SYLLABLES:
        raise ValueError('Unsupported pinyin syllable: ' + lyric)
    initial = next((x for x in sorted(GROUPS, key=len, reverse=True)
                    if x and syllable.startswith(x)), '')
    final = syllable[len(initial):]
    if initial == 'y':
        final = {'i':'i', 'in':'in', 'ing':'ing', 'u':'v', 'ue':'ve',
                 'uan':'van', 'un':'vn', 'ong':'iong', 'ou':'iou'}.get(final, 'i' + final)
        initial = ''
    elif initial == 'w':
        final = {'u':'u', 'ei':'uei', 'en':'uen', 'eng':'ueng'}.get(final, 'u' + final)
        initial = ''
    elif initial in ('j', 'q', 'x') and final.startswith('u'):
        final = 'v' + final[1:]
    final = {'iu':'iou', 'ui':'uei', 'un':'uen'}.get(final, final)
    if final == 'i' and initial in ('z', 'c', 's'):
        vowel = 'i\\'
    elif final == 'i' and initial in ('zh', 'ch', 'sh', 'r'):
        vowel = 'i`'
    else:
        vowel = FINALS[final]
    return ' '.join(filter(None, (INITIALS.get(initial), vowel)))


def aliases():
    """ASCII aliases survive the stock ENUNU renderer's Shift-JIS UST transport."""
    result = set()
    for syllable in SYLLABLES:
        spellings = {syllable}
        if 'v' in syllable:
            spellings.add(syllable.replace('v', 'u:'))
        for spelling in spellings:
            for tone in ('', '0', '1', '2', '3', '4', '5'):
                result.add(spelling + tone)
    return sorted(result)


if __name__ == '__main__':
    expected = {'ni':'n i', 'hao':'x AU', 'shi':'s` i`', 'zi':'ts i\\',
                'jie':r'ts\ iE_r', 'xue':r's\ yE_r', 'yuan':'y{_n',
                'yun':'y_n', 'ju':'ts\\ y', 'nv':'n y', 'liu':'l i@U',
                'gui':'k uei', 'wen':'u@_n', 'yong':'iUN', 'er':'@`'}
    for lyric, expected in expected.items():
        assert phonemes(lyric) == expected, (lyric, phonemes(lyric), expected)
    assert phonemes('nǚ3') == phonemes('NU:3') == phonemes('nv')
    for lyric in aliases():
        assert phonemes(lyric)
    for invalid in ('hello', 'ni hao', 'biong', 'ni6', '', '你'):
        try: phonemes(invalid)
        except ValueError: pass
        else: raise AssertionError('Invalid syllable accepted: ' + invalid)
    print(f'PASS: {len(SYLLABLES)} syllables, {len(aliases())} ASCII aliases, contextual vowels and invalid inputs')
