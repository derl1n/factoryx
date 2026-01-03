import os
import json
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
import socket
from flask import Flask, request, jsonify, render_template
from urllib.parse import urlparse
from dotenv import load_dotenv
from langdetect import detect
from googletrans import Translator
import dns.resolver
from bs4 import BeautifulSoup
import re
from datetime import datetime
import hashlib

load_dotenv()

# ==========================================================
# DATABASE CONFIGURATION - ЗМІНЕНО ДЛЯ RENDER
# ==========================================================
DATABASE_URL = os.getenv("DATABASE_URL")  # Render автоматично додає це

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

# ==========================================================
# DATABASE FUNCTIONS - ЗМІНЕНО ДЛЯ POSTGRESQL
# ==========================================================
def get_db():
    """Підключення до PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """Ініціалізація бази даних PostgreSQL"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Читаємо SQL з init_db.sql
                with open("init_db.sql", "r", encoding="utf-8") as f:
                    sql = f.read()
                cur.execute(sql)
            conn.commit()
        print("✅ База даних ініціалізована")
    except Exception as e:
        print(f"⚠️ Помилка ініціалізації БД: {e}")

# ==========================================================
# HASHING FUNCTIONS
# ==========================================================
def hash_text(text):
    """Хешує текст за допомогою SHA-256"""
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# ==========================================================
# BLOCKED DOMAINS
# ==========================================================
BLOCKED_DOMAINS = [
    # Російські та білоруські домени
    '.ru', '.рф', '.su',
    '.by',
    'kremlin', 'tass.', 'ria.', 'rbc.', 'kommersant.', 'interfax.',
    'lenta.', 'gazeta.', 'russian.rt.', 'sputnik', 'iz.ru',
    'forbes.ru', 'vedomosti.', 'rossiyskaya-gazeta.', 'rg.ru',
    'belta.by', 'sb.by', 'ont.by',
    # Казино
    'casino', 'казино', 'bet', 'betting', 'ставки', 'poker', 'покер',
    'slots', 'слоты', 'jackpot', 'джекпот', 'gambling', 'азартні',
    'azino', 'vulkan', 'вулкан', 'joycasino', 'slot', 'pin-up',
    'pinup', '1xbet', 'fonbet', 'parimatch', 'leon', 'winline',
    'betfair', 'bwin', '888casino', 'slottica', 'riobet', '777',
    # Дорослий контент (18+)
    'porn', 'порно', 'xxx', 'sex', 'секс', 'adult', 'xvideos',
    'pornhub', 'xnxx', 'redtube', 'youporn', 'tube8', 'spankwire',
    'keezmovies', 'chaturbate', 'livejasmin', 'bongacams', 'stripchat',
    'nude', 'голі', 'naked', 'nsfw', 'erotic', 'erotica', 'hentai',
    'cam4', 'myfreecams', 'camsoda', 'onlyfans', 'manyvids'
]

def is_blocked_source(url):
    """Перевіряє чи джерело заблоковане (РФ/БЛР/Казино/18+)"""
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
    
    # Перевірка на російські/білоруські
    russian_domains = ['.ru', '.рф', '.su', 'kremlin', 'tass.', 'ria.', 'rbc.',
                      'kommersant.', 'interfax.', 'lenta.', 'gazeta.', 'sputnik']
    belarusian_domains = ['.by', 'belta.by', 'sb.by', 'ont.by']
    
    for domain in russian_domains:
        if domain in url_lower:
            return "russian"
    for domain in belarusian_domains:
        if domain in url_lower:
            return "belarusian"
    
    # Перевірка на казино
    casino_keywords = ['casino', 'казино', 'bet', 'betting', 'ставки', 'poker',
                      'покер', 'slots', 'слоты', 'gambling', 'azino', 'vulkan',
                      '1xbet', 'fonbet', 'parimatch', '777']
    for keyword in casino_keywords:
        if keyword in url_lower:
            return "casino"
    
    # Перевірка на 18+
    adult_keywords = ['porn', 'порно', 'xxx', 'sex', 'adult', 'pornhub',
                     'xnxx', 'nude', 'naked', 'nsfw', 'erotic', 'onlyfans']
    for keyword in adult_keywords:
        if keyword in url_lower:
            return "adult"
    
    return None

