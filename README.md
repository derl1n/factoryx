# 🔍 Factoryx - AI-Powered Fact-Checking System

An advanced fact-checking tool that combines AI (Perplexity AI & Google Gemini) with multiple verification APIs to analyze the credibility of text statements and web articles.

## ✨ Features

### 🤖 AI-Powered Analysis
- **Perplexity AI Integration** - Primary fact-checking engine with real-time web search
- **Google Gemini Fallback** - Backup AI analysis for reliability
- **Multi-language Support** - Ukrainian, English
- **Credibility Scoring** - 0-100 scale with detailed explanations

### 🛡️ Security & Safety Checks
- **Content Filtering** - Blocks Russian/Belarusian propaganda sources
- **Malware Detection** - Google Safe Browsing API integration
- **Spam Protection** - Spamhaus DNS blocklist checking
- **Adult Content Filter** - Sightengine API for NSFW detection
- **Casino/Gambling Detection** - Prevents scam site analysis

### 🔎 Multiple Verification Sources
- Google Fact Check Tools API
- Google Custom Search API
- Domain reputation analysis
- Article date verification
- Source credibility assessment

### 💬 Telegram Bot
- Interactive keyboard interface
- Text and link verification
- Group chat support
- Real-time fact-checking
- Multilingual responses

### 🌐 Web Interface
- Modern, responsive design
- Dark/Light theme toggle
- Three verification modes:
  - Text only
  - Link only
  - Text + Link combined
- Comprehensive results display

## 📦 Installation
### Prerequisites
- Python 3.10+
- PostgreSQL database
- API keys (see Configuration section)

### Clone Repository
- bash
- git clone https://github.com/derl1n/factoryx.git
- cd factoryx

### Install Dependencies
The requirements.txt file includes all necessary Python packages:
- bash
- pip install -r requirements.txt

### Environment Setup
Create a .env file in the project root:

- DATABASE_URL=postgresql://user:password@host:port/database
- PERPLEXITY_API_KEY=your_perplexity_key
- GEMINI_API_KEY=your_gemini_key
- GOOGLE_FACTCHECK_KEY=your_factcheck_key
- GOOGLE_SAFE_BROWSING_KEY=your_safebrowsing_key
- GOOGLE_SEARCH_KEY=your_search_key
- GOOGLE_SEARCH_CX=your_custom_search_engine_id
- SIGHTENGINE_USER=your_sightengine_user
- SIGHTENGINE_SECRET=your_sightengine_secret
- TELEGRAM_BOT_TOKEN=your_bot_token

### Database Initialization
The database will auto-initialize on first run. Ensure PostgreSQL is running and the DATABASE_URL is correct.

## 🚀 Usage
### Running the Web Application
- bash
- python app.py
- The server will start on http://localhost:5000

### Running the Telegram Bot
- bash
- python bot.py
- Deployment


### 🔧 API Configuration

- Perplexity AI - Get API Key ⭢ https://www.perplexity.ai/account/api/=
- Google Gemini - Get API Key ⭢ https://aistudio.google.com/app/api-keys
- Google Fact Check - Get API Key ⭢ https://console.cloud.google.com/
- Google Safe Browsing - Get API Key ⭢ https://console.cloud.google.com/
- Google Search - Get API Key ⭢ https://console.cloud.google.com/
- Sightengine - Get API Key ⭢ https://sightengine.com/


### 📱 Telegram Bot Commands
Command	Description
- /start	Initialize bot and show welcome message
- /check	Start fact-checking process
- /cancel	Cancel current verification
- /help	Show detailed instructions
- /stats	View verification statistics

### 🎯 Verification Modes
1. Text Only
Verifies factual accuracy of statements, claims, and assertions.

2. Link Only
Extracts content from URLs and verifies article credibility.

3. Text + Link
Combines text claim with source URL for comprehensive analysis.

### 📊 Credibility Scoring
Score Range	Verdict	Meaning
- 80-100	✅ Likely True	High confidence in accuracy
- 50-79	⚠️ Needs Verification	Mixed or uncertain evidence
- 0-49	❌ Likely False	Strong indicators of misinformation

### 🏗️ Project Structure

```
factoryx/
├── app.py # Flask web application
├── bot.py # Telegram bot handler
├── requirements.txt # Python dependencies
├── init_db.sql # Database schema
├── .env # Environment variables (not in repo)
├── sitemap.xml # SEO sitemap
├── robots.txt # Crawler rules
├── templates/
│ └── index.html # Web interface
├── static/
│ ├── css/
│ │ └── style.css # Styling & themes
│ ├── js/
│ │ └── main.js # Frontend logic
│ └── img/
│ │ └── icon.png # Favicon
│ │ └── logo.png # Main logo
│ │ └── logo-nav.png # Navigation logo
└── README.md # This file
```

## 🔒 Security Features
### Blocked Content:  
- Russian (.ru, .рф, .su) and Belarusian (.by) propaganda sources
- Casino and gambling websites
- Adult/NSFW content
- Known malware/phishing domains
- Spam-listed domains (Spamhaus)
- Content Validation
- Question detection (requires statements, not questions)
- Subjective claim filtering
- Gibberish/spam text detection
- Minimum text length requirements (10 characters, 2 words)

## 🌍 Supported Languages
- Ukrainian (uk) - Primary language
- English (en) - Full support
- Auto-detection with fallback translation

## 👤 Author d2rl1n
- GitHub: [@derl1n](https://github.com/derl1n)
- Telegram: [@d2rl1n](https://t.me/d2rl1n)
- Telegram bot: [@factoryx_factcheck_bot](https://t.me/factoryx_factcheck_bot)
- Website: [factoryx.com.ua](https://factoryx.com.ua/)

## 🙏 Acknowledgments
- Perplexity AI for powerful fact-checking capabilities
- Google for Gemini AI, Safe Browsing, and Fact Check APIs
- Sightengine for content moderation
- BeautifulSoup for web scraping
- Flask community for excellent web framework

## 📞 Support
For issues, questions, or suggestions:

- Telegram: [@d2rl1n](https://t.me/d2rl1n)
- Email: lovov513@gmail.com

⚠️ Disclaimer: This tool provides AI-assisted fact-checking but should not be the sole source of truth. Always verify important information through multiple trusted sources.
