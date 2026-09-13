"""Experimental Japanese kana / romaji conversion contributed through a user archive.

The contributor reports testing a traditional Japanese voicebank; maintainers
have not independently verified every symbol or a full Japanese backend render.
No editor, API, voicebank or extracted score is included here.
"""
import unicodedata

_KANA = {
    'あ': 'a', 'い': 'i', 'う': 'M', 'え': 'e', 'お': 'o',
    'か': 'k a', 'き': "k' i", 'く': 'k M', 'け': 'k e', 'こ': 'k o',
    'さ': 's a', 'し': 'S i', 'す': 's M', 'せ': 's e', 'そ': 's o',
    'た': 't a', 'ち': 'tS i', 'つ': 'ts M', 'て': 't e', 'と': 't o',
    'な': 'n a', 'に': 'J i', 'ぬ': 'n M', 'ね': 'n e', 'の': 'n o',
    'は': 'h a', 'ひ': 'C i', 'ふ': 'p\\ M', 'へ': 'h e', 'ほ': 'h o',
    'ま': 'm a', 'み': "m' i", 'む': 'm M', 'め': 'm e', 'も': 'm o',
    'や': 'j a', 'ゆ': 'j M', 'よ': 'j o',
    'ら': '4 a', 'り': "4' i", 'る': '4 M', 'れ': '4 e', 'ろ': '4 o',
    'わ': 'w a',
    'が': 'g a', 'ぎ': "g' i", 'ぐ': 'g M', 'げ': 'g e', 'ご': 'g o',
    'ざ': 'dz a', 'じ': 'dZ i', 'ず': 'dz M', 'ぜ': 'dz e', 'ぞ': 'dz o',
    'だ': 'd a', 'ぢ': "d' i", 'づ': 'd M', 'で': 'd e', 'ど': 'd o',
    'ば': 'b a', 'び': "b' i", 'ぶ': 'b M', 'べ': 'b e', 'ぼ': 'b o',
    'ぱ': 'p a', 'ぴ': "p' i", 'ぷ': 'p M', 'ぺ': 'p e', 'ぽ': 'p o',
    'きゃ': "k' j a", 'きゅ': "k' j M", 'きょ': "k' j o",
    'しゃ': 'S j a', 'しゅ': 'S j M', 'しょ': 'S j o',
    'ちゃ': 'tS j a', 'ちゅ': 'tS j M', 'ちょ': 'tS j o',
    'にゃ': 'J j a', 'にゅ': 'J j M', 'にょ': 'J j o',
    'ひゃ': 'C j a', 'ひゅ': 'C j M', 'ひょ': 'C j o',
    'みゃ': "m' j a", 'みゅ': "m' j M", 'みょ': "m' j o",
    'りゃ': "4' j a", 'りゅ': "4' j M", 'りょ': "4' j o",
    'ぎゃ': "g' j a", 'ぎゅ': "g' j M", 'ぎょ': "g' j o",
    'じゃ': 'dZ j a', 'じゅ': 'dZ j M', 'じょ': 'dZ j o',
    'びゃ': "b' j a", 'びゅ': "b' j M", 'びょ': "b' j o",
    'ぴゃ': "p' j a", 'ぴゅ': "p' j M", 'ぴょ': "p' j o",
    'ん': 'n', 'っ': 'k', 'を': 'w o',
}

_SMALL = {'ぁ': 'a', 'ぃ': 'i', 'ぅ': 'M', 'ぇ': 'e', 'ぉ': 'o',
          'ゃ': 'j a', 'ゅ': 'j M', 'ょ': 'j o'}


def _katakana(kana):
    return ''.join(chr(ord(char) + 0x60) for char in kana)


_KANA.update({_katakana(kana): phoneme for kana, phoneme in _KANA.items()})
_SMALL.update({_katakana(kana): phoneme for kana, phoneme in _SMALL.items()})

