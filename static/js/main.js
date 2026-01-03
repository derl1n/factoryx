document.addEventListener("DOMContentLoaded", () => {
    /* ==== Элементы ==== */
    const pages = document.querySelectorAll(".page, .page2");
    const page = document.querySelector(".page");
    const navMenu = document.querySelector(".nav-links");
    const resultsDiv = document.getElementById("results");
    const loadingDiv = document.getElementById("loading");
    const navLinks = document.querySelectorAll(".nav-link");
    const factCheckForm = document.getElementById("fact-check-form");
    const textInput = document.getElementById("text-input");
    const linkInput = document.getElementById("link-input");
    const modeRadios = document.querySelectorAll("input[name='mode']");
    const themeToggle = document.getElementById("theme-toggle");
    const langBtn = document.getElementById("lang-btn");
    const langDropdown = document.querySelector(".lang-dropdown");
    const burger = document.getElementById("burger");
    
    let currentLang = localStorage.getItem("lang") || "uk";
    let currentTheme = localStorage.getItem("theme") || "light";
    let requestMade = false;

    /* ==== Переводы ==== */
    const translations = {
        uk: {
            "nav.factCheck": "Перевірка фактів",
            "nav.sources": "Корисні джерела",
            "home.title": "Перевірка фактів",
            "home.subtitle": "За допомогою наукового інструменту перевірки правдивості",
            "home.modeText": "Тільки текст",
            "home.modeLink": "Тільки посилання",
            "home.modeBoth": "Текст + посилання",
            "home.textPlaceholder": "Введіть текст для перевірки...",
            "home.linkPlaceholder": "https://example.com",
            "home.checkButton": "Перевірити",
            "home.checking": "Йде перевірка...",
            "results.title": "Результати перевірки",
            "results.factcheck": "Google FactCheck",
            "results.search": "Google Search",
            "results.gemini": "Perplexity AI",
            "results.domain": "Перевірка домену",
            "results.score": "Оцінка достовірності",
            "results.sources": "Джерела перевірки",
            "notfound": "Нічого не знайдено",
            "safe": "✅ Безпечно",
            "unsafe": "❌ Небезпечно",
            "notblacklist": "✅ Не в чорному списку",
            "blacklist": "❌ У чорному списку",
            "errorText": "❌ Введіть текст",
            "errorLink": "❌ Введіть посилання",
            "errorBoth": "❌ Заповніть всі поля",
            "errorTextShort": "❌ Введіть текст (мінімум 10 символів та 2 слова)",
            "errorQuestion": "❌ Введіть твердження, а не питання",
            "errorSubjective": "❌ Це субʼєктивне твердження — його неможливо перевірити",
            "sources.title": "Корисні джерела",
            "sources.subtitle": "Перевірені ресурси для додаткової інформації",
            "sources.reuters": "Reuters",
            "sources.reutersDesc": "Міжнародна інформаційна організація",
            "sources.bbc": "BBC Reality Check",
            "sources.bbcDesc": "Служба перевірки фактів BBC",
            "sources.snopes": "Snopes",
            "sources.snopesDesc": "Сайт перевірки міських легенд та чуток",
            "sources.politifact": "PolitiFact",
            "sources.politifactDesc": "Сайт перевірки фактів, лауреат премії Пулітцера",
            "sources.cdc": "CDC",
            "sources.cdcDesc": "Центри контролю та профілактики захворювань",
            "sources.who": "WHO",
            "sources.whoDesc": "Всесвітня організація охорони здоров'я",
            "sources.stopfake": "StopFake",
            "sources.stopfakeDesc": "Українська організація перевірки фактів",
            "sources.vox": "VoxUkraine",
            "sources.voxDesc": "Українська аналітична платформа",
            "sources.visit": "Відвідати",
            "tips.title": "💡 Поради для перевірки фактів",
            "tips.checkMultipleSources": "Перевіряйте кілька джерел",
            "tips.checkMultipleSourcesDesc": "Завжди перевіряйте інформацію з кількох надійних джерел.",
            "tips.primarySources": "Шукайте первинні джерела",
            "tips.primarySourcesDesc": "Знаходьте оригінальне джерело інформації, коли це можливо.",
            "tips.checkDate": "Перевіряйте дату публікації",
            "tips.checkDateDesc": "Переконайтеся, що інформація актуальна та доречна.",
            "tips.beSkeptical": "Будьте скептичними",
            "tips.beSkepticalDesc": "Ставте під сумнів надзвичайні твердження та перевіряйте докази."
        },
        en: {
            "nav.factCheck": "Fact Check",
            "nav.sources": "Sources",
            "home.title": "Fact Check",
            "home.subtitle": "Fast scientific truth-checking tool",
            "home.modeText": "Text only",
            "home.modeLink": "Link only",
            "home.modeBoth": "Text + Link",
            "home.textPlaceholder": "Enter text to check...",
            "home.linkPlaceholder": "https://example.com",
            "home.checkButton": "Check",
            "home.checking": "Checking...",
            "results.title": "Results",
            "results.factcheck": "Google FactCheck",
            "results.search": "Google Search",
            "results.gemini": "Perplexity AI",
            "results.domain": "Domain check",
            "results.score": "Credibility Score",
            "results.sources": "Verification Sources",
            "notfound": "Nothing found",
            "safe": "✅ Safe",
            "unsafe": "❌ Unsafe",
            "notblacklist": "✅ Not in blacklist",
            "blacklist": "❌ In blacklist",
            "errorText": "❌ Enter text",
            "errorLink": "❌ Enter a link",
            "errorBoth": "❌ Fill in all the fields",
            "errorTextShort": "❌ Enter text (minimum 10 characters and 2 words)",
            "errorQuestion": "❌ Enter a statement, not a question",
            "errorSubjective": "❌ This is a subjective statement and cannot be verified",
            "sources.title": "Sources",
            "sources.subtitle": "Verified resources for additional information",
            "sources.reuters": "Reuters",
            "sources.reutersDesc": "International news organization",
            "sources.bbc": "BBC Reality Check",
            "sources.bbcDesc": "BBC fact-checking service",
            "sources.snopes": "Snopes",
            "sources.snopesDesc": "Urban legends and rumor checking site",
            "sources.politifact": "PolitiFact",
            "sources.politifactDesc": "Fact-checking site, Pulitzer Prize winner",
            "sources.cdc": "CDC",
            "sources.cdcDesc": "Centers for Disease Control and Prevention",
            "sources.who": "WHO",
            "sources.whoDesc": "World Health Organization",
            "sources.stopfake": "StopFake",
            "sources.stopfakeDesc": "Ukrainian fact-checking organization",
            "sources.vox": "VoxUkraine",
            "sources.voxDesc": "Ukrainian analytical platform",
            "sources.visit": "Visit",
            "tips.title": "💡 Fact-checking Tips",
            "tips.checkMultipleSources": "Check multiple sources",
            "tips.checkMultipleSourcesDesc": "Always verify information from multiple reliable sources.",
            "tips.primarySources": "Look for primary sources",
            "tips.primarySourcesDesc": "Find the original source when possible.",
            "tips.checkDate": "Check the publication date",
            "tips.checkDateDesc": "Make sure the information is current and relevant.",
            "tips.beSkeptical": "Be skeptical",
            "tips.beSkepticalDesc": "Question extraordinary claims and check evidence."
        }
    };

    /* ==== Утилиты ==== */
    function cleanMarkdown(text) {
        if (!text) return "";
        return text.replace(/\*\*(.*?)\*\*/g, "$1").replace(/__(.*?)__/g, "$1");
    }

    function shortenText(text, long = false) {
        const s = text.split(/[.!?]+/).map(x => x.trim()).filter(x => x);
        if (!long) return s.slice(0, 5).join(". ") + ".";
        return s.slice(0, 10).join(". ") + ".";
    }

    function scoreColor(score) {
        if (score >= 70) return "#22c55e";
        if (score >= 50) return "#f59e0b";
        return "#ef4444";
    }

    function shortenUrl(url, maxLength = 50) {
        if (url.length <= maxLength) return url;
        return url.substring(0, maxLength) + "...";
    }

    function getScoreLabel(score, lang) {
        const labels = {
            uk: { high: "Вірогідно правда", medium: "Невизначено", low: "Вірогідно неправда" },
            en: { high: "Likely True", medium: "Uncertain", low: "Likely False" }
        };
        if (score >= 70) return labels[lang].high;
        if (score >= 50) return labels[lang].medium;
        return labels[lang].low;
    }

    /* ==== Адаптивный зсув ==== */
    function updateTranslate() {
        const width = window.innerWidth;
        let translateValue = 0;
        const mode = document.querySelector('input[name="mode"]:checked')?.value || "text";
        
        if (!requestMade) {
            if (width <= 480) {
                if (mode === "text") translateValue = 14;
                if (mode === "link") translateValue = 22;
                if (mode === "both") translateValue = 8;
            } else if (width <= 768) {
                if (mode === "text") translateValue = 10;
                if (mode === "link") translateValue = 18;
                if (mode === "both") translateValue = 4;
            } else if (width <= 1100) {
                if (mode === "text") translateValue = 4;
                if (mode === "link") translateValue = 10;
                if (mode === "both") translateValue = -1;
            } else {
                if (mode === "text") translateValue = 4;
                if (mode === "link") translateValue = 10;
                if (mode === "both") translateValue = -1;
            }
        } else {
            translateValue = 0;
        }
        
        page.style.transform = `translateY(${translateValue}%)`;
    }

    /* ==== Бургер ==== */
    if (burger && navMenu) {
        burger.addEventListener("click", () => {
            navMenu.classList.toggle("show");
            burger.classList.toggle("active");
        });
        
        document.querySelectorAll(".nav-link").forEach(link => {
            link.addEventListener("click", () => {
                navMenu.classList.remove("show");
                burger.classList.remove("active");
            });
        });
    }

    const navLink1 = document.querySelector(".nav-link1");
    const navLink2 = document.querySelector(".nav-link2");
    
    function updateMargin() {
        if (!navLink1 || !navLink2) return;
        navLink1.style.marginRight = navLink2.classList.contains("active") ? "1.65rem" : "2.6rem";
    }
    
    updateMargin();

    /* ==== Переход между страницами ==== */
    [navLink1, navLink2].forEach(link => {
        if (!link) return;
        link.addEventListener("click", (e) => {
            e.preventDefault();
            navLink1.classList.remove("active");
            navLink2.classList.remove("active");
            link.classList.add("active");
            updateMargin();
            
            const targetPage = link.dataset.page;
            pages.forEach(p => p.classList.add("hidden"));
            
            if (targetPage === "home") document.getElementById("home-page").classList.remove("hidden");
            if (targetPage === "sources") document.getElementById("sources-page").classList.remove("hidden");
            
            resultsDiv.innerHTML = "";
            textInput.value = "";
            linkInput.value = "";
            requestMade = false;
            updateTranslate();
        });
    });

    /* ==== Тема ==== */
    function applyTheme(theme) {
        document.body.classList.toggle("dark", theme === "dark");
        themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
        localStorage.setItem("theme", theme);
    }
    
    applyTheme(currentTheme);
    
    themeToggle.addEventListener("click", () => {
        currentTheme = currentTheme === "light" ? "dark" : "light";
        applyTheme(currentTheme);
    });

    /* ==== Переклад ==== */
    langBtn.addEventListener("click", () => {
        langDropdown.classList.toggle("hidden");
    });

    document.querySelectorAll(".lang-option").forEach(opt => {
        opt.addEventListener("click", async () => {
            await translatePage(opt.dataset.lang);
            langDropdown.classList.add("hidden");
        });
    });

    async function translatePage(lang) {
        currentLang = lang;
        localStorage.setItem("lang", lang);
        
        document.querySelectorAll("[data-translate]").forEach(el => {
            const key = el.getAttribute("data-translate");
            if (translations[lang][key]) el.textContent = translations[lang][key];
        });
        
        document.querySelectorAll("[data-translate-placeholder]").forEach(el => {
            const key = el.getAttribute("data-translate-placeholder");
            if (translations[lang][key]) el.placeholder = translations[lang][key];
        });

        // Перекладаємо заголовки в результатах
        const verdictTitle = resultsDiv.querySelector(".verdict-title");
        if (verdictTitle) {
            verdictTitle.textContent = `📊 ${translations[lang]["results.score"]}`;
        }
        
        const sourcesTitles = resultsDiv.querySelectorAll(".sources-title");
        sourcesTitles.forEach(title => {
            if (title.textContent.includes("🔗")) {
                title.textContent = `🔗 ${translations[lang]["results.sources"]}`;
            }
            if (title.textContent.includes("📰")) {
                title.textContent = `📰 ${translations[lang]["results.factcheck"]}`;
            }
            if (title.textContent.includes("🔍")) {
                title.textContent = `🔍 ${translations[lang]["results.search"]}`;
            }
        });

        const dynamicEls = resultsDiv.querySelectorAll("[data-translate-dynamic]");
        if (dynamicEls.length) {
            dynamicEls.forEach(async el => {
                const text = el.getAttribute("data-original") || el.textContent;
                el.setAttribute("data-original", text);
                try {
                    const res = await fetch("/translate", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ text, target: lang })
                    });
                    const jd = await res.json();
                    if (jd.translated) el.textContent = jd.translated;
                } catch (e) {
                    console.error("Translate error:", e);
                }
            });
        }

        const errorEl = resultsDiv.querySelector(".error-message");
        if (errorEl) {
            const key = Object.keys(translations.uk).find(k => 
                translations.uk[k] === errorEl.textContent || translations.en[k] === errorEl.textContent
            );
            if (key && translations[lang][key]) {
                errorEl.textContent = translations[lang][key];
            }
        }
    }

    /* ==== Переключение режимов ==== */
    modeRadios.forEach(radio => {
        radio.addEventListener("change", () => {
            const mode = document.querySelector('input[name="mode"]:checked').value;
            
            document.getElementById("text-field").classList.add("hidden");
            document.getElementById("link-field").classList.add("hidden");
            
            if (mode === "text") document.getElementById("text-field").classList.remove("hidden");
            if (mode === "link") document.getElementById("link-field").classList.remove("hidden");
            if (mode === "both") {
                document.getElementById("text-field").classList.remove("hidden");
                document.getElementById("link-field").classList.remove("hidden");
            }
            
            resultsDiv.innerHTML = "";
            textInput.value = "";
            linkInput.value = "";
            requestMade = false;
            updateTranslate();
        });
    });

    /* ==== Отправка формы ==== */
    factCheckForm.addEventListener("submit", async e => {
        e.preventDefault();
        
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const text = textInput.value.trim();
        const link = linkInput.value.trim();
        const t = translations[currentLang];
        
        if (mode === "text") {
            if (!text) return showError(t.errorText);
            const words = text.split(/\s+/);
            if (text.length < 10 || words.length < 2) return showError(t.errorTextShort);
        }
        
        if (mode === "link") {
            if (!link) return showError(t.errorLink);
        }
        
        if (mode === "both") {
            if (!text && !link) return showError(t.errorBoth);
            if (!text) return showError(t.errorText);
            if (!link) return showError(t.errorLink);
            const words = text.split(/\s+/);
            if (text.length < 10 || words.length < 2) return showError(t.errorTextShort);
        }
        
        if (text) {
            const clean = text.trim().toLowerCase();
            if (clean.endsWith("?")) return showError(t.errorQuestion);
            
            const questionWords = ["хто","що","коли","де","чому","як","скільки","чи","who","what","where","when","why","how","which","кто","что","где","когда","почему","как"];
            const firstWord = text.split(/\s+/)[0]?.toLowerCase().replace(/[^\w]/g,'');
            if (firstWord && questionWords.includes(firstWord)) return showError(t.errorQuestion);
            if (/\b(чи|ли)\s+\w+/.test(clean)) return showError(t.errorQuestion);
        }
        
        loadingDiv.classList.remove("hidden");
        resultsDiv.classList.add("hidden");
        requestMade = true;
        updateTranslate();
        
        try {
            const res = await fetch("/check", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, link, lang: currentLang })
            });
            
            const data = await res.json();
            loadingDiv.classList.add("hidden");
            resultsDiv.classList.remove("hidden");
            
            if (!res.ok) return showError(data.error || "Error");
            
            renderResults(data);
            
        } catch (err) {
            showError("Network error");
            loadingDiv.classList.add("hidden");
        }
    });

    function showError(message) {
        resultsDiv.innerHTML = `<div class="error-message">${message}</div>`;
        resultsDiv.classList.remove("hidden");
        loadingDiv.classList.add("hidden");
    }

    /* ==== Рендер результатов ==== */
    function renderResults(data) {
        const t = translations[currentLang];
        
        let html = `
            <div class="verdict-card">
                <div class="verdict-header" style="align-items: center;">
                    <div class="verdict-title">📊 ${t["results.score"]}</div>
                    <div class="verdict-score" style="color: ${scoreColor(data.score)}">
                        ${data.score}/100
                    </div>
                </div>
            </div>
        `;

        const gem = data.gemini;
        if (gem && gem.explanation) {
            html += `
                <div class="analysis-card">
                    <h3 class="analysis-title">🤖 ${t["results.gemini"]}</h3>
                    <p class="analysis-content" data-translate-dynamic>${cleanMarkdown(gem.explanation)}</p>
                </div>
            `;
        }

        if (gem && gem.sources && gem.sources.length > 0) {
            html += `<div class="sources-card" style="margin-bottom: 2rem;">
                <h3 class="sources-title">🔗 ${t["results.sources"]}</h3>`;
            gem.sources.forEach(src => {
                try {
                    const hostname = new URL(src).hostname;
                    html += `
                        <a href="${src}" target="_blank" class="source-item">
                            <span class="source-icon">🔗</span>
                            <div class="source-content">
                                <div class="source-title">${hostname}</div>
                                <div class="source-url">${shortenUrl(src)}</div>
                            </div>
                        </a>`;
                } catch {
                    html += `
                        <a href="${src}" target="_blank" class="source-item">
                            <span class="source-icon">🔗</span>
                            <div class="source-content">
                                <div class="source-title">Джерело</div>
                                <div class="source-url">${shortenUrl(src)}</div>
                            </div>
                        </a>`;
                }
            });
            html += `</div>`;
        }

        const gfc = data.google_factcheck || [];
        if (gfc.length) {
            html += `<div class="sources-card" style="margin-bottom: 2rem;">
                <h3 class="sources-title">📰 ${t["results.factcheck"]}</h3>`;
            gfc.slice(0, 3).forEach(c => {
                const claim = c.text || "";
                const rating = c.claimReview?.[0]?.textualRating || t.notfound;
                html += `
                    <div class="source-item">
                        <span class="source-icon">📰</span>
                        <div class="source-content">
                            <div class="source-title">${claim}</div>
                            <div class="source-url">${rating}</div>
                        </div>
                    </div>`;
            });
            html += `</div>`;
        }

        const gs = data.google_search || [];
        if (gs.length) {
            html += `<div class="sources-card" style="margin-bottom: 2rem;">
                <h3 class="sources-title">🔍 ${t["results.search"]}</h3>`;
            gs.slice(0, 3).forEach(s => {
                html += `
                    <a href="${s.link}" target="_blank" class="source-item">
                        <span class="source-icon">🔗</span>
                        <div class="source-content">
                            <div class="source-title">${s.title}</div>
                            <div class="source-url">${shortenUrl(s.link)}</div>
                        </div>
                    </a>`;
            });
            html += `</div>`;
        }

        const dc = data.domain_check || {};
        if (Object.keys(dc).length) {
            const sb = dc.safe_browsing || {};
            const spam = dc.spamhaus || {};
            html += `
                <div class="analysis-card" style="margin-bottom: 2rem;">
                    <h3 class="analysis-title">🌐 ${t["results.domain"]}</h3>
                    <p class="analysis-content">
                        ${sb.safe ? t.safe : t.unsafe}<br>
                        ${spam.listed ? t.blacklist : t.notblacklist}
                    </p>
                </div>`;
        }

        resultsDiv.innerHTML = html;
    }

    window.addEventListener("resize", updateTranslate);
    updateTranslate();
    translatePage(currentLang);
});
