import os
import time
import requests
import re
from urllib.parse import unquote
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')
FLASK_API = 'https://factoryx.com.ua/check'
TG_API = f"https://api.telegram.org/bot{TOKEN}"

print(f"🤖 Bot Token: {'OK' if TOKEN else 'MISSING'}")
print(f"📡 Flask API: {FLASK_API}")

user_states = {}
user_languages = {} 

MESSAGES = {
    'uk': {
        'welcome': (
            "🔍 Factoryx — AI Fact-Checker Bot\n\n"
            "Перевіряю правдивість інформації за допомогою Perplexity AI!\n\n"
            "🔥 Можливості:\n"
            "✅ Перевіряю текстові твердження\n"
            "🔗 Аналізую статті за посиланням\n"
            "🌐 Працюю в групах\n"
            "🔍 Перевіряю небезпечні посилання\n\n"
            "👇 Обери дію:"
        ),
        'group_welcome': (
            "🔍 Factoryx — AI Fact-Checker Bot\n\n"
            "Перевіряю правдивість інформації за допомогою Perplexity AI!\n\n"
            "🔥 Можливості:\n"
            "✅ Перевіряю текстові твердження\n"
            "🔗 Аналізую статті за посиланням\n"
            "🌐 Працюю в групах\n"
            "🔍 Перевіряю небезпечні посилання\n\n"
            "📋 Команди:\n"
            "/check — Розпочати перевірку\n"
            "/lang — Змінити мову\n"
            "/help — Докладна інструкція\n"
            "/stats — Статистика\n\n"
            "💬 Підтримка: @d2rl1n"
        ),
        'help': (
            "📖 Інструкція:\n\n"
            "Як перевірити:\n"
            "1️⃣ Натисни кнопку \"🔍 Перевірити\"\n"
            "2️⃣ Потім надішли:\n"
            " • Або текст для перевірки (мін. 10 символів)\n"
            " • Або посилання на статтю\n"
            " • Або текст і посилання одночасно\n\n"
            "В групах:\n"
            "• Команда /check працює так само\n"
            "• Бот запитає, що перевірити\n\n"
            "🎯 Оцінки:\n"
            "✅ 80-100 = Ймовірно правда\n"
            "⚠️ 50-79 = Потребує перевірки\n"
            "❌ 0-49 = Ймовірно неправда\n\n"
            "💬 Підтримка: @d2rl1n"
        ),
        'check_btn': '🔍 Перевірити',
        'lang_btn': '🌐 Мова',
        'help_btn': '📖 Інструкція',
        'stats_btn': '📊 Статистика',
        'cancel_btn': '❌ Скасувати',
        'checking': '🔍 Перевіряю...',
        'enter_text': (
            "🔍 Що перевірити?\n\n"
            "Надішли:\n"
            "• Або текст для перевірки (мін. 10 символів)\n"
            "• Або посилання на статтю\n"
            "• Або текст і посилання одночасно\n\n"
            "Для скасування натисни \"❌ Скасувати\""
        ),
        'cancelled': '❌ Перевірку скасовано.',
        'no_active': '💡 Немає активної перевірки.',
        'gibberish': '❌ Введіть твердження для перевірки',
        'short': '❌ Текст занадто короткий (мінімум 10 символів)',
        'unknown_error': '❌ Невідома помилка',
        'probably_true': 'Ймовірно правда',
        'needs_check': 'Потребує перевірки',
        'probably_false': 'Ймовірно неправда',
        'score': 'Оцінка',
        'explanation': 'Пояснення',
        'sources': 'Джерела перевірки',
        'fact_checks': 'Фактчеків',
        'search_results': 'Джерел',
        'unsafe_link': '⚠️ Небезпечне посилання!',
        'spam_domain': '⚠️ Домен у спам-списку!',
        'timeout': '⏱️ Таймаут запиту. Спробуй ще раз.',
        'connection_error': '❌ Сервер не відповідає. Перевір, чи запущено app.py',
        'error_check': '❌ Помилка перевірки. Спробуй ще раз або напиши @d2rl1n',
        'stats_title': '📊 Статистика Factoryx:',
        'stats_total': '📈 Всього перевірок',
        'stats_today': '🗓 Сьогодні',
        'stats_week': '📅 За тиждень',
        'stats_unavailable': '📊 Статистика тимчасово недоступна',
        'no_html_retry': '⚠️ Помилка HTML, відправляю без форматування',
        'start_hint': '💡 Щоб перевірити інформацію:\n\nНатисни \"🔍 Перевірити\"',
        'language_changed': '✅ Мову змінено на 🇺🇦 Українська',
    },
    'en': {
        'welcome': (
            "🔍 Factoryx — AI Fact-Checker Bot\n\n"
            "Verify information with Perplexity AI!\n\n"
            "🔥 Features:\n"
            "✅ Check text statements\n"
            "🔗 Analyze articles by link\n"
            "🌐 Works in groups\n"
            "🔍 Check dangerous links\n\n"
            "👇 Choose an action:"
        ),
        'group_welcome': (
            "🔍 Factoryx — AI Fact-Checker Bot\n\n"
            "Verify information with Perplexity AI!\n\n"
            "🔥 Features:\n"
            "✅ Check text statements\n"
            "🔗 Analyze articles by link\n"
            "🌐 Works in groups\n"
            "🔍 Check dangerous links\n\n"
            "📋 Commands:\n"
            "/check — Start verification\n"
            "/lang — Change language\n"
            "/help — Instructions\n"
            "/stats — Statistics\n\n"
            "💬 Support: @d2rl1n"
        ),
        'help': (
            "📖 Instructions:\n\n"
            "How to verify:\n"
            "1️⃣ Press \"🔍 Check\"\n"
            "2️⃣ Then send:\n"
            " • Or text to verify (min. 10 characters)\n"
            " • Or link to article\n"
            " • Or text and link together\n\n"
            "In groups:\n"
            "• Command /check works the same way\n"
            "• Bot will ask what to check\n\n"
            "🎯 Scores:\n"
            "✅ 80-100 = Likely true\n"
            "⚠️ 50-79 = Needs verification\n"
            "❌ 0-49 = Likely false\n\n"
            "💬 Support: @d2rl1n"
        ),
        'check_btn': '🔍 Check',
        'lang_btn': '🌐 Language',
        'help_btn': '📖 Help',
        'stats_btn': '📊 Stats',
        'cancel_btn': '❌ Cancel',
        'checking': '🔍 Checking...',
        'enter_text': (
            "🔍 What to verify?\n\n"
            "Send:\n"
            "• Text to verify (min. 10 characters)\n"
            "• Or link to article\n"
            "• Or text and link together\n\n"
            "To cancel press \"❌ Cancel\""
        ),
        'cancelled': '❌ Verification cancelled.',
        'no_active': '💡 No active verification.',
        'gibberish': '❌ Enter a statement to verify',
        'short': '❌ Text too short (minimum 10 characters)',
        'unknown_error': '❌ Unknown error',
        'probably_true': 'Likely true',
        'needs_check': 'Needs verification',
        'probably_false': 'Likely false',
        'score': 'Score',
        'explanation': 'Explanation',
        'sources': 'Verification sources',
        'fact_checks': 'Fact checks',
        'search_results': 'Results',
        'unsafe_link': '⚠️ Unsafe link!',
        'spam_domain': '⚠️ Domain is blacklisted!',
        'timeout': '⏱️ Request timeout. Try again.',
        'connection_error': '❌ Server not responding. Check if app.py is running',
        'error_check': '❌ Verification error. Try again or contact @d2rl1n',
        'stats_title': '📊 Factoryx Statistics:',
        'stats_total': '📈 Total checks',
        'stats_today': '🗓 Today',
        'stats_week': '📅 This week',
        'stats_unavailable': '📊 Statistics temporarily unavailable',
        'no_html_retry': '⚠️ HTML error, sending without formatting',
        'start_hint': '💡 To verify information:\n\nPress \"🔍 Check\"',
        'language_changed': '✅ Language changed to 🇬🇧 English',
    },
    'es': {
        'welcome': "🔍 Factoryx — Bot de Verificación de Hechos con IA\n\n¡Verifico la veracidad de la información con Perplexity AI!\n\n🔥 Características:\n✅ Verifico afirmaciones de texto\n🔗 Analizo artículos por enlace\n🌐 Funciono en grupos\n🔍 Verifico enlaces peligrosos\n\n👇 Elige una acción:",
        'group_welcome': "🔍 Factoryx — Bot de Verificación de Hechos con IA\n\n¡Verifico la veracidad de la información!\n\n📋 Comandos:\n/check — Iniciar verificación\n/lang — Cambiar idioma\n/help — Instrucciones\n/stats — Estadísticas\n\n💬 Soporte: @d2rl1n",
        'help': "📖 Instrucciones:\n\nCómo verificar:\n1️⃣ Presiona \"🔍 Verificar\"\n2️⃣ Luego envía:\n • Texto para verificar (mín. 10 caracteres)\n • O enlace a artículo\n • O texto y enlace juntos\n\nEn grupos:\n• El comando /check funciona igual\n• El bot te preguntará qué verificar\n\n🎯 Puntuaciones:\n✅ 80-100 = Probablemente verdad\n⚠️ 50-79 = Necesita verificación\n❌ 0-49 = Probablemente falso\n\n💬 Soporte: @d2rl1n",
        'check_btn': '🔍 Verificar',
        'lang_btn': '🌐 Idioma',
        'help_btn': '📖 Ayuda',
        'stats_btn': '📊 Estadísticas',
        'cancel_btn': '❌ Cancelar',
        'checking': '🔍 Verificando...',
        'enter_text': "🔍 ¿Qué verificar?\n\nEnvía:\n• Texto para verificar (mín. 10 caracteres)\n• O enlace\n• O ambos\n\nPara cancelar presiona \"❌ Cancelar\"",
        'cancelled': '❌ Verificación cancelada.',
        'no_active': '💡 Sin verificación activa.',
        'gibberish': '❌ Ingresa una afirmación válida',
        'short': '❌ Texto muy corto (mínimo 10 caracteres)',
        'unknown_error': '❌ Error desconocido',
        'probably_true': 'Probablemente verdad',
        'needs_check': 'Necesita verificación',
        'probably_false': 'Probablemente falso',
        'score': 'Puntuación',
        'explanation': 'Explicación',
        'sources': 'Fuentes de verificación',
        'fact_checks': 'Verificaciones de hechos',
        'search_results': 'Resultados',
        'unsafe_link': '⚠️ ¡Enlace inseguro!',
        'spam_domain': '⚠️ ¡Dominio en lista negra!',
        'timeout': '⏱️ Tiempo agotado. Intenta de nuevo.',
        'connection_error': '❌ Servidor sin respuesta. Comprueba si app.py está ejecutándose',
        'error_check': '❌ Error en verificación. Intenta de nuevo o contacta @d2rl1n',
        'stats_title': '📊 Estadísticas de Factoryx:',
        'stats_total': '📈 Verificaciones totales',
        'stats_today': '🗓 Hoy',
        'stats_week': '📅 Esta semana',
        'stats_unavailable': '📊 Estadísticas no disponibles',
        'no_html_retry': '⚠️ Error HTML, enviando sin formato',
        'start_hint': '💡 Para verificar información:\n\nPresiona \"🔍 Verificar\"',
        'language_changed': '✅ Idioma cambiado a 🇪🇸 Español',
    },
    'fr': {
        'welcome': "🔍 Factoryx — Bot de Vérification des Faits par IA\n\nJe vérifie la véracité de l'information avec Perplexity AI!\n\n🔥 Caractéristiques:\n✅ Je vérifie les déclarations textuelles\n🔗 J'analyse les articles par lien\n🌐 Je fonctionne dans les groupes\n🔍 Je vérifie les liens dangereux\n\n👇 Choisissez une action:",
        'group_welcome': "🔍 Factoryx — Bot de Vérification des Faits par IA\n\nJe vérifie la véracité de l'information!\n\n📋 Commandes:\n/check — Commencer la vérification\n/lang — Changer de langue\n/help — Instructions\n/stats — Statistiques\n\n💬 Support: @d2rl1n",
        'help': "📖 Instructions:\n\nComment vérifier:\n1️⃣ Appuyez sur \"🔍 Vérifier\"\n2️⃣ Puis envoyez:\n • Texte à vérifier (min. 10 caractères)\n • Ou lien article\n • Ou les deux\n\nDans les groupes:\n• La commande /check fonctionne de la même façon\n• Le bot vous demandera ce à vérifier\n\n🎯 Scores:\n✅ 80-100 = Probablement vrai\n⚠️ 50-79 = À vérifier\n❌ 0-49 = Probablement faux\n\n💬 Support: @d2rl1n",
        'check_btn': '🔍 Vérifier',
        'lang_btn': '🌐 Langue',
        'help_btn': '📖 Aide',
        'stats_btn': '📊 Statistiques',
        'cancel_btn': '❌ Annuler',
        'checking': '🔍 Vérification en cours...',
        'enter_text': "🔍 Qu'y a-t-il à vérifier?\n\nEnvoyez:\n• Texte à vérifier (min. 10 caractères)\n• Ou lien\n• Ou les deux\n\nPour annuler appuyez sur \"❌ Annuler\"",
        'cancelled': '❌ Vérification annulée.',
        'no_active': '💡 Pas de vérification active.',
        'gibberish': '❌ Entrez une déclaration valide',
        'short': '❌ Texte trop court (minimum 10 caractères)',
        'unknown_error': '❌ Erreur inconnue',
        'probably_true': 'Probablement vrai',
        'needs_check': 'À vérifier',
        'probably_false': 'Probablement faux',
        'score': 'Score',
        'explanation': 'Explication',
        'sources': 'Sources de vérification',
        'fact_checks': 'Vérifications de faits',
        'search_results': 'Résultats',
        'unsafe_link': '⚠️ Lien dangereux!',
        'spam_domain': '⚠️ Domaine sur liste noire!',
        'timeout': '⏱️ Délai dépassé. Réessayez.',
        'connection_error': '❌ Serveur ne répond pas. Vérifiez si app.py est en cours d\'exécution',
        'error_check': '❌ Erreur de vérification. Réessayez ou contactez @d2rl1n',
        'stats_title': '📊 Statistiques Factoryx:',
        'stats_total': '📈 Vérifications totales',
        'stats_today': '🗓 Aujourd\'hui',
        'stats_week': '📅 Cette semaine',
        'stats_unavailable': '📊 Statistiques indisponibles',
        'no_html_retry': '⚠️ Erreur HTML, envoi sans formatage',
        'start_hint': '💡 Pour vérifier:\n\nAppuyez sur \"🔍 Vérifier\"',
        'language_changed': '✅ Langue changée en 🇫🇷 Français',
    },
    'de': {
        'welcome': "🔍 Factoryx — KI-Faktenchecker-Bot\n\nIch überprüfe die Richtigkeit von Informationen mit Perplexity AI!\n\n🔥 Funktionen:\n✅ Ich überprüfe Textaussagen\n🔗 Ich analysiere Artikel nach Link\n🌐 Ich arbeite in Gruppen\n🔍 Ich überprüfe gefährliche Links\n\n👇 Wähle eine Aktion:",
        'group_welcome': "🔍 Factoryx — KI-Faktenchecker-Bot\n\nIch überprüfe die Richtigkeit von Informationen!\n\n📋 Befehle:\n/check — Überprüfung starten\n/lang — Sprache ändern\n/help — Anleitung\n/stats — Statistiken\n\n💬 Unterstützung: @d2rl1n",
        'help': "📖 Anleitung:\n\nWie überprüfen:\n1️⃣ Drücke \"🔍 Überprüfen\"\n2️⃣ Dann sende:\n • Text zum Überprüfen (min. 10 Zeichen)\n • Oder Artikel-Link\n • Oder beides\n\nIn Gruppen:\n• Der Befehl /check funktioniert gleich\n• Der Bot fragt, was zu überprüfen ist\n\n🎯 Bewertungen:\n✅ 80-100 = Wahrscheinlich wahr\n⚠️ 50-79 = Überprüfung erforderlich\n❌ 0-49 = Wahrscheinlich falsch\n\n💬 Unterstützung: @d2rl1n",
        'check_btn': '🔍 Überprüfen',
        'lang_btn': '🌐 Sprache',
        'help_btn': '📖 Hilfe',
        'stats_btn': '📊 Statistiken',
        'cancel_btn': '❌ Abbrechen',
        'checking': '🔍 Wird überprüft...',
        'enter_text': "🔍 Was überprüfen?\n\nSende:\n• Text zum Überprüfen (min. 10 Zeichen)\n• Oder Link\n• Oder beides\n\nZum Abbrechen drücke \"❌ Abbrechen\"",
        'cancelled': '❌ Überprüfung abgebrochen.',
        'no_active': '💡 Keine aktive Überprüfung.',
        'gibberish': '❌ Geben Sie eine gültige Aussage ein',
        'short': '❌ Text zu kurz (mindestens 10 Zeichen)',
        'unknown_error': '❌ Unbekannter Fehler',
        'probably_true': 'Wahrscheinlich wahr',
        'needs_check': 'Überprüfung erforderlich',
        'probably_false': 'Wahrscheinlich falsch',
        'score': 'Bewertung',
        'explanation': 'Erklärung',
        'sources': 'Überprüfungsquellen',
        'fact_checks': 'Faktenprüfungen',
        'search_results': 'Ergebnisse',
        'unsafe_link': '⚠️ Unsicherer Link!',
        'spam_domain': '⚠️ Domain auf schwarzer Liste!',
        'timeout': '⏱️ Zeitüberschreitung. Versuchen Sie es erneut.',
        'connection_error': '❌ Server antwortet nicht. Überprüfen Sie, ob app.py ausgeführt wird',
        'error_check': '❌ Überprüfungsfehler. Versuchen Sie es erneut oder kontaktieren Sie @d2rl1n',
        'stats_title': '📊 Factoryx-Statistiken:',
        'stats_total': '📈 Überprüfungen insgesamt',
        'stats_today': '🗓 Heute',
        'stats_week': '📅 Diese Woche',
        'stats_unavailable': '📊 Statistiken nicht verfügbar',
        'no_html_retry': '⚠️ HTML-Fehler, ohne Formatierung senden',
        'start_hint': '💡 Zum Überprüfen:\n\nDrücke \"🔍 Überprüfen\"',
        'language_changed': '✅ Sprache auf 🇩🇪 Deutsch geändert',
    },
    'pl': {
        'welcome': "🔍 Factoryx — Bot Weryfikacji Faktów z AI\n\nWeryfikuję prawdziwość informacji za pomocą Perplexity AI!\n\n🔥 Funkcje:\n✅ Weryfikuję oświadczenia tekstowe\n🔗 Analizuję artykuły po linku\n🌐 Działam w grupach\n🔍 Sprawdzam niebezpieczne linki\n\n👇 Wybierz akcję:",
        'group_welcome': "🔍 Factoryx — Bot Weryfikacji Faktów z AI\n\nWeryfikuję prawdziwość informacji!\n\n📋 Komendy:\n/check — Rozpocząć weryfikację\n/lang — Zmienić język\n/help — Instrukcje\n/stats — Statystyki\n\n💬 Wsparcie: @d2rl1n",
        'help': "📖 Instrukcje:\n\nJak weryfikować:\n1️⃣ Naciśnij \"🔍 Sprawdź\"\n2️⃣ Następnie wyślij:\n • Tekst do weryfikacji (min. 10 znaków)\n • Lub link do artykułu\n • Lub jedno i drugie\n\nW grupach:\n• Komenda /check działa tak samo\n• Bot zapyta, co sprawdzić\n\n🎯 Oceny:\n✅ 80-100 = Prawdopodobnie prawda\n⚠️ 50-79 = Wymaga weryfikacji\n❌ 0-49 = Prawdopodobnie fałsz\n\n💬 Wsparcie: @d2rl1n",
        'check_btn': '🔍 Sprawdź',
        'lang_btn': '🌐 Język',
        'help_btn': '📖 Pomoc',
        'stats_btn': '📊 Statystyki',
        'cancel_btn': '❌ Anuluj',
        'checking': '🔍 Sprawdzanie...',
        'enter_text': "🔍 Co sprawdzić?\n\nWyślij:\n• Tekst do weryfikacji (min. 10 znaków)\n• Lub link\n• Lub jedno i drugie\n\nAby anulować naciśnij \"❌ Anuluj\"",
        'cancelled': '❌ Weryfikacja anulowana.',
        'no_active': '💡 Brak aktywnej weryfikacji.',
        'gibberish': '❌ Wprowadź ważne stwierdzenie',
        'short': '❌ Tekst za krótki (minimum 10 znaków)',
        'unknown_error': '❌ Nieznany błąd',
        'probably_true': 'Prawdopodobnie prawda',
        'needs_check': 'Wymaga weryfikacji',
        'probably_false': 'Prawdopodobnie fałsz',
        'score': 'Ocena',
        'explanation': 'Wyjaśnienie',
        'sources': 'Źródła weryfikacji',
        'fact_checks': 'Sprawdzenia faktów',
        'search_results': 'Wyniki',
        'unsafe_link': '⚠️ Niebezpieczny link!',
        'spam_domain': '⚠️ Domena na czarnej liście!',
        'timeout': '⏱️ Przekroczenie limitu czasu. Spróbuj ponownie.',
        'connection_error': '❌ Serwer nie odpowiada. Sprawdź, czy app.py jest uruchomiony',
        'error_check': '❌ Błąd weryfikacji. Spróbuj ponownie lub skontaktuj się z @d2rl1n',
        'stats_title': '📊 Statystyki Factoryx:',
        'stats_total': '📈 Weryfikacji razem',
        'stats_today': '🗓 Dzisiaj',
        'stats_week': '📅 Ten tydzień',
        'stats_unavailable': '📊 Statystyki niedostępne',
        'no_html_retry': '⚠️ Błąd HTML, wysyłam bez formatowania',
        'start_hint': '💡 Do weryfikacji:\n\nNaciśnij \"🔍 Sprawdź\"',
        'language_changed': '✅ Język zmieniony na 🇵🇱 Polski',
    },
    'it': {
        'welcome': "🔍 Factoryx — Bot di Verifica dei Fatti con AI\n\nVerificо la veridicità delle informazioni con Perplexity AI!\n\n🔥 Funzioni:\n✅ Verifico affermazioni di testo\n🔗 Analizzo articoli tramite link\n🌐 Funziono nei gruppi\n🔍 Verifico link pericolosi\n\n👇 Scegli un'azione:",
        'group_welcome': "🔍 Factoryx — Bot di Verifica dei Fatti con AI\n\nVerificо la veridicità delle informazioni!\n\n📋 Comandi:\n/check — Avvia verifica\n/lang — Cambia lingua\n/help — Istruzioni\n/stats — Statistiche\n\n💬 Assistenza: @d2rl1n",
        'help': "📖 Istruzioni:\n\nCome verificare:\n1️⃣ Premi \"🔍 Verifica\"\n2️⃣ Poi invia:\n • Testo da verificare (min. 10 caratteri)\n • O link articolo\n • O entrambi\n\nNei gruppi:\n• Il comando /check funziona allo stesso modo\n• Il bot ti chiederà cosa verificare\n\n🎯 Punteggi:\n✅ 80-100 = Probabilmente vero\n⚠️ 50-79 = Necessita verifica\n❌ 0-49 = Probabilmente falso\n\n💬 Assistenza: @d2rl1n",
        'check_btn': '🔍 Verifica',
        'lang_btn': '🌐 Lingua',
        'help_btn': '📖 Aiuto',
        'stats_btn': '📊 Statistiche',
        'cancel_btn': '❌ Annulla',
        'checking': '🔍 Verifica in corso...',
        'enter_text': "🔍 Cosa verificare?\n\nInvia:\n• Testo da verificare (min. 10 caratteri)\n• O link\n• O entrambi\n\nPer annullare premi \"❌ Annulla\"",
        'cancelled': '❌ Verifica annullata.',
        'no_active': '💡 Nessuna verifica attiva.',
        'gibberish': '❌ Inserisci un\'affermazione valida',
        'short': '❌ Testo troppo corto (minimo 10 caratteri)',
        'unknown_error': '❌ Errore sconosciuto',
        'probably_true': 'Probabilmente vero',
        'needs_check': 'Necessita verifica',
        'probably_false': 'Probabilmente falso',
        'score': 'Punteggio',
        'explanation': 'Spiegazione',
        'sources': 'Fonti di verifica',
        'fact_checks': 'Verifiche dei fatti',
        'search_results': 'Risultati',
        'unsafe_link': '⚠️ Link pericoloso!',
        'spam_domain': '⚠️ Dominio nella lista nera!',
        'timeout': '⏱️ Timeout. Riprova.',
        'connection_error': '❌ Server non risponde. Verifica se app.py è in esecuzione',
        'error_check': '❌ Errore di verifica. Riprova o contatta @d2rl1n',
        'stats_title': '📊 Statistiche Factoryx:',
        'stats_total': '📈 Verifiche totali',
        'stats_today': '🗓 Oggi',
        'stats_week': '📅 Questa settimana',
        'stats_unavailable': '📊 Statistiche non disponibili',
        'no_html_retry': '⚠️ Errore HTML, invio senza formattazione',
        'start_hint': '💡 Per verificare:\n\nPremi \"🔍 Verifica\"',
        'language_changed': '✅ Lingua cambiata in 🇮🇹 Italiano',
    }
}

