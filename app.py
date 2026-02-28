import os
import json
import requests
import socket
from flask import Flask, request, jsonify, render_template, Response
from urllib.parse import urlparse
from dotenv import load_dotenv
from langdetect import detect
from googletrans import Translator
import dns.resolver
from bs4 import BeautifulSoup
from flask import send_from_directory
import re
from datetime import datetime
import hashlib
import sqlite3

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
USE_SQLITE = not DATABASE_URL or "postgresql" not in DATABASE_URL
SQLITE_DB = "factcheck.db"

GOOGLE_API_KEY = os.getenv("GOOGLE_FACTCHECK_KEY")
SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")
SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY")
SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")
SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")

app = Flask(__name__, template_folder="templates", static_folder="static")
translator = Translator()

def get_db():
    if USE_SQLITE:
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            print(f"⚠️ PostgreSQL помилка: {e}, використовую SQLite")
            conn = sqlite3.connect(SQLITE_DB)
            conn.row_factory = sqlite3.Row
            return conn

def init_db():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            if USE_SQLITE:
                cur.execute('''CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT,
                    url_hash TEXT,
                    score INTEGER,
                    verdict TEXT,
                    explanation TEXT,
                    sources TEXT,
                    lang TEXT DEFAULT 'uk',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_query_hash ON checks(query_hash)')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_lang ON checks(lang)')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_query_lang ON checks(query_hash, lang)')
            else:
                with open("init_db.sql", "r", encoding="utf-8") as f:
                    sql = f.read()
                cur.execute(sql)
            
            conn.commit()
        print("✅ База даних ініціалізована")
    except Exception as e:
        print(f"⚠️ Помилка ініціалізації БД: {e}")

def hash_text(text):
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


BLOCKED_DOMAINS = [
    '.ru', '.рф', '.su',
    '.by',
    'kremlin', 'tass.', 'ria.', 'rbc.', 'kommersant.', 'interfax.',
    'lenta.', 'gazeta.', 'russian.rt.', 'sputnik', 'iz.ru',
    'forbes.ru', 'vedomosti.', 'rossiyskaya-gazeta.', 'rg.ru',
    'belta.by', 'sb.by', 'ont.by',

    'casino', 'казино', 'bet', 'betting', 'ставки', 'poker', 'покер',
    'slots', 'слоты', 'jackpot', 'джекпот', 'gambling', 'азартні',
    'azino', 'vulkan', 'вулкан', 'joycasino', 'slot', 'pin-up',
    'pinup', '1xbet', 'fonbet', 'parimatch', 'leon', 'winline',
    'betfair', 'bwin', '888casino', 'slottica', 'riobet', '777',

    'porn', 'порно', 'xxx', 'sex', 'секс', 'adult', 'xvideos',
    'pornhub', 'xnxx', 'redtube', 'youporn', 'tube8', 'spankwire',
    'keezmovies', 'chaturbate', 'livejasmin', 'bongacams', 'stripchat',
    'nude', 'голі', 'naked', 'nsfw', 'erotic', 'erotica', 'hentai',
    'cam4', 'myfreecams', 'camsoda', 'onlyfans', 'manyvids'
]

# Language to Google Custom Search parameters
LANGUAGE_SEARCH_PARAMS = {
    'uk': {'lr': 'lang_uk', 'hl': 'uk'},  # Ukrainian
    'en': {'lr': 'lang_en', 'hl': 'en'},  # English
    'es': {'lr': 'lang_es', 'hl': 'es'},  # Spanish
    'fr': {'lr': 'lang_fr', 'hl': 'fr'},  # French
    'de': {'lr': 'lang_de', 'hl': 'de'},  # German
    'pl': {'lr': 'lang_pl', 'hl': 'pl'},  # Polish
    'it': {'lr': 'lang_it', 'hl': 'it'},  # Italian
}

# Detect language from URL/source
def detect_url_language(url):
    """Detect the language of content from URL domain and structure"""
    url_lower = url.lower()
    
    # Block Russian content completely
    russian_indicators = ['.ru', '.рф', '.su', 'russian', 'россий', 'русск', '/ru/', '-ru-', '_ru_']
    for indicator in russian_indicators:
        if indicator in url_lower:
            return 'ru'  # Mark as Russian to block it
    
    # Check TLDs and domain patterns for other languages
    language_patterns = {
        'uk': ['.ua', 'ukrainian', 'укр', 'ukraine', '/uk/', '-uk-'],
        'en': ['.co.uk', '.com', '.org', '.gov', '/en/', 'english', 'англійськ'],
        'es': ['.es', 'español', 'spain', 'spanish', '/es/', 'españa'],
        'fr': ['.fr', 'french', 'français', 'france', '/fr/'],
        'de': ['.de', 'deutsch', 'german', 'deutschland', '/de/'],
        'pl': ['.pl', 'polish', 'polski', 'poland', '/pl/'],
        'it': ['.it', 'italian', 'italiano', 'italia', '/it/'],
    }
    
    for lang, patterns in language_patterns.items():
        for pattern in patterns:
            if pattern in url_lower:
                return lang
    
    return None

def is_url_safe_language(url, required_lang):
    """Check if URL content is in the required language. Always blocks Russian.
    More permissive: only block if language is explicitly detected AND doesn't match."""
    detected = detect_url_language(url)
    
    # Always block Russian URLs
    if detected == 'ru':
        return False
    
    # Always allow if no language detected from URL (will check content later if needed)
    # This allows .com, .org, .net, .io etc. domains to pass
    if detected is None:
        return True
    
    # Only block if language is explicitly detected and doesn't match required
    # BUT allow if detected matches required language
    match_rules = {
        'uk': ['uk', 'en'],  # Ukrainian can use Ukrainian + English sources
        'en': ['en'],         # English sources for English  
        'es': ['es', 'en'],   # Spanish can use Spanish + English
        'fr': ['fr', 'en'],   # French can use French + English
        'de': ['de', 'en'],   # German can use German + English
        'pl': ['pl', 'en'],   # Polish can use Polish + English
        'it': ['it', 'en'],   # Italian can use Italian + English
    }
    
    allowed = match_rules.get(required_lang, ['en'])
    return detected in allowed

def is_blocked_source(url):
    if not url:
        return False
    url_lower = url.lower()
    for blocked in BLOCKED_DOMAINS:
        if blocked in url_lower:
            return True
    return False

def get_block_reason(url):
    """Визначає причину блокування"""
    if not url:
        return None
    url_lower = url.lower()
    
    russian_domains = ['.ru', '.рф', '.su', 'kremlin', 'tass.', 'ria.', 'rbc.',
                      'kommersant.', 'interfax.', 'lenta.', 'gazeta.', 'sputnik']
    belarusian_domains = ['.by', 'belta.by', 'sb.by', 'ont.by']
    
    for domain in russian_domains:
        if domain in url_lower:
            return "russian"
    for domain in belarusian_domains:
        if domain in url_lower:
            return "belarusian"
    
    casino_keywords = ['casino', 'казино', 'bet', 'betting', 'ставки', 'poker',
                      'покер', 'slots', 'слоты', 'gambling', 'azino', 'vulkan',
                      '1xbet', 'fonbet', 'parimatch', '777']
    for keyword in casino_keywords:
        if keyword in url_lower:
            return "casino"
    
    adult_keywords = ['porn', 'порно', 'xxx', 'sex', 'adult', 'pornhub',
                     'xnxx', 'nude', 'naked', 'nsfw', 'erotic', 'onlyfans']
    for keyword in adult_keywords:
        if keyword in url_lower:
            return "adult"
    
    return None

def filter_sources(sources, lang=None):
    """Filter sources by blocking list and optionally by language"""
    if not sources:
        return []
    
    filtered = []
    for source in sources:
        url = source if isinstance(source, str) else source.get('link', '')
        
        # Always block blocked sources
        if is_blocked_source(url):
            continue
        
        # Block Russian content completely
        if not is_url_safe_language(url, lang or 'en'):
            print(f"  🚫 Filtered by language: {url}")
            continue
        
        # Add to filtered list
        if isinstance(source, str):
            filtered.append(source)
        elif isinstance(source, dict):
            filtered.append(source)
    
    return filtered

def check_adult_content_sightengine(url):
    if not SIGHTENGINE_USER or not SIGHTENGINE_SECRET:
        return {"checked": False, "reason": "API not configured"}
    
    try:
        params = {
            'url': url,
            'models': 'nudity-2.1,offensive',
            'api_user': SIGHTENGINE_USER,
            'api_secret': SIGHTENGINE_SECRET
        }
        
        r = requests.get('https://api.sightengine.com/1.0/check.json', params=params, timeout=10)
        if r.status_code != 200:
            return {"checked": False, "reason": "API error"}
        
        data = r.json()
        
        nudity = data.get('nudity', {})
        raw_score = nudity.get('raw', 0)
        partial_score = nudity.get('partial', 0)
        
        if raw_score > 0.5 or partial_score > 0.6:
            return {"checked": True, "blocked": True, "type": "adult", "confidence": max(raw_score, partial_score)}
        
        return {"checked": True, "blocked": False}
        
    except Exception as e:
        print(f"⚠️ Sightengine error: {e}")
        return {"checked": False, "reason": str(e)}

def check_gambling_content(url):
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, "html.parser")
        
        text_content = soup.get_text().lower()
        gambling_keywords = [
            'casino', 'казино', 'poker', 'покер', 'slots', 'слоти',
            'jackpot', 'джекпот', 'roulette', 'рулетка', 'blackjack',
            'ставки', 'betting', 'gambling', 'азартні ігри',
            'бонус депозит', 'bonus deposit', 'free spins'
        ]
        
        matches = sum(1 for keyword in gambling_keywords if keyword in text_content)
        
        if matches >= 3:
            return {"checked": True, "blocked": True, "type": "casino", "matches": matches}
        
        return {"checked": True, "blocked": False}
        
    except Exception as e:
        print(f"⚠️ Gambling check error: {e}")
        return {"checked": False, "reason": str(e)}

def check_safe_browsing_extended(url):
    try:
        api = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={SAFE_BROWSING_KEY}"
        payload = {
            "client": {"clientId": "factoryx", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": [
                    "MALWARE",
                    "SOCIAL_ENGINEERING",
                    "UNWANTED_SOFTWARE",
                    "POTENTIALLY_HARMFUL_APPLICATION"
                ],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        
        res = requests.post(api, json=payload, timeout=10)
        jd = res.json()
        
        if jd.get("matches"):
            return {"safe": False, "threat_types": [m.get("threatType") for m in jd.get("matches", [])]}
        
        return {"safe": True}
        
    except Exception as e:
        print(f"⚠️ Safe Browsing error: {e}")
        return {"safe": True}

def detect_language(text):
    try:
        detected = detect(text)
        # Map language codes to supported languages
        # Important: Never map Russian to Ukrainian!
        lang_map = {
            'uk': 'uk', 
            'ru': 'en',  # Russian detected = use English instead (never Russian!)
            'en': 'en', 
            'es': 'es', 
            'fr': 'fr', 
            'de': 'de', 
            'pl': 'pl', 
            'it': 'it'
        }
        return lang_map.get(detected, 'en')
    except:
        return "en"

def get_raw_language_code(text):
    """Get raw language code without mapping (for checking user's actual text language)"""
    try:
        return detect(text)
    except:
        return None

def validate_link_language(url, selected_lang):
    """
    Check if link content language matches selected language.
    Returns: (is_valid, error_message_or_None)
    """
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Extract text from page
        for bad in soup(["script", "style", "header", "footer", "nav"]):
            bad.decompose()
        
        text_blocks = [t.get_text() for t in soup.find_all(['p', 'h1', 'h2', 'h3', 'article'])]
        page_text = " ".join(text_blocks)[:500]
        
        if not page_text or len(page_text) < 20:
            return True, None  # Can't detect, allow
        
        raw_lang = get_raw_language_code(page_text)
        
        # Block Russian completely
        if raw_lang == 'ru':
            error_msgs = {
                'uk': "❌ Посилання містить російський контент",
                'en': "❌ Link contains Russian content",
                'es': "❌ El enlace contiene contenido en ruso",
                'fr': "❌ Le lien contient du contenu en russe",
                'de': "❌ Link enthält russische Inhalte",
                'pl': "❌ Link zawiera treść w języku rosyjskim",
                'it': "❌ Il link contiene contenuti in russo"
            }
            return False, error_msgs.get(selected_lang, error_msgs['en'])
        
        if raw_lang is None:
            return True, None
        
        # Map and check language match
        lang_mapping = {
            'uk': 'uk', 'ru': 'ru',
            'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'pl': 'pl', 'it': 'it'
        }
        
        detected_mapped = lang_mapping.get(raw_lang, None)
        if detected_mapped is None:
            return True, None
        
        # Check if detected language matches selected language
        if detected_mapped != selected_lang:
            short_lang_names = {
                'uk': 'UK',
                'en': 'EN',
                'es': 'ES',
                'fr': 'FR',
                'de': 'DE',
                'pl': 'PL',
                'it': 'IT'
            }
            
            detected_short = short_lang_names.get(detected_mapped, detected_mapped)
            selected_short = short_lang_names.get(selected_lang, selected_lang)
            
            # Build error for CURRENT language
            error_msg = None
            if selected_lang == 'uk':
                error_msg = f"⚠️ Посилання на {detected_short}, інтерфейс на {selected_short}. Змініть мову або використайте посилання на {selected_short}"
            elif selected_lang == 'en':
                error_msg = f"⚠️ Link in {detected_short}, interface in {selected_short}. Change language or use link in {selected_short}"
            elif selected_lang == 'es':
                error_msg = f"⚠️ Enlace en {detected_short}, interfaz en {selected_short}. Cambia el idioma o usa enlace en {selected_short}"
            elif selected_lang == 'fr':
                error_msg = f"⚠️ Lien en {detected_short}, interface en {selected_short}. Changez la langue ou utilisez un lien en {selected_short}"
            elif selected_lang == 'de':
                error_msg = f"⚠️ Link auf {detected_short}, Interface auf {selected_short}. Ändern Sie die Sprache oder verwenden Sie Link auf {selected_short}"
            elif selected_lang == 'pl':
                error_msg = f"⚠️ Link w {detected_short}, interfejs w {selected_short}. Zmień język lub użyj linku w {selected_short}"
            elif selected_lang == 'it':
                error_msg = f"⚠️ Link in {detected_short}, interfaccia in {selected_short}. Cambia lingua o usa link in {selected_short}"
            
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        print(f"⚠️ Language validation for link failed: {e}")
        return True, None  # Allow if we can't check

def validate_text_language(text, selected_lang):
    """
    Validate if text language matches selected interface language.
    Returns: (is_valid, error_message_or_lang)
    Only blocks Russian completely. Shows short error for language mismatch.
    """
    if not text or len(text.strip()) < 10:
        return True, None
    
    raw_lang = get_raw_language_code(text)
    
    # Always block Russian text completely
    if raw_lang == 'ru':
        error_msgs = {
            'uk': "❌ Російська мова не підтримується",
            'en': "❌ Russian language is not supported",
            'es': "❌ El idioma ruso no es compatible",
            'fr': "❌ La langue russe n'est pas prise en charge",
            'de': "❌ Russische Sprache wird nicht unterstützt",
            'pl': "❌ Język rosyjski nie jest obsługiwany",
            'it': "❌ La lingua russa non è supportata"
        }
        return False, error_msgs.get(selected_lang, error_msgs['en'])
    
    # If no language detected, allow it
    if raw_lang is None:
        return True, None
    
    # Map raw language codes to our supported languages
    lang_mapping = {
        'uk': 'uk', 'ru': 'ru',
        'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'pl': 'pl', 'it': 'it'
    }
    
    detected_mapped = lang_mapping.get(raw_lang, None)
    
    # If detected language is not in our supported list, allow it
    if detected_mapped is None:
        return True, None
    
    # Check if detected language matches selected language
    if detected_mapped != selected_lang:
        # Languages don't match - show SHORT error
        short_lang_names = {
            'uk': 'UK',
            'en': 'EN',
            'es': 'ES',
            'fr': 'FR',
            'de': 'DE',
            'pl': 'PL',
            'it': 'IT'
        }
        
        detected_short = short_lang_names.get(detected_mapped, detected_mapped)
        selected_short = short_lang_names.get(selected_lang, selected_lang)
        
        # Build error for CURRENT selected language
        error_msg = None
        if selected_lang == 'uk':
            error_msg = f"⚠️ Текст на {detected_short}, інтерфейс на {selected_short}. Змініть мову або напишіть на {selected_short}"
        elif selected_lang == 'en':
            error_msg = f"⚠️ Text in {detected_short}, interface in {selected_short}. Change language or write in {selected_short}"
        elif selected_lang == 'es':
            error_msg = f"⚠️ Texto en {detected_short}, interfaz en {selected_short}. Cambia el idioma o escribe en {selected_short}"
        elif selected_lang == 'fr':
            error_msg = f"⚠️ Texte en {detected_short}, interface en {selected_short}. Changez la langue ou écrivez en {selected_short}"
        elif selected_lang == 'de':
            error_msg = f"⚠️ Text auf {detected_short}, Interface auf {selected_short}. Sprache ändern oder auf {selected_short} schreiben"
        elif selected_lang == 'pl':
            error_msg = f"⚠️ Tekst w {detected_short}, interfejs w {selected_short}. Zmień język lub napisz w {selected_short}"
        elif selected_lang == 'it':
            error_msg = f"⚠️ Testo in {detected_short}, interfaccia in {selected_short}. Cambia lingua o scrivi in {selected_short}"
        
        return False, error_msg
    
    # Languages match
    return True, None

def get_language_specific_sources(lang):
    """Returns language-specific source priorities"""
    sources = {
        'uk': {
            'label': 'Ukrainian',
            'sources': [
                'Suspilne.media', 'Ukrainska Pravda', 'UNIĀN', 'Kyiv Independent',
                'BBC', 'Reuters', 'AP News', 'AFP', 'The Guardian', 'DW'
            ],
            'instruction': (
                "\n📌 ДЖЕРЕЛА ПРІОРИТЕТУ (від найважливіших):\n"
                "1️⃣ Українські: Suspilne, Ukrainska Pravda, УНІАН, Kyiv Independent\n"
                "2️⃣ Західні агенції: Reuters, AP, BBC, AFP, CNN, The Guardian\n"
                "3️⃣ Міжнародні: Wikipedia (eng), DW, Euronews\n"
            )
        },
        'en': {
            'label': 'English',
            'sources': [
                'Reuters', 'AP News', 'BBC News', 'The Guardian', 'CNN', 'NPR',
                'The New York Times', 'The Washington Post', 'Politico', 'The Economist'
            ],
            'instruction': (
                "\n📌 SOURCE PRIORITY (from most important):\n"
                "1️⃣ Major news agencies: Reuters, AP, BBC, AFP, CNN\n"
                "2️⃣ Quality newspapers: The Guardian, NYT, Washington Post\n"
                "3️⃣ International: Wikipedia, DW, Euronews\n"
            )
        },
        'es': {
            'label': 'Spanish',
            'sources': [
                'El País', 'BBC Mundo', 'Reuters en español', 'CNN en Español',
                'Infobae', 'La Nación', 'Reforma', 'El Mundo'
            ],
            'instruction': (
                "\n📌 PRIORIDAD DE FUENTES (de más a menos importante):\n"
                "1️⃣ Agencias principales: Reuters, AP, BBC Mundo, AFP\n"
                "2️⃣ Periódicos de calidad: El País, Infobae, La Nación\n"
                "3️⃣ Internacionales: Wikipedia, DW, Euronews\n"
            )
        },
        'fr': {
            'label': 'French',
            'sources': [
                'AFP', 'Reuters France', 'BBC Afrique', 'Le Monde', 'Libération',
                'France 24', 'Le Figaro', 'Mediapart'
            ],
            'instruction': (
                "\n📌 PRIORITÉ DES SOURCES (du plus important au moins important):\n"
                "1️⃣ Agences principales: AFP, Reuters, BBC, CNN\n"
                "2️⃣ Journaux de qualité: Le Monde, Libération, Le Figaro\n"
                "3️⃣ Internationaux: Wikipedia, DW, Euronews\n"
            )
        },
        'de': {
            'label': 'German',
            'sources': [
                'Deutsche Welle', 'Tagesschau', 'Die Zeit', 'Der Spiegel',
                'Frankfurter Allgemeine', 'Süddeutsche Zeitung', 'BBC Deutsch'
            ],
            'instruction': (
                "\n📌 QUELLENPRIORITÄT (von wichtigsten zu am wenigsten wichtigen):\n"
                "1️⃣ Hauptagenturen: Reuters, AP, BBC, dpa\n"
                "2️⃣ Qualitätsmedien: Der Spiegel, Die Zeit, FAZ\n"
                "3️⃣ Internationale: Wikipedia, DW, Euronews\n"
            )
        },
        'pl': {
            'label': 'Polish',
            'sources': [
                'Agencja Reuters', 'BBC Polskie', 'Wyborcza.pl', 'Polityka',
                'Tygodnik Powszechny', 'Rzeczpospolita', 'Gazeta Wyborcza'
            ],
            'instruction': (
                "\n📌 PRIORYTET ŹRÓDEŁ (od najważniejszych):\n"
                "1️⃣ Główne agencje: Reuters, AP, BBC, PAP\n"
                "2️⃣ Media wysokiej jakości: Wyborcza, Polityka, Rzeczpospolita\n"
                "3️⃣ Międzynarodowe: Wikipedia, DW, Euronews\n"
            )
        },
        'it': {
            'label': 'Italian',
            'sources': [
                'ANSA', 'Reuters Italia', 'BBC Italia', 'La Repubblica', 'Il Corriere',
                'La Stampa', 'Il Sole 24 Ore', 'Euronews'
            ],
            'instruction': (
                "\n📌 PRIORITÀ DELLE FONTI (da più a meno importanti):\n"
                "1️⃣ Agenzie principali: Reuters, AP, BBC, ANSA\n"
                "2️⃣ Giornali di qualità: La Repubblica, Corriere, La Stampa\n"
                "3️⃣ Internazionali: Wikipedia, DW, Euronews\n"
            )
        }
    }
    return sources.get(lang, sources['en'])

def translate_text(text, target="uk"):
    try:
        return translator.translate(text, dest=target).text
    except:
        return text

@app.route("/translate", methods=["POST"])
def translate_api():
    data = request.json
    text = data.get("text", "")
    target = data.get("target", "uk")
    
    if not text:
        return jsonify({"translated": ""})
    
    return jsonify({"translated": translate_text(text, target)})

def is_question(text):
    clean = text.strip().lower()
    if clean.endswith("?"):
        return True
    
    q_words = [
        "хто", "що", "коли", "де", "чому", "як", "скільки", "чи",
        "who", "what", "where", "when", "why", "how", "which",
        "кто", "что", "где", "когда", "почему", "как"
    ]
    
    parts = re.findall(r'\b\w+\b', clean)
    if parts and parts[0] in q_words:
        return True
    
    return False

def is_subjective(text):
    subjective_words = [
        "крутий", "поганий", "жахливий", "добрий", "гарний",
        "я думаю", "мені здається", "вважаю", "на мій погляд",
        "красивий", "огидний"
    ]
    
    t = text.lower()
    return any(w in t for w in subjective_words)

def is_gibberish(text):
    if not text or len(text.strip()) < 5:
        return True
    
    text_no_spaces = text.replace(' ', '').replace('\n', '')
    if len(text_no_spaces) < 5:
        return True
    
    words = re.findall(r'[a-zA-Zа-яА-ЯіїєґІЇЄҐ]{2,}', text)
    if len(words) >= 3:
        return False
    
    if re.search(r'(.)\1{5,}', text):
        return True
    
    if len(text) < 20:
        keyboard_patterns = ['qwerty', 'asdfgh', 'zxcvbn', 'йцукен', 'фывап', 'ячсмит']
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in keyboard_patterns):
            return True
    
    if len(text_no_spaces) < 30:
        vowels = 'aeiouаеєиіїоуюя'
        has_vowels = any(char.lower() in vowels for char in text)
        if not has_vowels:
            return True
    
    return False

def extract_article_date(soup, url):
    try:
        meta_dates = [
            soup.find("meta", property="article:published_time"),
            soup.find("meta", {"name": "publish-date"}),
            soup.find("meta", {"name": "date"}),
            soup.find("time")
        ]
        
        for meta in meta_dates:
            if meta:
                date_str = meta.get("content") or meta.get("datetime") or meta.get_text()
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        return date_obj.strftime("%Y-%m-%d")
                    except:
                        pass
        
        url_date = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', url)
        if url_date:
            year, month, day = url_date.groups()
            return f"{year}-{month}-{day}"
        
        return None
        
    except:
        return None

def clean_citations(text):
    if not text:
        return text
    
    cleaned = re.sub(r'\[\d+\]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def google_factcheck(query, lang='uk'):
    try:
        url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={query}&key={GOOGLE_API_KEY}"
        r = requests.get(url, timeout=10)
        claims = r.json().get("claims", [])
        
        filtered_claims = []
        for claim in claims:
            if 'claimReview' in claim:
                has_blocked = False
                for review in claim['claimReview']:
                    review_url = review.get('url', '')
                    # Block if URL is blocked or not in the right language
                    if is_blocked_source(review_url) or not is_url_safe_language(review_url, lang):
                        has_blocked = True
                        if not is_blocked_source(review_url):
                            print(f"  🚫 Factcheck filtered by language: {review_url}")
                        break
                
                if not has_blocked:
                    filtered_claims.append(claim)
            else:
                filtered_claims.append(claim)
        
        return filtered_claims
        
    except Exception as e:
        print(f"⚠️ Google Factcheck error: {e}")
        return []

def google_search(query, lang='en'):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        
        # Add language-specific parameters
        search_params = {
            "key": SEARCH_KEY,
            "cx": SEARCH_CX,
            "q": query,
            "num": 50  # Request 50 results to get more after filtering
        }
        
        # Add language restrictions if available
        if lang in LANGUAGE_SEARCH_PARAMS:
            lang_params = LANGUAGE_SEARCH_PARAMS[lang]
            search_params['lr'] = lang_params['lr']
            search_params['hl'] = lang_params['hl']
        
        res = requests.get(url, params=search_params, timeout=10)
        
        items = res.json().get("items", [])
        results = [
            {
                "title": i.get("title"),
                "snippet": i.get("snippet"),
                "link": i.get("link")
            }
            for i in items
        ]
        
        # Filter by blocked domains and language
        filtered = filter_sources(results, lang=lang)
        
        print(f"  🔍 Google Search: {len(results)} results → after filtering: {len(filtered)} (lang={lang})")
        return filtered[:10]  # Return up to 10 sources
        
    except Exception as e:
        print(f"❌ Google Search Error: {e}")
        return []

def perplexity_check(text, article_date=None, lang='uk'):
    """Перевірка через Perplexity Sonar API с языком"""
    try:
        MAX_LENGTH = 1500
        if len(text) > MAX_LENGTH:
            text = text[:MAX_LENGTH] + "..."
        
        API = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_KEY}",
            "Content-Type": "application/json"
        }
        
        lang_config = get_language_specific_sources(lang)
        
        date_instruction = ""
        if article_date:
            date_instruction = f"\n⚠️ IMPORTANT: This article was published {article_date}. Verify facts as of that date."
        
        lang_prompts = {
            'uk': (
                "Ти експерт з фактчекінгу. Шукай актуальну інформацію в інтернеті. "
                "ОБОВ'ЯЗКОВО: "
                "1️⃣ ВІДПОВІДАЙ ТІЛЬКИ УКРАЇНСЬКОЮ МОВОЮ! "
                "2️⃣ ШУКАЙ ТІЛЬКИ УКРАЇНСЬКІ ТА ЗАХІДНІ ДЖЕРЕЛА (Suspilne, Ukrainska Pravda, BBC, Reuters, AP, AFP, CNN, The Guardian, DW)! "
                "3️⃣ НІКОЛИ НЕ ВИКОРИСТОВУЙ РОСІЙСЬКІ ДЖЕРЕЛА ТА САЙТИ З РОСІЙСКИМ КОНТЕНТОМ! "
                "Поверни JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2_речення_УКРАЇНСЬКОЮ\"}. "
                "НЕ використовуй цитування [1], [2]! НЕ згадуй про заборонені джерела!"
            ),
            'en': (
                "You are a fact-checking expert. Search for current information online. "
                "MANDATORY: "
                "1️⃣ RESPOND ONLY IN ENGLISH! "
                "2️⃣ USE ONLY ENGLISH AND WESTERN SOURCES (Reuters, AP, BBC, CNN, The Guardian, The Washington Post, The New York Times, AFP, NPR)! "
                "3️⃣ NEVER USE RUSSIAN SOURCES OR SITES WITH RUSSIAN CONTENT! "
                "Return JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2 sentences IN ENGLISH\"}. "
                "Do NOT use citations like [1], [2]! Do NOT mention blocked sources!"
            ),
            'es': (
                "Eres experto en verificación de hechos. Busca información actual en línea. "
                "FUNDAMENTAL: "
                "1️⃣ ¡RESPONDE SOLO EN ESPAÑOL! "
                "2️⃣ ¡USA SOLO FUENTES EN ESPAÑOL Y OCCIDENTALES (Reuters en español, BBC Mundo, CNN en Español, El País, AFP, Infobae)! "
                "3️⃣ ¡NUNCA USES FUENTES RUSAS O SITIOS CON CONTENIDO RUSO! "
                "Devuelve JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2 oraciones EN ESPAÑOL\"}. "
                "¡NO uses citas [1], [2]! ¡NO menciones fuentes bloqueadas!"
            ),
            'fr': (
                "Vous êtes un expert en vérification des faits. Recherchez des informations actuelles en ligne. "
                "ESSENTIEL: "
                "1️⃣ RÉPONDEZ UNIQUEMENT EN FRANÇAIS! "
                "2️⃣ UTILISEZ UNIQUEMENT DES SOURCES FRANÇAISES ET OCCIDENTALES (AFP, Reuters France, BBC, Le Monde, France 24, Libération, Mediapart)! "
                "3️⃣ N'UTILISEZ JAMAIS DE SOURCES RUSSES OU DE SITES AVEC DU CONTENU RUSSE! "
                "Retournez JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2 phrases EN FRANÇAIS\"}. "
                "N'utilisez PAS de citations [1], [2]! Ne mentionnez PAS les sources bloquées!"
            ),
            'de': (
                "Sie sind ein Faktenprüfungsexperte. Suchen Sie online nach aktuellen Informationen. "
                "WESENTLICH: "
                "1️⃣ ANTWORTEN SIE NUR AUF DEUTSCH! "
                "2️⃣ VERWENDEN SIE NUR DEUTSCHE UND WESTLICHE QUELLEN (Deutsche Welle, Tagesschau, Die Zeit, Der Spiegel, Reuters, BBC, AFP)! "
                "3️⃣ VERWENDEN SIE NIE RUSSISCHE QUELLEN ODER WEBSITES MIT RUSSISCHEM INHALT! "
                "Geben Sie JSON zurück: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2 Sätze AUF DEUTSCH\"}. "
                "Verwenden Sie KEINE Zitate [1], [2]! Erwähnen Sie KEINE gesperrten Quellen!"
            ),
            'pl': (
                "Jesteś ekspertem weryfikacji faktów. Wyszukaj bieżące informacje online. "
                "ISTOTNE: "
                "1️⃣ ODPOWIADAJ TYLKO PO POLSKU! "
                "2️⃣ UŻYWAJ TYLKO POLSKICH I ZACHODNICH ŹRÓDEŁ (Agencja Reuters, BBC Polskie, Wyborcza, Polityka, Rzeczpospolita, AFP)! "
                "3️⃣ NIGDY NIE UŻYWAJ ROSYJSKICH ŹRÓDEŁ LUB STRON Z ROSYJSKĄ TREŚCIĄ! "
                "Zwróć JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2 zdania PO POLSKU\"}. "
                "NIE używaj cytatów [1], [2]! NIE wspominaj zablokowanych źródeł!"
            ),
            'it': (
                "Sei un esperto di verifica dei fatti. Cerca informazioni attuali online. "
                "ESSENZIALE: "
                "1️⃣ RISPONDI SOLO IN ITALIANO! "
                "2️⃣ USA SOLO FONTI ITALIANE E OCCIDENTALI (ANSA, Reuters Italia, BBC, La Repubblica, Il Corriere, La Stampa, Euronews)! "
                "3️⃣ NON USARE MAI FONTI RUSSE O SITI CON CONTENUTO RUSSO! "
                "Restituisci JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2 frasi IN ITALIANO\"}. "
                "NON utilizzare citazioni [1], [2]! NON menzionare fonti bloccate!"
            )
        }
        
        system_prompt = lang_prompts.get(lang, lang_prompts['en'])
        source_instruction = (
            lang_config['instruction'] +
            "🚫 BLOCKED: .ru, .рф, .su, .by domains, Russian media, casinos, adult content!\n"
            "⚠️ IMPORTANT: If only blocked sources found - search for Western alternatives or write 'Insufficient reliable sources'"
        )
        
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        system_prompt +
                        f"{date_instruction}"
                        f"{source_instruction}"
                    )
                },
                {
                    "role": "user",
                    "content": ("Verify this statement: " if lang == 'en' else 
                               "Перевір це твердження: " if lang == 'uk' else
                               "Verifica esta afirmación: " if lang == 'es' else
                               "Vérifiez cette affirmation : " if lang == 'fr' else
                               "Überprüfen Sie diese Aussage: " if lang == 'de' else
                               "Zweryfikuj to stwierdzenie: " if lang == 'pl' else
                               "Verifica questa affermazione: ") + text
                }
            ],
            "temperature": 0.1,
            "max_tokens": 400,
            "return_citations": True
        }
        
        r = requests.post(API, json=payload, headers=headers, timeout=30)
        
        if r.status_code != 200:
            print(f"❌ Perplexity {r.status_code}")
            return {"error": f"Perplexity API error (code {r.status_code})"}
        
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        
        # Filter citations by language AND block list
        filtered_citations = filter_sources(citations, lang=lang)
        
        print(f"📊 Perplexity sources: {len(citations)} → after filtering: {len(filtered_citations)}, lang={lang}")
        
        # Check if we have Russian content mixed in (shouldn't happen but just to be sure)
        for citation in citations:
            if detect_url_language(citation) == 'ru':
                print(f"  ⚠️ Russian source detected and blocked: {citation}")
        
        json_match = re.search(r'\{[^{}]*"score"[^{}]*"verdict"[^{}]*"explanation"[^{}]*\}', content, re.DOTALL)
        
        if json_match:
            try:
                result = json.loads(json_match.group())
                
                if not isinstance(result.get("score"), (int, float)):
                    result["score"] = 50
                
                if result.get("verdict") not in ["true", "false", "uncertain"]:
                    result["verdict"] = "uncertain"
                
                explanation = clean_citations(result.get("explanation", ""))
                explanation = re.sub(r'(\.|^)[^.]*(\.\s*ru|\sру домен|російськ[іи][йх]?\s+(джерел|ЗМІ|сайт)|заборонен[іи]|казино|casino|дорослий контент|adult content).*?\.', '.', explanation, flags=re.IGNORECASE)
                explanation = re.sub(r'^\s*\.+\s*', '', explanation).strip()
                
                sentences = re.split(r'[.!?]+', explanation)
                sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
                
                if sentences:
                    result["explanation"] = ". ".join(sentences[:2]) + "."
                else:
                    if len(filtered_citations) == 0:
                        no_sources_msg = {
                            'uk': "Недостатньо надійних джерел для перевірки цього твердження.",
                            'en': "Insufficient reliable sources to verify this claim.",
                            'es': "Fuentes confiables insuficientes para verificar esta afirmación.",
                            'fr': "Sources fiables insuffisantes pour vérifier cette affirmation.",
                            'de': "Unzureichende zuverlässige Quellen zur Überprüfung dieser Aussage.",
                            'pl': "Niewystarczające wiarygodne źródła do weryfikacji tego stwierdzenia.",
                            'it': "Fonti affidabili insufficienti per verificare questa affermazione."
                        }
                        result["explanation"] = no_sources_msg.get(lang, no_sources_msg['en'])
                    else:
                        verified_msg = {
                            'uk': "Інформація підтверджена кількома незалежними джерелами.",
                            'en': "Information verified by multiple independent sources.",
                            'es': "Información verificada por múltiples fuentes independientes.",
                            'fr': "Information vérifiée par plusieurs sources indépendantes.",
                            'de': "Information verifiziert durch mehrere unabhängige Quellen.",
                            'pl': "Informacja zweryfikowana przez wiele niezależnych źródeł.",
                            'it': "Informazioni verificate da più fonti indipendenti."
                        }
                        result["explanation"] = verified_msg.get(lang, verified_msg['en'])
                
                result["sources"] = filtered_citations[:5]
                
                try:
                    detected_lang = detect(result.get('explanation', ''))
                    lang_mapping = {
                        'ru': 'uk', 'be': 'en', 
                        'uk': 'uk', 'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'pl': 'pl', 'it': 'it'
                    }
                    
                    if detected_lang != lang and detected_lang in ['ru', 'uk', 'en', 'es', 'fr', 'de', 'pl', 'it']:
                        print(f"🌐 Translation needed: detected={detected_lang}, requested={lang}")
                        lang_names = {
                            'uk': 'uk', 'en': 'en', 'es': 'es', 'fr': 'fr', 
                            'de': 'de', 'pl': 'pl', 'it': 'it'
                        }
                        target_lang_code = lang_names.get(lang, 'en')
                        translated = translator.translate(result.get('explanation', ''), src_language=detected_lang, dest_language=target_lang_code)
                        if translated and translated.text:
                            result["explanation"] = translated.text
                            print(f"✅ Translated to {lang}")
                except Exception as e:
                    print(f"⚠️ Translation check failed: {e}")
                
                print(f"✅ Perplexity: score={result['score']}, filtered_sources={len(result['sources'])}, lang={lang}")
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON decode error: {e}")
                pass
        
        return {
            "score": 50,
            "verdict": "uncertain",
            "explanation": (
                "Недостатньо інформації" if lang == 'uk' else
                "Insufficient information" if lang == 'en' else
                "Información insuficiente" if lang == 'es' else
                "Information insuffisante" if lang == 'fr' else
                "Unzureichende Informationen" if lang == 'de' else
                "Niewystarczające informacje" if lang == 'pl' else
                "Informazioni insufficienti" if lang == 'it' else
                "Insufficient information"
            ) if len(filtered_citations) == 0 else (
                "Інформація підтверджена" if lang == 'uk' else
                "Information verified" if lang == 'en' else
                "Información verificada" if lang == 'es' else
                "Information vérifiée" if lang == 'fr' else
                "Information überprüft" if lang == 'de' else
                "Informacja zweryfikowana" if lang == 'pl' else
                "Informazione verificata" if lang == 'it' else
                "Information verified"
            ),
            "sources": filtered_citations[:5]
        }
        
    except requests.exceptions.Timeout:
        timeout_msgs = {
            'uk': "Таймаут запиту",
            'en': "Request timeout",
            'es': "Tiempo de espera agotado",
            'fr': "Délai d'attente écoulé",
            'de': "Anfrage-Timeout",
            'pl': "Limit czasu żądania",
            'it': "Timeout della richiesta"
        }
        return {"error": timeout_msgs.get(lang, timeout_msgs['en'])}
    except Exception as e:
        print(f"❌ Perplexity: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def gemini_check(text, long=False):
    MAX_LENGTH = 2000 if long else 1000
    if len(text) > MAX_LENGTH:
        text = text[:MAX_LENGTH] + "..."
    
    instruction = (
        "Перевір факт і поверни JSON: {\"score\":0-100, \"verdict\":\"true/false/uncertain\", \"explanation\":\"1-2 речення\"}. "
        "Використовуй тільки західні та українські джерела (BBC, Reuters, AP, Suspilne). "
        "🚫 НЕ використовуй російські (.ru, .рф), білоруські (.by), казино та дорослі сайти!"
    )
    
    payload = {
        "contents": [{"parts": [{"text": instruction + "\nФакт: " + text}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512}
    }
    
    API = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_KEY}"
    
    try:
        r = requests.post(API, json=payload, timeout=20)
        
        if r.status_code != 200:
            return {"error": f"Gemini API помилка"}
        
        raw = r.json()
        
        if "candidates" not in raw or not raw["candidates"]:
            return {"score": 50, "verdict": "uncertain", "explanation": "Не вдалося проаналізувати", "sources": []}
        
        candidate = raw["candidates"][0]
        
        if "content" not in candidate:
            return {"score": 50, "verdict": "uncertain", "explanation": "Помилка AI", "sources": []}
        
        out = candidate["content"]["parts"][0]["text"]
        cleaned = out.replace("```json", "").replace("```", "").strip()
        
        try:
            data = json.loads(cleaned)
            data["sources"] = []
            return data
        except:
            return {"score": 50, "verdict": "uncertain", "explanation": "Помилка обробки", "sources": []}
            
    except Exception as e:
        print(f"❌ Gemini: {e}")
        return {"error": str(e)}

def check_spamhaus(domain):
    try:
        q = ".".join(reversed(domain.split("."))) + ".zen.spamhaus.org"
        dns.resolver.resolve(q, "A")
        return {"listed": True}
    except dns.resolver.NXDOMAIN:
        return {"listed": False}
    except:
        return {"listed": False}

def check_safe_browsing(url):
    try:
        api = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={SAFE_BROWSING_KEY}"
        payload = {
            "client": {"clientId": "factoryx", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        
        res = requests.post(api, json=payload, timeout=10)
        jd = res.json()
        
        return {"safe": not bool(jd.get("matches"))}
        
    except:
        return {"safe": True}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stats", methods=["GET"])
def get_stats():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM checks")
            total = cur.fetchone()['count']
            
            cur.execute(
                "SELECT COUNT(*) as count FROM checks WHERE DATE(created_at) = CURRENT_DATE"
            )
            today = cur.fetchone()['count']
            
            cur.execute(
                "SELECT COUNT(*) as count FROM checks WHERE created_at >= NOW() - INTERVAL '7 days'"
            )
            week = cur.fetchone()['count']
        
        return jsonify({
            "total_checks": total,
            "today": today,
            "week": week,
            "status": "ok"
        })
        
    except Exception as e:
        print(f"❌ Статистика: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/check", methods=["POST"])
def check_fact():
    data = request.json
    text = (data.get("text") or "").strip()
    link = (data.get("link") or "").strip()
    lang = data.get("lang", "uk")
    
    # Ensure language is supported
    supported_langs = ['uk', 'en', 'es', 'fr', 'de', 'pl', 'it']
    if lang not in supported_langs:
        lang = 'en'
    
    if text or link:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                query_hash = hash_text(text or link[:200])
                
                cur.execute("""
                    SELECT score, verdict, explanation, sources, created_at 
                    FROM checks 
                    WHERE query_hash = %s 
                AND lang = %s
                AND created_at > NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC 
                LIMIT 1
                """, (query_hash, lang))
                
                cached = cur.fetchone()
                if cached:
                    print(f"✅ Cache found! Score: {cached['score']}, lang: {lang}, time: {cached['created_at']}")
                    
                    sources = []
                    if cached['sources']:
                        try:
                            sources = json.loads(cached['sources'])
                        except:
                            sources = []
                    
                    return jsonify({
                        'mode': 'both' if (text and link) else ('text' if text else 'link'),
                        'score': cached['score'],
                        'cached': True,
                        'cached_at': cached['created_at'].isoformat(),
                        'gemini': {
                            'score': cached['score'],
                            'verdict': cached['verdict'] or 'uncertain',
                            'explanation': cached['explanation'] or 'Result from cache',
                            'sources': sources
                        },
                        'google_factcheck': [],
                        'google_search': [],
                        'domain_check': {}
                    })
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
    
    if text and link:
        mode = "both"
    elif text:
        mode = "text"
    else:
        mode = "link"
    
    error_messages = {
        "uk": {
            "no_text": "❌ Введіть текст",
            "text_short": "❌ Введіть текст (мінімум 10 символів та 2 слова)",
            "no_link": "❌ Введіть посилання",
            "question": "❌ Введіть твердження, а не питання",
            "subjective": "❌ Це субʼєктивне твердження",
            "gibberish": "❌ Введіть твердження для перевірки",
            "domain_not_exist": "❌ Посилання не працює - домен не існує або недоступний",
            "page_load_failed": "❌ Не вдалося завантажити сторінку. Перевірте посилання або надішліть текст вручну",
            "no_text_extracted": "❌ Не вдалося витягти текст з посилання. Надішліть текст вручну",
            "phishing": "🚨 НЕБЕЗПЕЧНЕ ПОСИЛАННЯ! Google Safe Browsing виявив (фішинг/шкідливе ПЗ)",
            "spam": "🚨 НЕБЕЗПЕЧНИЙ ДОМЕН! Spamhaus позначив цей домен як шкідливий",
            "blocked_russian": "🚫 Російські джерела не підтримуються",
            "blocked_belarusian": "🚫 Білоруські джерела не підтримуються",
            "blocked_casino": "🚫 Сайти казино та азартних ігор не підтримуються",
            "blocked_adult": "🚫 Сайти дорослого контенту (18+) не підтримуються",
            "blocked_casino_detected": "🚫 Виявлено сайт казино або азартних ігор",
            "blocked_adult_detected": "🚫 Виявлено сайт дорослого контенту 18+"
        },
        "en": {
            "no_text": "❌ Enter text",
            "text_short": "❌ Enter text (minimum 10 characters and 2 words)",
            "no_link": "❌ Enter a link",
            "question": "❌ Enter a statement, not a question",
            "subjective": "❌ This is subjective",
            "gibberish": "❌ Enter valid text",
            "domain_not_exist": "❌ Link doesn't work - domain doesn't exist or unavailable",
            "page_load_failed": "❌ Failed to load page. Check the link or send text manually",
            "no_text_extracted": "❌ Failed to extract text from link. Send text manually",
            "phishing": "🚨 DANGEROUS LINK! Google Safe Browsing detected (phishing/malware)",
            "spam": "🚨 DANGEROUS DOMAIN! Spamhaus blacklisted this domain",
            "blocked_russian": "🚫 Russian sources are not supported",
            "blocked_belarusian": "🚫 Belarusian sources are not supported",
            "blocked_casino": "🚫 Casino and gambling sites are not supported",
            "blocked_adult": "🚫 Adult content sites (18+) are not supported",
            "blocked_casino_detected": "🚫 Casino/gambling site detected",
            "blocked_adult_detected": "🚫 Adult content site (18+) detected"
        },
        "es": {
            "no_text": "❌ Ingresa texto",
            "text_short": "❌ Ingresa texto (mínimo 10 caracteres y 2 palabras)",
            "no_link": "❌ Ingresa un enlace",
            "question": "❌ Ingresa una afirmación, no una pregunta",
            "subjective": "❌ Esto es subjetivo",
            "gibberish": "❌ Ingresa texto válido",
            "domain_not_exist": "❌ El enlace no funciona - dominio no existe o no disponible",
            "page_load_failed": "❌ No se pudo cargar la página. Verifica el enlace o envía texto manualmente",
            "no_text_extracted": "❌ No se pudo extraer texto del enlace. Envía texto manualmente",
            "phishing": "🚨 ¡ENLACE PELIGROSO! Google Safe Browsing detectó (phishing/malware)",
            "spam": "🚨 ¡DOMINIO PELIGROSO! Spamhaus marcó este dominio",
            "blocked_russian": "🚫 Las fuentes rusas no son compatibles",
            "blocked_belarusian": "🚫 Las fuentes bielorrusas no son compatibles",
            "blocked_casino": "🚫 Los sitios de casino y apuestas no son compatibles",
            "blocked_adult": "🚫 Los sitios de contenido adulto (18+) no son compatibles",
            "blocked_casino_detected": "🚫 Sitio de casino/apuestas detectado",
            "blocked_adult_detected": "🚫 Sitio de contenido adulto (18+) detectado"
        },
        "fr": {
            "no_text": "❌ Entrez du texte",
            "text_short": "❌ Entrez du texte (minimum 10 caractères et 2 mots)",
            "no_link": "❌ Entrez un lien",
            "question": "❌ Entrez une affirmation, pas une question",
            "subjective": "❌ C'est subjectif",
            "gibberish": "❌ Entrez du texte valide",
            "domain_not_exist": "❌ Le lien ne fonctionne pas - domaine n'existe pas ou inaccessible",
            "page_load_failed": "❌ Echec du chargement. Vérifiez le lien ou envoyez le texte manuellement",
            "no_text_extracted": "❌ Impossible d'extraire le texte du lien. Envoyez le texte manuellement",
            "phishing": "🚨 LIEN DANGEREUX! Google Safe Browsing a détecté (phishing/malware)",
            "spam": "🚨 DOMAINE DANGEREUX! Spamhaus a marqué ce domaine",
            "blocked_russian": "🚫 Les sources russes ne sont pas supportées",
            "blocked_belarusian": "🚫 Les sources biélorusses ne sont pas supportées",
            "blocked_casino": "🚫 Les sites de casino et jeux ne sont pas supportés",
            "blocked_adult": "🚫 Les sites adultes (18+) ne sont pas supportés",
            "blocked_casino_detected": "🚫 Site de casino/jeux détecté",
            "blocked_adult_detected": "🚫 Site adulte (18+) détecté"
        },
        "de": {
            "no_text": "❌ Text eingeben",
            "text_short": "❌ Text eingeben (mindestens 10 Zeichen und 2 Wörter)",
            "no_link": "❌ Link eingeben",
            "question": "❌ Aussage eingeben, nicht Frage",
            "subjective": "❌ Das ist subjektiv",
            "gibberish": "❌ Gültigen Text eingeben",
            "domain_not_exist": "❌ Link funktioniert nicht - Domain existiert nicht oder nicht erreichbar",
            "page_load_failed": "❌ Seite konnte nicht geladen werden. Link überprüfen oder Text manuell senden",
            "no_text_extracted": "❌ Text konnte nicht aus Link extrahiert werden. Text manuell senden",
            "phishing": "🚨 GEFÄHRLICHER LINK! Google Safe Browsing erkannt (Phishing/Malware)",
            "spam": "🚨 GEFÄHRLICHE DOMAIN! Spamhaus markierte diese Domain",
            "blocked_russian": "🚫 Russische Quellen werden nicht unterstützt",
            "blocked_belarusian": "🚫 Weißrussische Quellen werden nicht unterstützt",
            "blocked_casino": "🚫 Casino- und Glücksspielseiten werden nicht unterstützt",
            "blocked_adult": "🚫 Erwachsenenseiten (18+) werden nicht unterstützt",
            "blocked_casino_detected": "🚫 Casino-/Glücksspielseite erkannt",
            "blocked_adult_detected": "🚫 Erwachsenenseite (18+) erkannt"
        },
        "pl": {
            "no_text": "❌ Wpisz tekst",
            "text_short": "❌ Wpisz tekst (minimum 10 znaków i 2 słowa)",
            "no_link": "❌ Wpisz link",
            "question": "❌ Wpisz stwierdzenie, nie pytanie",
            "subjective": "❌ To jest subiektywne",
            "gibberish": "❌ Wpisz ważny tekst",
            "domain_not_exist": "❌ Link nie działa - domena nie istnieje lub niedostępna",
            "page_load_failed": "❌ Nie udało się załadować strony. Sprawdź link lub wyślij tekst ręcznie",
            "no_text_extracted": "❌ Nie udało się wyodrębnić tekstu z linku. Wyślij tekst ręcznie",
            "phishing": "🚨 NIEBEZPIECZNY LINK! Google Safe Browsing wykrył (phishing/malware)",
            "spam": "🚨 NIEBEZPIECZNA DOMENA! Spamhaus oznaczył tę domenę",
            "blocked_russian": "🚫 Źródła rosyjskie nie są obsługiwane",
            "blocked_belarusian": "🚫 Źródła białoruskie nie są obsługiwane",
            "blocked_casino": "🚫 Witryny kasyn i gier hazardowych nie są obsługiwane",
            "blocked_adult": "🚫 Witryny dorosłe (18+) nie są obsługiwane",
            "blocked_casino_detected": "🚫 Wykryta witryna kasyn/hazardu",
            "blocked_adult_detected": "🚫 Wykryta witryna dorosła (18+)"
        },
        "it": {
            "no_text": "❌ Inserisci testo",
            "text_short": "❌ Inserisci testo (minimo 10 caratteri e 2 parole)",
            "no_link": "❌ Inserisci un link",
            "question": "❌ Inserisci un'affermazione, non una domanda",
            "subjective": "❌ Questo è soggettivo",
            "gibberish": "❌ Inserisci testo valido",
            "domain_not_exist": "❌ Il link non funziona - dominio non esiste o non disponibile",
            "page_load_failed": "❌ Impossibile caricare la pagina. Verifica il link o invia testo manualmente",
            "no_text_extracted": "❌ Impossibile estrarre testo dal link. Invia testo manualmente",
            "phishing": "🚨 LINK PERICOLOSO! Google Safe Browsing ha rilevato (phishing/malware)",
            "spam": "🚨 DOMINIO PERICOLOSO! Spamhaus ha contrassegnato questo dominio",
            "blocked_russian": "🚫 Le fonti russe non sono supportate",
            "blocked_belarusian": "🚫 Le fonti bielorusse non sono supportate",
            "blocked_casino": "🚫 I siti di casinò e giochi non sono supportati",
            "blocked_adult": "🚫 I siti per adulti (18+) non sono supportati",
            "blocked_casino_detected": "🚫 Sito di casinò/gioco rilevato",
            "blocked_adult_detected": "🚫 Sito per adulti (18+) rilevato"
        }
    }
    
    errors = error_messages.get(lang, error_messages["uk"])
    
    if link and is_blocked_source(link):
        block_reason = get_block_reason(link)
        
        if block_reason == "russian":
            return jsonify({"error": errors["blocked_russian"]}), 400
        elif block_reason == "belarusian":
            return jsonify({"error": errors["blocked_belarusian"]}), 400
        elif block_reason == "casino":
            return jsonify({"error": errors["blocked_casino"]}), 400
        elif block_reason == "adult":
            return jsonify({"error": errors["blocked_adult"]}), 400
        else:
            return jsonify({"error": errors["blocked_russian"]}), 400
    
    if mode == "text":
        if not text:
            return jsonify({"error": errors["no_text"]}), 400
        
        words = text.split()
        if len(text) < 10 or len(words) < 2:
            return jsonify({"error": errors["text_short"]}), 400
    
    if mode == "link":
        if not link:
            return jsonify({"error": errors["no_link"]}), 400
    
    if mode == "both":
        if not link:
            return jsonify({"error": errors["no_link"]}), 400
    
    if text and is_question(text):
        return jsonify({"error": errors["question"]}), 400
    
    if text and is_subjective(text):
        return jsonify({"error": errors["subjective"]}), 400
    
    if text and is_gibberish(text):
        return jsonify({"error": errors["gibberish"]}), 400
    
    # Check if text language matches selected interface language
    if text:
        is_valid, error_msg = validate_text_language(text, lang)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
    
    if link and link.startswith("http"):
        domain = urlparse(link).netloc
        print(f"🔍 Перевірка безпеки: {domain}")
        
        try:
            socket.gethostbyname(domain)
            print(f"  ✅ Домен існує")
        except socket.gaierror:
            print(f"  ❌ Домен НЕ існує!")
            return jsonify({"error": errors["domain_not_exist"]}), 400
        
        safe_check = check_safe_browsing(link)
        spam_check = check_spamhaus(domain)
        
        print(f"  Safe Browsing: {safe_check}")
        print(f"  Spamhaus: {spam_check}")
        
        if not safe_check["safe"]:
            print("🚨 НЕБЕЗПЕЧНЕ ПОСИЛАННЯ ВИЯВЛЕНО!")
            return jsonify({"error": errors["phishing"]}), 400
        
        if spam_check["listed"]:
            print("🚨 ДОМЕН В СПАМ-СПИСКУ!")
            return jsonify({"error": errors["spam"]}), 400
        
        if SIGHTENGINE_USER and SIGHTENGINE_SECRET:
            adult_check = check_adult_content_sightengine(link)
            print(f"  🔞 Adult Check: {adult_check}")
            
            if adult_check.get("blocked"):
                print("🚨 ВИЯВЛЕНО ДОРОСЛИЙ КОНТЕНТ!")
                return jsonify({"error": errors["blocked_adult_detected"]}), 400
        
        gambling_check = check_gambling_content(link)
        print(f"  🎰 Gambling Check: {gambling_check}")
        
        if gambling_check.get("blocked"):
            print("🚨 ВИЯВЛЕНО САЙТ КАЗИНО!")
            return jsonify({"error": errors["blocked_casino_detected"]}), 400
        
        # Validate link content language
        is_valid, error_msg = validate_link_language(link, lang)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
    
    page_text = ""
    article_date = None
    
    if link and link.startswith("http"):
        try:
            r = requests.get(link, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.content, "html.parser")
            
            article_date = extract_article_date(soup, link)
            if article_date:
                print(f"📅 Дата статті: {article_date}")
            
            for bad in soup(["script", "style", "header", "footer", "nav"]):
                bad.decompose()
            
            blocks = [
                t.get_text().strip()
                for t in soup.find_all(["p", "article", "section"])
                if len(t.get_text().strip()) > 25
            ]
            
            page_text = " ".join(blocks[:80])
            
            if not text and not page_text:
                print("❌ Порожній page_text")
                return jsonify({"error": errors["no_text_extracted"]}), 400
            
            if not text:
                text = page_text[:500]
                
        except Exception as e:
            print(f"⚠️ Помилка завантаження: {e}")
            if not text:
                return jsonify({"error": errors["page_load_failed"]}), 400
    
    combined = f"{text} {page_text}".strip()
    
    # Always use user's chosen language if provided, otherwise detect
    if lang and lang in ['uk', 'en', 'es', 'fr', 'de', 'pl', 'it']:
        check_lang = lang
        detected = detect_language(combined) if combined else 'en'
    else:
        detected = detect_language(combined) if combined else 'en'
        check_lang = detected
        if check_lang not in ['uk', 'en', 'es', 'fr', 'de', 'pl', 'it']:
            check_lang = 'en'
    
    is_long = len(combined) > 900
    gem = None
    
    print(f"🔍 User language: {lang}, Detected: {detected}, Final language: {check_lang}")
    print(f"🔍 Perplexity check with lang={check_lang}")
    gem = perplexity_check(combined, article_date=article_date, lang=check_lang)
    
    if "error" in gem and GEMINI_KEY:
        print(f"⚠️ Perplexity failed, Gemini backup...")
        gem = gemini_check(combined, long=is_long)
    
    if "error" in gem:
        return jsonify({"error": gem["error"]}), 500
    
    google_fc = google_factcheck(combined, lang=check_lang) if mode != "link" else []
    google_s = google_search(combined, lang=check_lang) if mode != "link" else []
    
    score = int(gem.get("score", 50))
    verdict = gem.get("verdict", "uncertain")
    
    if verdict == "true":
        score += 10
    elif verdict == "false":
        score -= 20
    
    if google_fc:
        score += 5
    
    if google_s:
        score += 3
    
    domain_info = {}
    if link:
        domain = urlparse(link).netloc
        spam = check_spamhaus(domain)
        safe = check_safe_browsing(link)
        domain_info = {"spamhaus": spam, "safe_browsing": safe}
    
    score = max(0, min(score, 100))
    score = round(score / 20) * 20
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            query_hash = hash_text(text or combined[:200])
            url_hash = hash_text(link) if link else None
            
            sources_json = json.dumps(gem.get('sources', []))
            
            cur.execute('''
                INSERT INTO checks (query_hash, url_hash, score, verdict, explanation, sources, lang, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (query_hash, url_hash, score, gem.get('verdict', 'uncertain'), 
                gem.get('explanation', ''), sources_json, check_lang, datetime.now()))
            
            conn.commit()
            print(f"✅ Stats saved: score={score}, lang={check_lang}")
    except Exception as e:
        print(f"❌ Stats: {e}")

    
    result = {
        "mode": mode,
        "original_text": text,
        "processed_text": combined,
        "article_date": article_date,
        "gemini": gem,
        "google_factcheck": google_fc,
        "google_search": google_s,
        "domain_check": domain_info,
        "score": score
    }
    
    return jsonify(result)

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('.', 'sitemap.xml')

@app.route('/robots.txt')
def robots_txt():
    content = """User-agent: *
Allow: /

Sitemap: https://factoryx.com.ua/sitemap.xml"""
    return Response(content, mimetype='text/plain')


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
