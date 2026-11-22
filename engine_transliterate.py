"""
OpenFlow Roman Hinglish Transliteration Module
Converts Devanagari Hindi text to natural colloquial Roman Hinglish script
while strictly preserving English words (Latin script), punctuation, numbers, and symbols.
Zero network dependencies, 100% offline rule-based phonetic engine.
"""
import re
from typing import List

# Independent vowels
INDEPENDENT_VOWELS = {
    'अ': 'a',
    'आ': 'aa',
    'इ': 'i',
    'ई': 'ee',
    'उ': 'u',
    'ऊ': 'oo',
    'ऋ': 'ri',
    'ए': 'e',
    'ऐ': 'ai',
    'ओ': 'o',
    'औ': 'au',
    'अं': 'an',
    'अः': 'ah',
}

# Dependent vowel signs (matras)
MATRAS = {
    'ा': 'a',
    'ि': 'i',
    'ी': 'ee',
    'ु': 'u',
    'ू': 'oo',
    'ृ': 'ri',
    'े': 'e',
    'ै': 'ai',
    'ो': 'o',
    'ौ': 'au',
    'ं': 'n',
    'ँ': 'n',
    'ः': 'h',
}

# Consonants
CONSONANTS = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'क़': 'q', 'ख़': 'kh', 'ग़': 'gh', 'ज़': 'z', 'ड़': 'd', 'ढ़': 'dh', 'फ़': 'f',
}

# Special marks
VIRAMA = '्'
NUKTA = '़'