def get_user_language(chat_id):
    """Get user's language preference"""
    return user_languages.get(chat_id, 'uk')

def set_user_language(chat_id, lang):
    """Set user's language preference"""
    user_languages[chat_id] = lang

def get_message(msg_key, chat_id, **kwargs):
    """Get translated message"""
    lang = get_user_language(chat_id)
    msg = MESSAGES.get(lang, {}).get(msg_key) or MESSAGES['en'].get(msg_key, msg_key)
    for key, value in kwargs.items():
        msg = msg.replace(f'{{{key}}}', str(value))
    return msg

def get_main_keyboard(chat_id):
    """Main keyboard for private chats"""
    lang = get_user_language(chat_id)
    return {
        "keyboard": [
            [{"text": get_message('check_btn', chat_id)}],
            [{"text": get_message('help_btn', chat_id)}, {"text": get_message('stats_btn', chat_id)}],
            [{"text": get_message('lang_btn', chat_id)}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_cancel_keyboard(chat_id):
    """Keyboard with cancel"""
    return {
        "keyboard": [
            [{"text": get_message('cancel_btn', chat_id)}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_language_keyboard():
    """Language selection keyboard"""
    return {
        "inline_keyboard": [
            [{"text": "🇺🇦 Українська", "callback_data": "lang_uk"}, {"text": "🇬🇧 English", "callback_data": "lang_en"}],
            [{"text": "🇪🇸 Español", "callback_data": "lang_es"}, {"text": "🇫🇷 Français", "callback_data": "lang_fr"}],
            [{"text": "🇩🇪 Deutsch", "callback_data": "lang_de"}, {"text": "🇵🇱 Polski", "callback_data": "lang_pl"}],
            [{"text": "🇮🇹 Italiano", "callback_data": "lang_it"}]
        ]
    }

def get_updates(offset=None):
    params = {'offset': offset, 'timeout': 30}
    r = requests.get(f"{TG_API}/getUpdates", params=params, timeout=40)
    return r.json() if r.ok else {'ok': False}

def send_msg(chat_id, text, parse_mode='HTML', reply_to=None, keyboard=None):
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    if reply_to:
        data['reply_to_message_id'] = reply_to
    if keyboard:
        data['reply_markup'] = keyboard
    response = requests.post(f"{TG_API}/sendMessage", json=data)
    return response.json() if response.ok else None

def set_bot_commands():
    commands = [
        {"command": "check", "description": "Start verification"},
        {"command": "lang", "description": "Change language"},
        {"command": "cancel", "description": "Cancel verification"},
        {"command": "help", "description": "Instructions"},
        {"command": "stats", "description": "Statistics"},
        {"command": "start", "description": "Start bot"}
    ]
    try:
        requests.post(f"{TG_API}/setMyCommands", json={"commands": commands})
        print("✅ Commands set")
    except Exception as e:
        print(f"⚠️ Commands error: {e}")

def extract_text_and_link(message):
    urls = re.findall(r'https?://[^\s]+', message)
    link = urls[0] if urls else ""
    text = re.sub(r'https?://[^\s]+', '', message).strip()
    return text, link

def normalize_command(text):
    return re.sub(r'@\w+', '', text).strip()

def escape_html(text):
    if not text:
        return text
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def get_domain_name(url):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        if 'wikipedia' in domain:
            return 'Wikipedia'
        return domain
    except:
        return 'Джерело'

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

def check_fact(text, link, chat_id, chat_type):
    try:
        lang = get_user_language(chat_id)
        
        if text and is_gibberish(text):
            send_msg(chat_id, get_message('gibberish', chat_id), 
                    keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
            return
        
        send_msg(chat_id, get_message('checking', chat_id), 
                keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
        
        payload = {'text': text, 'link': link, 'lang': lang}
        r = requests.post(FLASK_API, json=payload, timeout=30)
        
        if r.status_code != 200:
            try:
                error_data = r.json()
                error = error_data.get('error', get_message('unknown_error', chat_id))
            except:
                error = f"Error {r.status_code}"
            send_msg(chat_id, escape_html(error), 
                    keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
            return
        
        data = r.json()
        if 'error' in data:
            send_msg(chat_id, escape_html(data['error']), 
                    keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
            return
        
        score = data.get('score', 50)
        gemini = data.get('gemini', {})
        explanation = gemini.get('explanation', '')[:800]
        sources = gemini.get('sources', [])
        google_fc = data.get('google_factcheck', [])
        google_s = data.get('google_search', [])
        domain_check = data.get('domain_check', {})
        
        if score >= 80:
            emoji = "✅"
            label = get_message('probably_true', chat_id)
        elif score >= 50:
            emoji = "⚠️"
            label = get_message('needs_check', chat_id)
        else:
            emoji = "❌"
            label = get_message('probably_false', chat_id)
        
        reply = f"{emoji} {label}\n\n"
        reply += f"📊 {get_message('score', chat_id)}: {score}/100\n\n"
        
        if explanation:
            explanation_clean = escape_html(explanation)
            reply += f"💬 {get_message('explanation', chat_id)}:\n{explanation_clean}\n\n"
        
        if sources:
            reply += f"🔗 {get_message('sources', chat_id)}:\n"
            for i, src in enumerate(sources[:5], 1):
                domain = get_domain_name(src)
                reply += f'{i}. <a href="{src}">{domain}</a>\n'
            reply += "\n"
        
        if google_fc:
            reply += f"📰 {get_message('fact_checks', chat_id)}: {len(google_fc)}\n"
        if google_s:
            reply += f"🔍 {get_message('search_results', chat_id)}: {len(google_s)}\n"
        
        if link and domain_check:
            sb = domain_check.get('safe_browsing', {})
            spam = domain_check.get('spamhaus', {})
            if not sb.get('safe', True):
                reply += f"\n{get_message('unsafe_link', chat_id)}"
            if spam.get('listed', False):
                reply += f"\n{get_message('spam_domain', chat_id)}"
        
        result = send_msg(chat_id, reply, parse_mode='HTML', 
                         keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
        
        if not result:
            print(get_message('no_html_retry', chat_id))
            reply_plain = re.sub(r'<[^>]+>', '', reply)
            send_msg(chat_id, reply_plain, parse_mode=None, 
                    keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
        
        print("✅ Verification completed")
        
    except requests.exceptions.Timeout:
        send_msg(chat_id, get_message('timeout', chat_id), 
                keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
    except requests.exceptions.ConnectionError:
        send_msg(chat_id, get_message('connection_error', chat_id), 
                keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
    except Exception as e:
        print(f"💥 Verification error: {e}")
        import traceback
        traceback.print_exc()
        send_msg(chat_id, get_message('error_check', chat_id), 
                keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)

app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Flask started on port {port}")
    app.run(host='0.0.0.0', port=port)

def main():
    offset = None
    set_bot_commands()
    print("🚀 Factoryx Bot started!")
    
    while True:
        updates = get_updates(offset)
        if not updates.get('ok', False) or not updates.get('result'):
            time.sleep(2)
            continue
        
        for u in updates['result']:
            offset = u['update_id'] + 1
            
            callback_query = u.get('callback_query')
            if callback_query:
                callback_data = callback_query.get('data')
                chat_id = callback_query.get('from', {}).get('id')
                message_id = callback_query.get('message', {}).get('message_id')
                
                if callback_data and callback_data.startswith('lang_'):
                    lang = callback_data.replace('lang_', '')
                    if lang in ['uk', 'en', 'es', 'fr', 'de', 'pl', 'it']:
                        set_user_language(chat_id, lang)
                        response_msg = get_message('language_changed', chat_id)
                        
                        requests.post(f"{TG_API}/answerCallbackQuery", 
                                    json={"callback_query_id": callback_query.get('id'),
                                          "text": response_msg,
                                          "show_alert": False})
                        
                        send_msg(chat_id, get_message('welcome', chat_id), 
                                keyboard=get_main_keyboard(chat_id))
                continue
            
            message = u.get('message', {})
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            chat_type = chat.get('type', 'private')
            text = message.get('text', '').strip()
            new_chat_member = message.get('new_chat_member')
            
            if not chat_id:
                continue
            
            if new_chat_member:
                bot_info_response = requests.get(f"{TG_API}/getMe").json()
                bot_id = bot_info_response.get('result', {}).get('id')
                if new_chat_member.get('id') == bot_id:
                    send_msg(chat_id, get_message('group_welcome', chat_id))
                    print(f"✅ Added to group: {chat_id}")
                continue
            
            original_text = text
            text_lower = text.lower()
            
            if chat_type in ['group', 'supergroup']:
                text = normalize_command(text)
            
            print(f"📨 [{chat_type}] {chat_id}: {text[:40]}...")
            
            if chat_type == 'private':
                check_btn = get_message('check_btn', chat_id).lower()
                cancel_btn = get_message('cancel_btn', chat_id).lower()
                help_btn = get_message('help_btn', chat_id).lower()
                stats_btn = get_message('stats_btn', chat_id).lower()
                lang_btn = get_message('lang_btn', chat_id).lower()
                
                if text_lower == check_btn or text == '/check':
                    user_states[chat_id] = 'waiting_for_input'
                    send_msg(chat_id, get_message('enter_text', chat_id), 
                            keyboard=get_cancel_keyboard(chat_id))
                    continue
                
                elif text_lower == cancel_btn or text == '/cancel':
                    if chat_id in user_states:
                        user_states.pop(chat_id, None)
                        send_msg(chat_id, get_message('cancelled', chat_id), 
                                keyboard=get_main_keyboard(chat_id))
                    else:
                        send_msg(chat_id, get_message('no_active', chat_id), 
                                keyboard=get_main_keyboard(chat_id))
                    continue
                
                elif text_lower == lang_btn or text == '/lang':
                    send_msg(chat_id, "🌐 Choose language:", 
                            keyboard=get_language_keyboard())
                    continue
                
                elif text_lower == help_btn or text == '/help':
                    send_msg(chat_id, get_message('help', chat_id), 
                            keyboard=get_main_keyboard(chat_id))
                    continue
                
                elif text_lower == stats_btn or text == '/stats':
                    try:
                        stats = requests.get(f"{FLASK_API.replace('/check', '/stats')}", 
                                           timeout=10).json()
                        total = stats.get('total_checks', 0)
                        today = stats.get('today', 0)
                        week = stats.get('week', 0)
                        reply = f"{get_message('stats_title', chat_id)}\n\n"
                        reply += f"{get_message('stats_total', chat_id)}: {total}\n"
                        reply += f"{get_message('stats_today', chat_id)}: {today}\n"
                        reply += f"{get_message('stats_week', chat_id)}: {week}"
                        send_msg(chat_id, reply, keyboard=get_main_keyboard(chat_id))
                    except Exception as e:
                        print(f"Stats error: {e}")
                        send_msg(chat_id, get_message('stats_unavailable', chat_id), 
                                keyboard=get_main_keyboard(chat_id))
                    continue
                
                elif text == '/start':
                    user_states.pop(chat_id, None)
                    send_msg(chat_id, get_message('welcome', chat_id), 
                            keyboard=get_main_keyboard(chat_id))
                    continue
            
            if chat_type in ['group', 'supergroup']:
                if text == '/start':
                    user_states.pop(chat_id, None)
                    send_msg(chat_id, get_message('group_welcome', chat_id))
                    continue
                
                elif text == '/check':
                    user_states[chat_id] = 'waiting_for_input'
                    send_msg(chat_id, get_message('enter_text', chat_id))
                    continue
                
                elif text == '/lang':
                    send_msg(chat_id, "🌐 Choose language:", 
                            keyboard=get_language_keyboard())
                    continue
                
                elif text == '/cancel':
                    if chat_id in user_states:
                        user_states.pop(chat_id, None)
                        send_msg(chat_id, get_message('cancelled', chat_id) + "\n\n/check")
                    else:
                        send_msg(chat_id, get_message('no_active', chat_id) + "\n\n/check")
                    continue
                
                elif text == '/help':
                    send_msg(chat_id, get_message('help', chat_id))
                    continue
                
                elif text == '/stats':
                    try:
                        stats = requests.get(f"{FLASK_API.replace('/check', '/stats')}", 
                                           timeout=10).json()
                        total = stats.get('total_checks', 0)
                        today = stats.get('today', 0)
                        week = stats.get('week', 0)
                        reply = f"{get_message('stats_title', chat_id)}\n\n"
                        reply += f"{get_message('stats_total', chat_id)}: {total}\n"
                        reply += f"{get_message('stats_today', chat_id)}: {today}\n"
                        reply += f"{get_message('stats_week', chat_id)}: {week}"
                        send_msg(chat_id, reply)
                    except Exception as e:
                        print(f"Stats error: {e}")
                        send_msg(chat_id, get_message('stats_unavailable', chat_id))
                    continue
                
                if not original_text.startswith('/'):
                    if user_states.get(chat_id) != 'waiting_for_input':
                        continue
            
            if user_states.get(chat_id) == 'waiting_for_input':
                check_text = original_text
                
                if not check_text or len(check_text.strip()) < 10:
                    send_msg(chat_id, get_message('short', chat_id), 
                            keyboard=get_main_keyboard(chat_id) if chat_type == 'private' else None)
                    continue
                
                extracted_text, link = extract_text_and_link(check_text)
                check_fact(extracted_text, link, chat_id, chat_type)
                user_states.pop(chat_id, None)
                continue
            
            if chat_type == 'private' and not text.startswith('/'):
                send_msg(chat_id, get_message('start_hint', chat_id), 
                        keyboard=get_main_keyboard(chat_id))
                continue

if __name__ == '__main__':
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    main()