def filter_sources(sources):
    """Фільтрує джерела, видаляючи заборонені"""
    if not sources:
        return []
    
    filtered = []
    for source in sources:
        if isinstance(source, str):
            if not is_blocked_source(source):
                filtered.append(source)
        elif isinstance(source, dict):
            if not is_blocked_source(source.get('link', '')):
                filtered.append(source)
    
    return filtered

# ==========================================================
# API ПЕРЕВІРКА ADULT/CASINO КОНТЕНТУ
# ==========================================================
def check_adult_content_sightengine(url):
    """Перевіряє URL на дорослий контент через Sightengine API"""
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
        
        # Перевірка на дорослий контент
        nudity = data.get('nudity', {})
        raw_score = nudity.get('raw', 0)
        partial_score = nudity.get('partial', 0)
        
        # Якщо ймовірність дорослого контенту > 50%
        if raw_score > 0.5 or partial_score > 0.6:
            return {"checked": True, "blocked": True, "type": "adult", "confidence": max(raw_score, partial_score)}
        
        return {"checked": True, "blocked": False}
        
    except Exception as e:
        print(f"⚠️ Sightengine error: {e}")
        return {"checked": False, "reason": str(e)}

def check_gambling_content(url):
    """Перевіряє URL на казино через аналіз контенту сторінки"""
    try:
        # Завантажуємо сторінку
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Шукаємо ключові слова казино в тексті
        text_content = soup.get_text().lower()
        gambling_keywords = [
            'casino', 'казино', 'poker', 'покер', 'slots', 'слоти',
            'jackpot', 'джекпот', 'roulette', 'рулетка', 'blackjack',
            'ставки', 'betting', 'gambling', 'азартні ігри',
            'бонус депозит', 'bonus deposit', 'free spins'
        ]
        
        # Рахуємо кількість збігів
        matches = sum(1 for keyword in gambling_keywords if keyword in text_content)
        
        # Якщо знайдено більше 3 ключових слів - ймовірно казино
        if matches >= 3:
            return {"checked": True, "blocked": True, "type": "casino", "matches": matches}
        
        return {"checked": True, "blocked": False}
        
    except Exception as e:
        print(f"⚠️ Gambling check error: {e}")
        return {"checked": False, "reason": str(e)}

def check_safe_browsing_extended(url):
    """Розширена перевірка через Google Safe Browsing"""
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

# ==========================================================
# LANGUAGE DETECTION + TRANSLATION
# ==========================================================
def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

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

# ==========================================================
# QUESTION DETECTION
# ==========================================================
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

# ==========================================================
# SUBJECTIVE DETECTION
# ==========================================================
def is_subjective(text):
    subjective_words = [
        "крутий", "поганий", "жахливий", "добрий", "гарний",
        "я думаю", "мені здається", "вважаю", "на мій погляд",
        "красивий", "огидний"
    ]
    
    t = text.lower()
    return any(w in t for w in subjective_words)

# ==========================================================
# GIBBERISH DETECTION
# ==========================================================
def is_gibberish(text):
    """Перевіряє чи текст є білібердою"""
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

# ==========================================================
# EXTRACT ARTICLE DATE
# ==========================================================
def extract_article_date(soup, url):
    """Витягує дату публікації статті з HTML"""
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