# Common Hindi word dictionary to produce clean, natural conversational Roman spellings
COMMON_WORDS = {
    "है": "hai",
    "हैं": "hain",
    "हो": "ho",
    "हूं": "hoon",
    "हूँ": "hoon",
    "था": "tha",
    "थी": "thee",
    "थे": "the",
    "का": "ka",
    "के": "ke",
    "की": "ki",
    "को": "ko",
    "में": "mein",
    "से": "se",
    "पर": "par",
    "ने": "ne",
    "तक": "tak",
    "और": "aur",
    "या": "ya",
    "कि": "ki",
    "तो": "to",
    "भी": "bhi",
    "ही": "hi",
    "यह": "yeh",
    "ये": "ye",
    "वह": "woh",
    "वे": "ve",
    "क्या": "kya",
    "क्यों": "kyon",
    "कहा": "kaha",
    "कहाँ": "kahan",
    "यहाँ": "yahan",
    "वहाँ": "wahan",
    "जहाँ": "jahan",
    "कब": "kab",
    "तब": "tab",
    "जब": "jab",
    "अब": "ab",
    "सब": "sab",
    "एक": "ek",
    "दो": "do",
    "तीन": "teen",
    "चार": "chaar",
    "पाँच": "paanch",
    "पांच": "paanch",
    "दस": "das",
    "सौ": "sau",
    "हज़ार": "hazaar",
    "हजार": "hazaar",
    "लाख": "lakh",
    "करोड़": "crore",
    "रुपये": "rupaye",
    "रुपए": "rupaye",
    "पैसे": "paise",
    "पैसा": "paisa",
    "नहीं": "nahi",
    "ना": "na",
    "हाँ": "haan",
    "हां": "haan",
    "बहुत": "bahut",
    "ज्यादा": "zyada",
    "कम": "kam",
    "अच्छा": "achha",
    "अच्छी": "achhi",
    "अच्छे": "achhe",
    "बुरा": "bura",
    "बड़ा": "bada",
    "बड़ी": "badi",
    "बड़े": "bade",
    "छोटा": "chhota",
    "छोटी": "chhoti",
    "छोटे": "chhote",
    "करना": "karna",
    "करता": "karta",
    "करती": "karti",
    "करते": "karte",
    "किया": "kiya",
    "किए": "kiye",
    "कर": "kar",
    "रहा": "raha",
    "रही": "rahi",
    "रहे": "rahe",
    "होगा": "hoga",
    "होगी": "hogi",
    "होंगे": "honge",
    "सकता": "sakta",
    "सकती": "sakti",
    "सकते": "sakte",
    "गया": "gaya",
    "गयी": "gayi",
    "गए": "gaye",
    "जाना": "jaana",
    "जाता": "jaata",
    "जाती": "jaati",
    "जाते": "jaate",
    "आना": "aana",
    "आता": "aata",
    "आती": "aati",
    "आते": "aate",
    "बोला": "bola",
    "बोली": "boli",
    "बोले": "bole",
    "कही": "kahi",
    "कहे": "kahe",
    "देखना": "dekhna",
    "देखा": "dekha",
    "देखे": "dekhe",
    "सुना": "suna",
    "सुने": "sune",
    "मुझे": "mujhe",
    "मुझको": "mujhko",
    "मेरा": "mera",
    "मेरी": "meri",
    "मेरे": "mere",
    "मैंने": "maine",
    "मैने": "maine",
    "हम": "hum",
    "हमें": "humein",
    "हमारा": "hamara",
    "हमारी": "hamari",
    "हमारे": "hamare",
    "तू": "tu",
    "तुझे": "tujhe",
    "तेरा": "tera",
    "तेरी": "teri",
    "तेरे": "tere",
    "तुम": "tum",
    "तुम्हें": "tumhein",
    "तुम्हारा": "tumhara",
    "तुम्हारी": "tumhari",
    "तुम्हारे": "tumhare",
    "आप": "aap",
    "आपको": "aapko",
    "आपका": "aapka",
    "आपकी": "aapki",
    "आपके": "aapke",
    "उसे": "use",
    "उसको": "usko",
    "उसका": "uska",
    "उसकी": "uski",
    "उसके": "uske",
    "उन्हें": "unhein",
    "उनको": "unko",
    "उनका": "unka",
    "उनकी": "unki",
    "उनके": "unke",
    "इसे": "ise",
    "इसको": "isko",
    "इसका": "iska",
    "इसकी": "iski",
    "इसके": "iske",
    "इन्हें": "inhein",
    "इनको": "inko",
    "इनका": "inka",
    "इनकी": "inki",
    "इनके": "inke",
    "लोग": "log",
    "लोगों": "logon",
    "दोस्त": "dost",
    "भाई": "bhai",
    "बहन": "behen",
    "घर": "ghar",
    "काम": "kaam",
    "समय": "samay",
    "दिन": "din",
    "रात": "raat",
    "सुबह": "subah",
    "शाम": "shaam",
    "आज": "aaj",
    "कल": "kal",
    "परसों": "parson",
    "पहले": "pehle",
    "बाद": "baad",
    "साथ": "saath",
    "पास": "paas",
    "दूर": "door",
    "ऊपर": "upar",
    "नीचे": "neeche",
    "अंदर": "andar",
    "बाहर": "bahar",
    "सामने": "saamne",
    "पीछे": "peeche",
    "तरफ": "taraf",
    "बात": "baat",
    "चीज": "cheez",
    "जगह": "jagah",
    "तरह": "tarah",
    "खाना": "khana",
    "पानी": "paani",
    "चाय": "chai",
    "गाड़ी": "gadi",
    "रास्ता": "raasta",
    "रास्ते": "raaste",
    "नाम": "naam",
    "शहर": "shehar",
    "देश": "desh",
    "दुनिया": "duniya",
    "ज़िंदगी": "zindagi",
    "जिंदगी": "zindagi",
    "खुश": "khush",
    "दुखी": "dukhi",
    "प्यार": "pyaar",
    "मदद": "madad",
    "ज़रूरत": "zaroorat",
    "जरूरत": "zaroorat",
    "ज़रूरी": "zaroori",
    "जरूरी": "zaroori",
    "वैज्ञानिकों": "vaigyanikon",
    "इज्ञानिकों": "vaigyanikon",
    "मानना": "maanna",
    "जानवरों": "jaanwaron",
    "पीछा": "peecha",
    "खाते": "khaate",
    "सुनते": "sunte",
    "हुए": "huye",
    "हुई": "huyi",
    "हुआ": "hua",
    "जमीन": "zameen",
    "रहेंगे": "rahenge",
    "वर्ष": "varsh",
    "वर्षा": "varsha",
    "स्नेह": "sneh",
    "अपनी": "apni",
    "अपने": "apne",
    "अपना": "apna",
    "खो": "kho",
    "दिया": "diya",
    "दिए": "diye",
    "दी": "dee",
    "दिव्यांग": "divyang",
    "उछल": "uchhal",
    "धक्का": "dhakka",
    "दे": "de",
    "सब्जियों": "sabziyon",
    "सब्ज़ियों": "sabziyon",
    "मांस": "maans",
    "विशेष": "vishesh",
    "रूप": "roop",
    "आधारित": "aadharit",
    "उपयोग": "upyog",
    "समान": "samaan",
    "क्षेत्रों": "kshetron",
    "रोटी": "roti",
    "तेल": "tel",
    "गंद": "gand",
    "द्वारा": "dwara",
}