_ROMAJI = {
    'a': 'a', 'i': 'i', 'u': 'M', 'e': 'e', 'o': 'o',
    'ka': 'k a', 'ki': "k' i", 'ku': 'k M', 'ke': 'k e', 'ko': 'k o',
    'sa': 's a', 'shi': 'S i', 'su': 's M', 'se': 's e', 'so': 's o',
    'ta': 't a', 'chi': 'tS i', 'tsu': 'ts M', 'te': 't e', 'to': 't o',
    'na': 'n a', 'ni': 'J i', 'nu': 'n M', 'ne': 'n e', 'no': 'n o',
    'ha': 'h a', 'hi': 'C i', 'fu': 'p\\ M', 'hu': 'p\\ M', 'he': 'h e', 'ho': 'h o',
    'ma': 'm a', 'mi': "m' i", 'mu': 'm M', 'me': 'm e', 'mo': 'm o',
    'ya': 'j a', 'yu': 'j M', 'yo': 'j o',
    'ra': '4 a', 'ri': "4' i", 'ru': '4 M', 're': '4 e', 'ro': '4 o',
    'wa': 'w a', 'wo': 'w o',
    'ga': 'g a', 'gi': "g' i", 'gu': 'g M', 'ge': 'g e', 'go': 'g o',
    'za': 'dz a', 'ji': 'dZ i', 'zu': 'dz M', 'ze': 'dz e', 'zo': 'dz o',
    'da': 'd a', 'di': "d' i", 'du': 'd M', 'de': 'd e', 'do': 'd o',
    'ba': 'b a', 'bi': "b' i", 'bu': 'b M', 'be': 'b e', 'bo': 'b o',
    'pa': 'p a', 'pi': "p' i", 'pu': 'p M', 'pe': 'p e', 'po': 'p o',
    'kya': "k' j a", 'kyu': "k' j M", 'kyo': "k' j o",
    'sha': 'S j a', 'shu': 'S j M', 'sho': 'S j o',
    'cha': 'tS j a', 'chu': 'tS j M', 'cho': 'tS j o',
    'nya': 'J j a', 'nyu': 'J j M', 'nyo': 'J j o',
    'hya': 'C j a', 'hyu': 'C j M', 'hyo': 'C j o',
    'mya': "m' j a", 'myu': "m' j M", 'myo': "m' j o",
    'rya': "4' j a", 'ryu': "4' j M", 'ryo': "4' j o",
    'gya': "g' j a", 'gyu': "g' j M", 'gyo': "g' j o",
    'ja': 'dZ j a', 'ju': 'dZ j M', 'jo': 'dZ j o',
    'bya': "b' j a", 'byu': "b' j M", 'byo': "b' j o",
    'pya': "p' j a", 'pyu': "p' j M", 'pyo': "p' j o",
    'n': 'n', 'nn': 'n', 'c': 'k',
}

_DOUBLED = set('kgtsdhbpmrzjc')

_VOWELS = set('a i M e o'.split())

def _emit(parts, phoneme):
    parts.extend(phoneme.split() if phoneme else [])


def _parse_kana(text):
    parts = []
    index = 0
    while index < len(text):
        pair = text[index:index + 2]
        if pair in _KANA:
            _emit(parts, _KANA[pair])
            index += 2
            continue
        char = text[index]
        if char in _KANA:
            _emit(parts, _KANA[char])
            index += 1
            continue
        if char in _SMALL:
            _emit(parts, _SMALL[char])
            index += 1
            continue
        if char == 'ー':
            if not parts or parts[-1] not in _VOWELS:
                raise ValueError('Japanese long mark must follow a vowel')
            parts.append(parts[-1])
            index += 1
            continue
        if char in '、。・！？　 .'.replace(' ', ''):
            index += 1
            continue
        raise ValueError('Unsupported Japanese kana: ' + char)
    if not parts:
        raise ValueError('Empty Japanese lyric')
    return ' '.join(parts)


def _parse_romaji(text):
    text = text.lower().replace('-', '')
    parts = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "'":
            index += 1
            continue
        if index + 1 < length and char == text[index + 1] and char in _DOUBLED:
            _emit(parts, 'k')
            index += 1
            continue
        three = text[index:index + 3]
        two = text[index:index + 2]
        if three in _ROMAJI:
            _emit(parts, _ROMAJI[three])
            index += 3
        elif two in _ROMAJI:
            _emit(parts, _ROMAJI[two])
            index += 2
        elif char in _ROMAJI:
            _emit(parts, _ROMAJI[char])
            index += 1
        else:
            raise ValueError('Unsupported romaji syllable: ' + text)
    if not parts:
        raise ValueError('Empty Japanese lyric')
    return ' '.join(parts)


def phonemes(lyric):
    text = unicodedata.normalize('NFKC', lyric.strip())
    if any('\u3040' <= char <= '\u30ff' for char in text):
        return _parse_kana(text)
    return _parse_romaji(text)


def aliases():
    spellings = set()
    for spelling in _ROMAJI:
        spellings.add(spelling)
        if spelling == 'n':
            spellings.add("n'")
    spellings.add('c')
    spellings.add('ー')
    spellings.update(_KANA)
    spellings.update(_SMALL)
    return sorted(spellings)


if __name__ == '__main__':
    expected = {
        'sa': 's a', 'ku': 'k M', 'ra': '4 a', 'shi': 'S i', 'chi': 'tS i',
        'tsu': 'ts M', 'fu': 'p\\ M', 'ji': 'dZ i', 'ni': 'J i', 'hi': 'C i',
        'ya': 'j a', 'yu': 'j M', 'yo': 'j o', 'kya': "k' j a", 'kka': 'k k a',
        'on': 'o n', 'sakura': 's a k M 4 a', 'う': 'M', 'くう': 'k M M',
        'さくら': 's a k M 4 a', 'サクラ': 's a k M 4 a',
        'にほんご': 'J i h o n g o', 'しんあい': 'S i n a i',
        'かっこう': 'k a k k o M',
    }
    for lyric, value in expected.items():
        assert phonemes(lyric) == value, (lyric, phonemes(lyric), value)
    for invalid in ('', 'xx', 'zzz'):
        try:
            phonemes(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid lyric accepted: ' + invalid)
    aliases_list = aliases()
    for alias in aliases_list:
        if alias != 'ー': phonemes(alias)
    print(f'PASS: {len(aliases_list)} experimental kana/romaji aliases, gemination, youon and invalid inputs')