# ==========================================================
# CLEAN CITATIONS
# ==========================================================
def clean_citations(text):
    """Видаляє цитування типу [1], [2], [3]"""
    if not text:
        return text
    
    cleaned = re.sub(r'\[\d+\]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

# ==========================================================
# GOOGLE FACTCHECK
# ==========================================================
def google_factcheck(query):
    try:
        url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={query}&key={GOOGLE_API_KEY}"
        r = requests.get(url, timeout=10)
        claims = r.json().get("claims", [])
        
        filtered_claims = []
        for claim in claims:
            if 'claimReview' in claim:
                has_blocked = False
                for review in claim['claimReview']:
                    if is_blocked_source(review.get('url', '')):
                        has_blocked = True
                        break
                
                if not has_blocked:
                    filtered_claims.append(claim)
            else:
                filtered_claims.append(claim)
        
        return filtered_claims
        
    except:
        return []

# ==========================================================
# GOOGLE SEARCH
# ==========================================================
def google_search(query):
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        res = requests.get(url, params={
            "key": SEARCH_KEY,
            "cx": SEARCH_CX,
            "q": query
        }, timeout=10)
        
        items = res.json().get("items", [])
        results = [
            {
                "title": i.get("title"),
                "snippet": i.get("snippet"),
                "link": i.get("link")
            }
            for i in items[:10]
        ]
        
        filtered = filter_sources(results)
        return filtered[:5]
        
    except:
        return []

# ==========================================================
# PERPLEXITY CHECK
# ==========================================================
def perplexity_check(text, article_date=None):
    """Перевірка через Perplexity Sonar API"""
    try:
        MAX_LENGTH = 1500
        if len(text) > MAX_LENGTH:
            text = text[:MAX_LENGTH] + "..."
        
        API = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_KEY}",
            "Content-Type": "application/json"
        }
        
        date_instruction = ""
        if article_date:
            date_instruction = f"\n⚠️ ВАЖЛИВО: Ця стаття опублікована {article_date}. Перевіряй факти на момент публікації."
        
        source_instruction = (
            "\n📌 ПРІОРИТЕТ ДЖЕРЕЛ (від найважливіших):\n"
            "1️⃣ Українські: Suspilne, Ukrainska Pravda, УНІАН, Kyiv Independent\n"
            "2️⃣ Західні агенції: Reuters, AP, BBC, AFP, CNN, The Guardian\n"
            "3️⃣ Міжнародні: Wikipedia (англійська), DW, Euronews\n"
            "🚫 ЗАБОРОНЕНО: .ru, .рф, .su, .by домени, російські ЗМІ, казино, дорослий контент!\n"
            "⚠️ ВАЖЛИВО: Якщо знайдено тільки заборонені джерела - шукай західні альтернативи або пиши 'Insufficient reliable sources'"
        )
        
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ти експерт з фактчекінгу. Шукай актуальну інформацію в інтернеті. "
                        "Поверни JSON: {\"score\": 0-100, \"verdict\": \"true/false/uncertain\", \"explanation\": \"1-2_речення\"}. "
                        "НЕ використовуй цитування [1], [2]! "
                        "НЕ згадуй у поясненні про заборонені джерела!"
                        f"{date_instruction}"
                        f"{source_instruction}"
                    )
                },
                {
                    "role": "user",
                    "content": f"Перевір це твердження: {text}"
                }
            ],
            "temperature": 0.1,
            "max_tokens": 400,
            "return_citations": True
        }
        
        r = requests.post(API, json=payload, headers=headers, timeout=30)
        
        if r.status_code != 200:
            print(f"❌ Perplexity {r.status_code}")
            return {"error": f"Perplexity API помилка (код {r.status_code})"}
        
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        filtered_citations = filter_sources(citations)
        
        print(f"📊 Джерел: {len(citations)} → після фільтрації: {len(filtered_citations)}")
        
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
                        result["explanation"] = "Недостатньо надійних джерел для перевірки цього твердження."
                    else:
                        result["explanation"] = "Інформація підтверджена кількома незалежними джерелами."
                
                result["sources"] = filtered_citations[:5]
                
                print(f"✅ Perplexity: score={result['score']}, filtered_sources={len(result['sources'])}")
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON decode error: {e}")
                pass
        
        return {
            "score": 50,
            "verdict": "uncertain",
            "explanation": "Недостатньо інформації для остаточної оцінки." if len(filtered_citations) == 0 else "Інформація підтверджена кількома джерелами.",
            "sources": filtered_citations[:5]
        }
        
    except requests.exceptions.Timeout:
        return {"error": "Таймаут запиту"}
    except Exception as e:
        print(f"❌ Perplexity: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

# ==========================================================
# GEMINI CHECK (BACKUP)
# ==========================================================
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

# ==========================================================
# DOMAIN CHECK
# ==========================================================
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

# ==========================================================
# ROUTES
# ==========================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stats", methods=["GET"])
def get_stats():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
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

# ==========================================================
# MAIN FACT CHECK
# ==========================================================
@app.route("/check", methods=["POST"])
def check_fact():
    data = request.json
    text = (data.get("text") or "").strip()
    link = (data.get("link") or "").strip()
    lang = data.get("lang", "uk")
    
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
        }
    }
    
    errors = error_messages.get(lang, error_messages["uk"])
    
    # ПЕРЕВІРКА НА ЗАБОРОНЕНІ САЙТИ (КЛЮЧОВІ СЛОВА)
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
    
    # ПЕРЕВІРКА ПОСИЛАННЯ ЧЕРЕЗ API
    if link and link.startswith("http"):
        domain = urlparse(link).netloc
        print(f"🔍 Перевірка безпеки: {domain}")
        
        try:
            socket.gethostbyname(domain)
            print(f"  ✅ Домен існує")
        except socket.gaierror:
            print(f"  ❌ Домен НЕ існує!")
            return jsonify({"error": errors["domain_not_exist"]}), 400
        
        # Перевірка на фішинг
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
        
        # АВТОМАТИЧНА ПЕРЕВІРКА ADULT КОНТЕНТУ (якщо є API)
        if SIGHTENGINE_USER and SIGHTENGINE_SECRET:
            adult_check = check_adult_content_sightengine(link)
            print(f"  🔞 Adult Check: {adult_check}")
            
            if adult_check.get("blocked"):
                print("🚨 ВИЯВЛЕНО ДОРОСЛИЙ КОНТЕНТ!")
                return jsonify({"error": errors["blocked_adult_detected"]}), 400
        
        # АВТОМАТИЧНА ПЕРЕВІРКА КАЗИНО (через аналіз контенту)
        gambling_check = check_gambling_content(link)
        print(f"  🎰 Gambling Check: {gambling_check}")
        
        if gambling_check.get("blocked"):
            print("🚨 ВИЯВЛЕНО САЙТ КАЗИНО!")
            return jsonify({"error": errors["blocked_casino_detected"]}), 400
    
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
    detected = detect_language(combined)
    
    if detected == "uk":
        query = combined
    elif detected == "ru":
        query = translate_text(combined, "uk")
    elif detected == "en":
        query = combined
    else:
        query = translate_text(combined, "en")
    
    is_long = len(query) > 900
    gem = None
    
    print(f"🔍 Perplexity: {query[:100]}...")
    gem = perplexity_check(query, article_date=article_date)
    
    if "error" in gem and GEMINI_KEY:
        print(f"⚠️ Perplexity failed, Gemini backup...")
        gem = gemini_check(query, long=is_long)
    
    if "error" in gem:
        return jsonify({"error": gem["error"]}), 500
    
    google_fc = google_factcheck(query) if mode != "link" else []
    google_s = google_search(query) if mode != "link" else []
    
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
            with conn.cursor() as cur:
                query_hash = hash_text(text or query[:200])
                url_hash = hash_text(link) if link else None
                
                cur.execute('''
                    INSERT INTO checks (query_hash, url_hash, score, created_at)
                    VALUES (%s, %s, %s, %s)
                ''', (query_hash, url_hash, score, datetime.now()))
            
            conn.commit()
        
        print(f"✅ Статистика збережена: score={score}")
        
    except Exception as e:
        print(f"❌ Статистика: {e}")
    
    result = {
        "mode": mode,
        "original_text": text,
        "processed_text": query,
        "article_date": article_date,
        "gemini": gem,
        "google_factcheck": google_fc,
        "google_search": google_s,
        "domain_check": domain_info,
        "score": score
    }
    
    return jsonify(result)

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