def _is_devanagari(char: str) -> bool:
    """Checks if character falls in Devanagari Unicode block (U+0900 - U+097F)."""
    return '\u0900' <= char <= '\u097f'

def transliterate_devanagari_word(word: str) -> str:
    """
    Phonetically transliterates a single Devanagari word into readable Roman Hindi.
    Applies Schwa deletion rules (Hindi final silent 'a').
    """
    clean_word = word.strip()
    if clean_word in COMMON_WORDS:
        return COMMON_WORDS[clean_word]

    # Strip non-alphanumeric punctuation (only ASCII / standard punctuation)
    # Never strip Devanagari matras as punctuation!
    pre_match = re.match(r"^([^\u0900-\u097f\w]*)([\u0900-\u097f]+)([^\u0900-\u097f\w]*)$", clean_word)
    pre, core, post = "", clean_word, ""
    if pre_match:
        pre, core, post = pre_match.groups()
        if core in COMMON_WORDS:
            return pre + COMMON_WORDS[core] + post

    res = []
    chars = list(core)
    n = len(chars)
    i = 0

    while i < n:
        c = chars[i]

        # Handle nukta combining (e.g. क + ़ = क़)
        if i + 1 < n and chars[i + 1] == NUKTA:
            combined = c + NUKTA
            if combined in CONSONANTS:
                c = combined
                i += 1

        if c in INDEPENDENT_VOWELS:
            res.append(INDEPENDENT_VOWELS[c])
            i += 1
            continue

        if c in CONSONANTS:
            cons = CONSONANTS[c]
            # Check what follows: virama, matra, or consonant
            if i + 1 < n and chars[i + 1] == VIRAMA:
                # Half-letter: append consonant without inherent 'a'
                res.append(cons)
                i += 2  # skip virama
            elif i + 1 < n and chars[i + 1] in MATRAS:
                matra = chars[i + 1]
                res.append(cons + MATRAS[matra])
                i += 2
            else:
                # Inherent vowel rule:
                # In Hindi, word-final consonant almost always drops inherent 'a' (schwa deletion).
                is_last_letter = (i == n - 1)
                if is_last_letter:
                    res.append(cons)
                else:
                    res.append(cons + "a")
                i += 1
            continue

        if c in MATRAS:
            res.append(MATRAS[c])
            i += 1
            continue

        # Any other character
        res.append(c)
        i += 1

    roman = "".join(res)
    roman = re.sub(r'a+$', 'a', roman)
    return pre + roman + post


def transliterate_to_hinglish(text: str) -> str:
    """
    Transliterates a mixed Devanagari and English text into natural Roman Hinglish.
    - English words (Latin script) are 100% untouched.
    - Numbers and punctuation are preserved.
    - Devanagari words are converted to phonetic Roman Hindi.
    """
    if not text:
        return ""

    tokens = re.split(r'(\s+)', text)
    result = []

    for token in tokens:
        if not token:
            continue
        if token.isspace():
            result.append(token)
            continue

        # Check if token contains any Devanagari characters
        has_devanagari = any(_is_devanagari(c) for c in token)
        if not has_devanagari:
            result.append(token)
        else:
            result.append(transliterate_devanagari_word(token))

    output = "".join(result)
    output = re.sub(r'[ \t]+', ' ', output).strip()
    return output
