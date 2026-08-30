const articleId = document.body.dataset.articleId || '';
const recordingDownloadName = document.body.dataset.recordingDownloadName || 'article.mp4';
const defaultLocalTtsSpeaker = 9;
const silentAudioDataUrl = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQQAAAAAgICA';
const articleNavigationUrl = './data/article-navigation.json';
const voiceSettingsUrl = '/api/voice-settings';
const defaultVoiceSettings = Object.freeze({
    source: 'docker',
    browserVoice: 'Google 日本語',
    browserRate: 0.9,
    browserPitch: 1,
    dockerSpeaker: defaultLocalTtsSpeaker,
    voicevoxProsody: Object.freeze({
        speedScale: 1,
        pitchScale: 0,
        intonationScale: 1
    })
});
let articleNavigation = [];
let voiceSettings = cloneDefaultVoiceSettings();
let voiceSettingsSaveRun = 0;

function currentArticleFile() {
    return decodeURIComponent(window.location.pathname.split('/').pop() || '');
}

function normalizeArticleHref(href) {
    return href.replace(/^\.\//, '');
}

function articleNavigationHrefs(article) {
    return [
        article.href,
        ...(Array.isArray(article.variantHrefs) ? article.variantHrefs : [])
    ].map(normalizeArticleHref);
}

function getCurrentArticleIndex() {
    const currentFile = currentArticleFile();
    return articleNavigation.findIndex((article) => articleNavigationHrefs(article).includes(currentFile));
}

function isValidArticleNavigationItem(item) {
    return item
        && typeof item.month === 'string'
        && typeof item.href === 'string'
        && typeof item.label === 'string'
        && (
            item.variantHrefs === undefined
            || (Array.isArray(item.variantHrefs) && item.variantHrefs.every((href) => typeof href === 'string'))
        );
}

async function loadArticleNavigation() {
    const response = await fetch(articleNavigationUrl, { cache: 'no-cache' });
    if (!response.ok) {
        throw new Error(`Article navigation failed to load with HTTP ${response.status}.`);
    }

    const payload = await response.json();
    if (!Array.isArray(payload) || !payload.every(isValidArticleNavigationItem)) {
        throw new Error('Article navigation manifest is invalid.');
    }

    articleNavigation = payload;
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[character]));
}

function cloneDefaultVoiceSettings() {
    return {
        source: defaultVoiceSettings.source,
        browserVoice: defaultVoiceSettings.browserVoice,
        browserRate: defaultVoiceSettings.browserRate,
        browserPitch: defaultVoiceSettings.browserPitch,
        dockerSpeaker: defaultVoiceSettings.dockerSpeaker,
        voicevoxProsody: {
            speedScale: defaultVoiceSettings.voicevoxProsody.speedScale,
            pitchScale: defaultVoiceSettings.voicevoxProsody.pitchScale,
            intonationScale: defaultVoiceSettings.voicevoxProsody.intonationScale
        }
    };
}

function clampNumber(value, fallback, minimum, maximum, precision = 2) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return fallback;
    }

    const clamped = Math.min(maximum, Math.max(minimum, numeric));
    return Number(clamped.toFixed(precision));
}

function normalizeVoiceSettings(payload = {}) {
    const defaults = cloneDefaultVoiceSettings();
    const source = payload?.source === 'browser' ? 'browser' : 'docker';
    const browserVoice = String(payload?.browserVoice || defaults.browserVoice).trim() || defaults.browserVoice;
    const dockerSpeaker = Number.parseInt(payload?.dockerSpeaker, 10);
    const incomingProsody = payload?.voicevoxProsody || {};
    return {
        source,
        browserVoice,
        browserRate: clampNumber(payload?.browserRate, defaults.browserRate, 0.7, 1.2),
        browserPitch: clampNumber(payload?.browserPitch, defaults.browserPitch, 0.8, 1.3),
        dockerSpeaker: Number.isInteger(dockerSpeaker) && dockerSpeaker >= 0 ? dockerSpeaker : defaults.dockerSpeaker,
        voicevoxProsody: {
            speedScale: clampNumber(incomingProsody?.speedScale, defaults.voicevoxProsody.speedScale, 0.8, 1.2),
            pitchScale: clampNumber(incomingProsody?.pitchScale, defaults.voicevoxProsody.pitchScale, -0.12, 0.12),
            intonationScale: clampNumber(incomingProsody?.intonationScale, defaults.voicevoxProsody.intonationScale, 0.7, 1.6)
        }
    };
}

function sliderValueText(value) {
    const rounded = Number(value);
    return Number.isFinite(rounded) ? rounded.toFixed(2).replace(/\.00$/, '') : '';
}

function updateRangeValue(inputId) {
    const input = document.getElementById(inputId);
    const output = document.querySelector(`[data-range-value-for="${inputId}"]`);
    if (!input || !output) {
        return;
    }

    output.textContent = sliderValueText(input.value);
}

function setRangeValue(inputId, value) {
    const input = document.getElementById(inputId);
    if (!input) {
        return;
    }

    input.value = String(value);
    updateRangeValue(inputId);
}

function applyVoiceSettingsToControls(settings = voiceSettings) {
    const normalized = normalizeVoiceSettings(settings);
    const sourceSelect = document.getElementById('voice-source');
    if (sourceSelect) {
        sourceSelect.value = normalized.source;
    }

    const browserVoiceSelect = document.getElementById('browser-voice');
    if (browserVoiceSelect && [...browserVoiceSelect.options].some((option) => option.value === normalized.browserVoice)) {
        browserVoiceSelect.value = normalized.browserVoice;
    }

    const dockerVoiceSelect = document.getElementById('docker-voice');
    if (dockerVoiceSelect) {
        dockerVoiceSelect.value = String(normalized.dockerSpeaker);
    }

    setRangeValue('browser-rate', normalized.browserRate);
    setRangeValue('browser-pitch', normalized.browserPitch);
    setRangeValue('docker-speed-scale', normalized.voicevoxProsody.speedScale);
    setRangeValue('docker-pitch-scale', normalized.voicevoxProsody.pitchScale);
    setRangeValue('docker-intonation-scale', normalized.voicevoxProsody.intonationScale);
    updateVoiceControlVisibility();
}

async function loadVoiceSettings() {
    const response = await fetch(voiceSettingsUrl, { cache: 'no-store' });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || `Voice settings failed to load with HTTP ${response.status}.`);
    }

    voiceSettings = normalizeVoiceSettings(payload.settings || payload);
    return voiceSettings;
}

async function saveVoiceSettings(nextSettings) {
    const runId = voiceSettingsSaveRun + 1;
    voiceSettingsSaveRun = runId;
    voiceSettings = normalizeVoiceSettings(nextSettings);

    const response = await fetch(voiceSettingsUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(voiceSettings)
    });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || `Voice settings failed to save with HTTP ${response.status}.`);
    }

    if (runId === voiceSettingsSaveRun) {
        voiceSettings = normalizeVoiceSettings(payload.settings || payload);
        applyVoiceSettingsToControls(voiceSettings);
    }
}

function currentVoiceSettingsFromControls() {
    return normalizeVoiceSettings({
        source: getSelectedVoiceSource(),
        browserVoice: document.getElementById('browser-voice')?.value || voiceSettings.browserVoice,
        browserRate: document.getElementById('browser-rate')?.value,
        browserPitch: document.getElementById('browser-pitch')?.value,
        dockerSpeaker: document.getElementById('docker-voice')?.value,
        voicevoxProsody: getSelectedVoicevoxProsody()
    });
}

async function persistVoiceSettingsFromControls() {
    await saveVoiceSettings(currentVoiceSettingsFromControls());
}

function reportVoiceSettingsError(error) {
    const status = document.getElementById('copy-status');
    if (status && error?.message) {
        status.textContent = error.message;
    }
}

function setToolbarButtonState(buttonOrId, state = 'default') {
    const button = typeof buttonOrId === 'string' ? document.getElementById(buttonOrId) : buttonOrId;
    if (!button) {
        return;
    }

    const labelKey = state === 'active'
        ? 'activeLabel'
        : state === 'loading'
            ? 'loadingLabel'
            : 'defaultLabel';
    const fallbackLabel = button.getAttribute('aria-label') || '';
    const label = button.dataset[labelKey] || button.dataset.defaultLabel || fallbackLabel;
    button.dataset.tooltip = label;
    button.setAttribute('aria-label', label);
    button.classList.toggle('is-active', state === 'active');
    button.classList.toggle('is-loading', state === 'loading');

    const hiddenLabel = button.querySelector('.icon-label');
    if (hiddenLabel) {
        hiddenLabel.textContent = label;
    }
}

function updateVoiceStatus() {
    const status = document.getElementById('voice-current-status');
    if (!status) {
        return;
    }

    if (getSelectedVoiceSource() === 'docker') {
        const dockerVoice = document.getElementById('docker-voice');
        const speakerName = dockerVoice?.selectedOptions?.[0]?.textContent?.trim() || `VOICEVOX speaker ${getSelectedLocalTtsSpeaker()}`;
        status.textContent = `Docker VOICEVOX · ${speakerName}`;
        return;
    }

    const browserVoice = document.getElementById('browser-voice');
    const voiceName = browserVoice?.selectedOptions?.[0]?.textContent?.trim() || 'Browser voice';
    status.textContent = `Browser Voice · ${voiceName}`;
}

function usesIosAudioGate() {
    const userAgent = navigator.userAgent || '';
    const platform = navigator.platform || '';
    return /iPad|iPhone|iPod/.test(userAgent)
        || (platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function updateLocalTtsAudioGate() {
    const button = document.getElementById('enable-docker-audio');
    if (!button) {
        return;
    }

    button.hidden = getSelectedVoiceSource() !== 'docker' || localTtsAudioUnlocked;
}

function setupVoiceSettingsMenu() {
    const toggle = document.getElementById('voice-menu-toggle');
    const menu = document.getElementById('voice-settings-menu');
    const voiceControls = document.querySelector('.voice-controls');
    if (!toggle || !menu) {
        return;
    }

    const setVoiceMenuOpen = (open) => {
        toggle.setAttribute('aria-expanded', String(open));
        menu.hidden = !open;
        voiceControls?.classList.toggle('is-open', open);
    };

    toggle.addEventListener('click', () => {
        const isOpen = toggle.getAttribute('aria-expanded') === 'true';
        setVoiceMenuOpen(!isOpen);
    });

    document.addEventListener('click', (event) => {
        if (menu.hidden || toggle.contains(event.target) || menu.contains(event.target)) {
            return;
        }

        setVoiceMenuOpen(false);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape' || menu.hidden) {
            return;
        }

        setVoiceMenuOpen(false);
        toggle.focus();
    });
}

function topNavLink(href, label, title, icon) {
    return `<a class="top-nav-link" href="${href}" aria-label="${label}" title="${title}">${icon}<span class="icon-label">${label}</span></a>`;
}

function renderTopNavigation() {
    const topNav = document.querySelector('.top-nav');
    if (!topNav) {
        return;
    }

    const homeIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"></path><path d="M6.5 10.5V20h15v-9.5"></path><path d="M10 20v-5h4v5"></path></svg>';
    const ebookIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 5.5A2.5 2.5 0 0 1 7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2.5 2.5 0 0 0-2.5-2.5z"></path><path d="M7 3v15.5"></path><path d="M10 7h6"></path><path d="M10 11h6"></path></svg>';
    const flashcardsIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h9A2.5 2.5 0 0 1 18 6.5v11A2.5 2.5 0 0 1 15.5 20h-9A2.5 2.5 0 0 1 4 17.5z"></path><path d="M8 8h6"></path><path d="M8 12h8"></path><path d="M8 16h4"></path></svg>';
    const publishIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>';
    const nextIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>';
    const lastIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 18 6-6-6-6"></path><path d="M17 6v12"></path></svg>';
    const links = [
        topNavLink('./index.html', 'Home', 'Home', homeIcon),
        topNavLink('./ebook.html', 'E-book', 'Interactive e-book', ebookIcon),
        topNavLink('./flashcards.html', 'Flashcards', 'Flashcards', flashcardsIcon),
        topNavLink('./publish.html', 'Publish', 'Publish article', publishIcon)
    ];

    if (articleNavigation.length > 0) {
        const currentIndex = getCurrentArticleIndex();
        const nextArticle = currentIndex >= 0
            ? articleNavigation[(currentIndex + 1) % articleNavigation.length]
            : articleNavigation[0];
        const lastArticle = articleNavigation[articleNavigation.length - 1];
        links.push(
            topNavLink(nextArticle.href, 'Next Page', 'Next page', nextIcon),
            topNavLink(lastArticle.href, 'Last Page', 'Last page', lastIcon)
        );
    }

    links.push('<button class="top-nav-link top-nav-button" type="button" data-theme-toggle aria-label="Switch to dark mode" title="Switch to dark mode"></button>');
    topNav.innerHTML = links.join('');
    if (typeof initializeThemeToggle === 'function') {
        initializeThemeToggle();
    }
}

function articleNavigationGroupsHtml(currentFile) {
    const groups = [];
    articleNavigation.forEach((article) => {
        const currentGroup = groups[groups.length - 1];
        if (!currentGroup || currentGroup.month !== article.month) {
            groups.push({ month: article.month, articles: [article] });
            return;
        }

        currentGroup.articles.push(article);
    });

    return groups.map((group) => `
                <div class="article-nav-group">
                    <h3 class="article-nav-heading">${escapeHtml(group.month)}</h3>
                    <ul class="article-nav-list">
${group.articles.map((article) => {
        const isCurrent = articleNavigationHrefs(article).includes(currentFile);
        const className = isCurrent ? 'article-nav-link is-current' : 'article-nav-link';
        const ariaCurrent = isCurrent ? ' aria-current="page"' : '';
        const label = /^\d{1,2}\/\d{1,2}(?:\s|$)/.test(article.label)
            ? article.label
            : `${article.date} ${article.label}`;
        return `                        <li><a class="${className}" href="${article.href}"${ariaCurrent}>${escapeHtml(label)}</a></li>`;
    }).join('\n')}
                    </ul>
                </div>`).join('');
}

function renderArticleNavigation() {
    const sidebar = document.querySelector('.article-sidebar');
    if (!sidebar) {
        return;
    }

    const menuIcon = '<svg class="nav-svg menu-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path></svg>';
    const closeIcon = '<svg class="nav-svg close-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>';
    const groupsHtml = articleNavigation.length > 0
        ? articleNavigationGroupsHtml(currentArticleFile())
        : '<p class="site-subtitle">Article navigation is unavailable.</p>';

    sidebar.innerHTML = `
        <h2 class="site-title">Japanese learning board</h2>
        <p class="site-subtitle">Quick links to every article.</p>
        <a class="article-nav-link article-utility-link" href="./ebook.html">Interactive E-book</a>
        <a class="article-nav-link article-utility-link" href="./flashcards.html">Flashcards</a>
        <a class="article-nav-link article-utility-link" href="./publish.html">Publish Article</a>
        <nav class="desktop-article-nav">${groupsHtml}
        </nav>
        <details class="mobile-article-menu">
            <summary aria-label="Article navigation" title="Article navigation">${menuIcon}${closeIcon}<span class="icon-label">Article Navigation</span></summary>
            <nav class="mobile-nav-content" aria-label="Folded article navigation">${groupsHtml}
            </nav>
        </details>`;
}

async function initializeArticleNavigation() {
    try {
        await loadArticleNavigation();
    } catch (error) {
        console.error(error);
    } finally {
        renderTopNavigation();
        renderArticleNavigation();
    }
}

let speaking = false;
let readingUnits = [];
let currentUnitIndex = -1;
let browserUtterance = null;
let sentenceMeta = [];
let availableBrowserVoices = [];
let recordingInProgress = false;
let coverDownloadInProgress = false;
let videoProgressTimer = 0;
let videoProgressPercent = 0;
let localTtsPlaybackActive = false;
let localTtsPlaybackRun = 0;
let activeTtsAudioUrl = null;
let localTtsAudioUnlocked = false;
let localTtsSpeakersLoaded = false;
let preparedLocalTtsAudioBlobs = null;
let preparedLocalTtsStartIndex = 0;
let preparedLocalTtsConfigKey = '';
let localTtsCacheStats = { hit: 0, miss: 0, unknown: 0 };
let articleAudioCacheStatusRun = 0;

function resetLocalTtsCacheStats() {
    localTtsCacheStats = { hit: 0, miss: 0, unknown: 0 };
}

function normalizeAudioCacheState(value) {
    if (value === 'hit' || value === 'miss') {
        return value;
    }
    return 'unknown';
}

function updateLocalTtsCacheStats(cacheState) {
    const normalized = normalizeAudioCacheState(cacheState);
    localTtsCacheStats[normalized] += 1;
    return normalized;
}

function articleAudioCacheSummary() {
    const parts = [];
    if (localTtsCacheStats.hit) {
        parts.push(`${localTtsCacheStats.hit} cached`);
    }
    if (localTtsCacheStats.miss) {
        parts.push(`${localTtsCacheStats.miss} generated`);
    }
    if (localTtsCacheStats.unknown) {
        parts.push(`${localTtsCacheStats.unknown} unknown`);
    }
    return parts.length ? `Audio cache: ${parts.join(', ')}.` : 'Audio cache: unknown.';
}

function articleAudioCacheAvailabilityText(cached, total) {
    if (!total) {
        return 'Audio cache: no article audio targets.';
    }
    const missing = Math.max(0, total - cached);
    return `Audio cache: ${cached}/${total} cached, ${missing} not cached.`;
}

async function fetchLocalTtsCacheStatus(
    texts,
    speaker = getSelectedLocalTtsSpeaker(),
    voicevoxProsody = getSelectedVoicevoxProsody()
) {
    const response = await fetch('/api/tts/voicevox/cache-status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            texts,
            speaker,
            voicevoxProsody
        })
    });

    if (!response.ok) {
        let errorMessage = `Audio cache status failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            if (payload.error) {
                errorMessage = payload.error;
            }
        } catch (error) {
            // Keep the HTTP status fallback if the response is not JSON.
        }
        throw new Error(errorMessage);
    }

    return response.json();
}

async function refreshArticleAudioCacheStatus() {
    if (!sentenceMeta.length || getSelectedVoiceSource() !== 'docker') {
        return;
    }
    const runId = articleAudioCacheStatusRun + 1;
    articleAudioCacheStatusRun = runId;
    const status = document.getElementById('copy-status');
    try {
        const payload = await fetchLocalTtsCacheStatus(
            sentenceMeta.map((sentence) => sentence.ttsText),
            getSelectedLocalTtsSpeaker(),
            getSelectedVoicevoxProsody()
        );
        if (runId === articleAudioCacheStatusRun && status && !speaking && !localTtsPlaybackActive) {
            status.textContent = articleAudioCacheAvailabilityText(payload.cached || 0, sentenceMeta.length);
        }
    } catch (error) {
        if (runId === articleAudioCacheStatusRun && status && !speaking && !localTtsPlaybackActive) {
            status.textContent = error.message;
        }
    }
}

function extractRubyBaseText(element) {
    const clone = element.cloneNode(true);
    clone.querySelectorAll('.sentence-read-button').forEach((node) => node.remove());
    clone.querySelectorAll('rt, rp').forEach((node) => node.remove());
    return normalizeCopiedText(clone.textContent);
}

function extractRubyTtsText(element) {
    const clone = element.cloneNode(true);
    clone.querySelectorAll('.sentence-read-button').forEach((node) => node.remove());
    clone.querySelectorAll('ruby').forEach((ruby) => {
        const reading = normalizeCopiedText(ruby.querySelector('rt')?.textContent);
        if (reading) {
            ruby.replaceWith(document.createTextNode(reading));
        }
    });
    clone.querySelectorAll('rt, rp').forEach((node) => node.remove());
    return normalizeTtsText(clone.textContent);
}

function normalizeCopiedText(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
}

function normalizeTtsText(text) {
    return normalizeCopiedText(String(text || '').replace(/[()（）［］\[\]{}｛｝]/g, ' '));
}

function buildBilingualArticleText() {
    const title = extractRubyBaseText(document.querySelector('h1'));
    const blocks = title ? [title] : [];

    document.querySelectorAll('.article-paragraph').forEach((paragraph) => {
        const japaneseText = extractRubyBaseText(paragraph);
        const translation = paragraph.nextElementSibling?.classList.contains('sentence-translation')
            ? normalizeCopiedText(paragraph.nextElementSibling.textContent)
            : '';
        const pair = [japaneseText, translation].filter(Boolean).join('\n');

        if (pair) {
            blocks.push(pair);
        }
    });

    return blocks.join('\n\n');
}

function splitIntoSentences(text) {
    const matches = text.match(/[^。！？!?]+[。！？!?]?/g) ?? [];
    return matches.map((sentence) => sentence.trim()).filter(Boolean);
}

function createSegmenter() {
    if (typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function') {
        return new Intl.Segmenter('ja-JP', { granularity: 'word' });
    }

    return null;
}

function tokenizeText(text, segmenter) {
    if (!text) {
        return [];
    }

    if (segmenter) {
        return Array.from(segmenter.segment(text), (segment) => segment.segment);
    }

    return Array.from(text);
}

function createUnitSpan(text) {
    const span = document.createElement('span');
    span.className = 'reading-unit';
    span.textContent = text;
    span.dataset.readingText = text;
    return span;
}

function replaceTextNodeWithUnits(textNode, segmenter) {
    const text = textNode.textContent ?? '';
    const tokens = tokenizeText(text, segmenter);
    if (!tokens.length) {
        return;
    }

    const fragment = document.createDocumentFragment();
    tokens.forEach((token) => {
        if (/^\s+$/.test(token)) {
            fragment.appendChild(document.createTextNode(token));
            return;
        }

        fragment.appendChild(createUnitSpan(token));
    });

    textNode.parentNode.replaceChild(fragment, textNode);
}

function wrapRubyNode(rubyNode) {
    const wrapper = document.createElement('span');
    wrapper.className = 'reading-unit';
    wrapper.dataset.readingText = extractRubyBaseText(rubyNode);
    rubyNode.parentNode.replaceChild(wrapper, rubyNode);
    wrapper.appendChild(rubyNode);
}

function decorateReadingContent() {
    const segmenter = createSegmenter();
    const targets = [document.querySelector('h1'), ...document.querySelectorAll('.article-paragraph')];

    targets.forEach((target) => {
        const childNodes = Array.from(target.childNodes);
        childNodes.forEach((node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                replaceTextNodeWithUnits(node, segmenter);
            } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === 'RUBY') {
                wrapRubyNode(node);
            }
        });
    });
}

function isHighlightableToken(text) {
    return /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}A-Za-z0-9]/u.test(text);
}

function buildReadingUnits() {
    const blocks = [document.querySelector('h1'), ...document.querySelectorAll('.article-paragraph')];
    const units = [];

    blocks.forEach((block, blockIndex) => {
        const blockUnits = Array.from(block.querySelectorAll('.reading-unit'));
        blockUnits.forEach((element) => {
            const text = element.dataset.readingText ?? element.textContent ?? '';
            const unitId = String(units.length);
            element.dataset.unitId = unitId;

            units.push({
                id: unitId,
                element,
                text,
                blockIndex,
                isHighlightable: isHighlightableToken(text)
            });
        });
    });

    readingUnits = units;
}

function buildSentenceMeta() {
    const blocks = [document.querySelector('h1'), ...document.querySelectorAll('.article-paragraph')];
    const metadata = [];
    let unitPointer = 0;

    blocks.forEach((block, blockIndex) => {
        const blockText = extractRubyBaseText(block);
        const sentences = splitIntoSentences(blockText);
        const ttsSentences = splitIntoSentences(extractRubyTtsText(block));

        sentences.forEach((sentence, sentenceIndex) => {
            const sentenceId = String(metadata.length);
            let consumed = '';
            const unitIds = [];

            while (unitPointer < readingUnits.length && readingUnits[unitPointer].blockIndex === blockIndex) {
                const unit = readingUnits[unitPointer];
                unit.sentenceId = sentenceId;
                unit.element.dataset.sentenceId = sentenceId;
                unitIds.push(unit.id);
                consumed += unit.text;
                unitPointer += 1;

                if (consumed.replace(/\s+/g, '') === sentence.replace(/\s+/g, '')) {
                    break;
                }
            }

            metadata.push({
                id: sentenceId,
                text: sentence,
                ttsText: ttsSentences[sentenceIndex] || sentence,
                unitIds,
                blockIndex
            });
        });
    });

    sentenceMeta = metadata;
}

function renderSentencePlaybackButtons() {
    document.querySelectorAll('.sentence-read-button').forEach((button) => button.remove());

    sentenceMeta.forEach((sentence, sentenceIndex) => {
        if (sentence.blockIndex === 0 || !sentence.unitIds.length) {
            return;
        }

        const firstUnitIndex = findUnitIndexById(sentence.unitIds[0]);
        const firstUnit = readingUnits[firstUnitIndex];
        if (!firstUnit?.element?.parentNode) {
            return;
        }

        const button = document.createElement('button');
        button.className = 'sentence-read-button';
        button.type = 'button';
        button.dataset.sentenceIndex = String(sentenceIndex);
        button.dataset.tooltip = 'Read from this sentence';
        button.setAttribute('aria-label', 'Read from this sentence');
        button.innerHTML = [
            '<svg class="sentence-read-svg" viewBox="0 0 24 24" aria-hidden="true">',
            '<path d="M8 5v14l11-7z"></path>',
            '</svg>',
            '<span class="icon-label">Read from this sentence</span>'
        ].join('');
        firstUnit.element.parentNode.insertBefore(button, firstUnit.element);
    });
}

function clearHighlight() {
    readingUnits.forEach((unit) => unit.element.classList.remove('is-speaking'));
    currentUnitIndex = -1;
}

function getPreferredBrowserVoices(voices) {
    const preferredNames = ['Google 日本語', 'Sandy', 'Shelley', 'Flo', 'Kyoko', 'Eddy', 'Reed', 'Rocko', 'Grandma', 'Grandpa'];
    return preferredNames
        .map((name) => voices.find((voice) => voice.name === name || voice.name.startsWith(`${name} (`)))
        .filter(Boolean);
}

function populateBrowserVoiceOptions() {
    const select = document.getElementById('browser-voice');
    if (!select) {
        return;
    }

    if (!('speechSynthesis' in window)) {
        select.innerHTML = '';
        const option = document.createElement('option');
        option.value = 'auto';
        option.textContent = 'No Japanese Voice';
        select.appendChild(option);
        updateVoiceStatus();
        return;
    }

    const voices = window.speechSynthesis.getVoices().filter((voice) => voice.lang === 'ja-JP');
    availableBrowserVoices = voices;

    const savedValue = voiceSettings.browserVoice;
    const previousValue = select.value;
    select.innerHTML = '';

    const preferredVoices = getPreferredBrowserVoices(voices);
    const orderedVoices = [
        ...preferredVoices,
        ...voices.filter((voice) => !preferredVoices.includes(voice))
    ];

    if (!orderedVoices.length) {
        const option = document.createElement('option');
        option.value = 'auto';
        option.textContent = 'No Japanese Voice';
        select.appendChild(option);
        updateVoiceStatus();
        return;
    }

    orderedVoices.forEach((voice) => {
        const option = document.createElement('option');
        option.value = voice.name;
        option.textContent = voice.name;
        select.appendChild(option);
    });

    if (savedValue && [...select.options].some((option) => option.value === savedValue)) {
        select.value = savedValue;
    } else if ([...select.options].some((option) => option.value === previousValue)) {
        select.value = previousValue;
    } else if ([...select.options].some((option) => option.value === 'Google 日本語')) {
        select.value = 'Google 日本語';
    } else {
        select.selectedIndex = 0;
    }

    updateVoiceStatus();
}

function getSelectedBrowserVoice() {
    const select = document.getElementById('browser-voice');
    return availableBrowserVoices.find((voice) => voice.name === select.value) || null;
}

function getSelectedVoiceSource() {
    const select = document.getElementById('voice-source');
    return select?.value === 'browser' ? 'browser' : 'docker';
}

function getSelectedLocalTtsSpeaker() {
    const select = document.getElementById('docker-voice');
    const speaker = Number(select?.value);
    return Number.isInteger(speaker) ? speaker : defaultLocalTtsSpeaker;
}

function getSelectedVoicevoxProsody() {
    return {
        speedScale: clampNumber(document.getElementById('docker-speed-scale')?.value, voiceSettings.voicevoxProsody.speedScale, 0.8, 1.2),
        pitchScale: clampNumber(document.getElementById('docker-pitch-scale')?.value, voiceSettings.voicevoxProsody.pitchScale, -0.12, 0.12),
        intonationScale: clampNumber(document.getElementById('docker-intonation-scale')?.value, voiceSettings.voicevoxProsody.intonationScale, 0.7, 1.6)
    };
}

function currentVoicevoxConfigKey() {
    return JSON.stringify({
        speaker: getSelectedLocalTtsSpeaker(),
        prosody: getSelectedVoicevoxProsody()
    });
}

function updateVoiceControlVisibility() {
    const source = getSelectedVoiceSource();
    const voiceControls = document.querySelector('.voice-controls');
    if (voiceControls) {
        voiceControls.classList.toggle('is-open', !(document.getElementById('voice-settings-menu')?.hidden ?? true));
    }

    document.querySelectorAll('.browser-voice-setting').forEach((element) => {
        element.hidden = source !== 'browser';
    });
    document.querySelectorAll('.docker-voice-setting').forEach((element) => {
        element.hidden = source !== 'docker';
    });

    updateVoiceStatus();
    updateLocalTtsAudioGate();
}

function highlightUnit(index) {
    if (index === currentUnitIndex) {
        return;
    }

    clearHighlight();

    if (index < 0 || !readingUnits[index] || !readingUnits[index].isHighlightable) {
        return;
    }

    currentUnitIndex = index;
    const sentenceId = readingUnits[index].sentenceId;
    readingUnits
        .filter((unit) => unit.sentenceId === sentenceId)
        .forEach((unit) => unit.element.classList.add('is-speaking'));
    readingUnits[index].element.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}

function findUnitIndexById(unitId) {
    for (let index = 0; index < readingUnits.length; index += 1) {
        if (readingUnits[index].id === unitId) {
            return index;
        }
    }

    return -1;
}

function createVoiceSettingLabel(id, text, extraClassName = '') {
    const label = document.createElement('label');
    label.className = `toolbar-label ${extraClassName}`.trim();
    label.htmlFor = id;
    label.textContent = text;
    return label;
}

function createVoiceRangeControl({ id, value, min, max, step, extraClassName = '' }) {
    const wrapper = document.createElement('div');
    wrapper.className = `voice-setting-control ${extraClassName}`.trim();

    const input = document.createElement('input');
    input.className = 'voice-slider';
    input.type = 'range';
    input.id = id;
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(value);

    const output = document.createElement('span');
    output.className = 'voice-slider-value';
    output.dataset.rangeValueFor = id;
    output.textContent = sliderValueText(value);

    wrapper.append(input, output);
    return wrapper;
}

function insertVoiceSourceControls() {
    const menu = document.getElementById('voice-settings-menu');
    const browserVoice = document.getElementById('browser-voice');
    const browserVoiceLabel = document.querySelector('label[for="browser-voice"]');
    if (!menu || !browserVoice || !browserVoiceLabel || document.getElementById('voice-source')) {
        return;
    }

    browserVoiceLabel.classList.add('browser-voice-setting');
    browserVoice.classList.add('browser-voice-setting');
    browserVoice.setAttribute('data-setting-kind', 'browser');

    const sourceLabel = createVoiceSettingLabel('voice-source', 'Voice Source');

    const sourceSelect = document.createElement('select');
    sourceSelect.className = 'voice-select';
    sourceSelect.id = 'voice-source';
    sourceSelect.setAttribute('aria-label', 'Voice source');
    sourceSelect.innerHTML = [
        '<option value="docker" selected>Docker VOICEVOX</option>',
        '<option value="browser">Browser Voice</option>'
    ].join('');
    sourceSelect.value = voiceSettings.source;
    sourceSelect.addEventListener('change', async () => {
        updateVoiceControlVisibility();
        if (getSelectedVoiceSource() === 'docker') {
            await populateLocalTtsVoiceOptions();
        }
        try {
            await persistVoiceSettingsFromControls();
        } catch (error) {
            reportVoiceSettingsError(error);
        }
    });

    const dockerVoiceLabel = createVoiceSettingLabel('docker-voice', 'Docker Voice', 'docker-voice-setting');

    const dockerVoice = document.createElement('select');
    dockerVoice.className = 'voice-select docker-voice-setting';
    dockerVoice.id = 'docker-voice';
    dockerVoice.setAttribute('aria-label', 'Docker VOICEVOX voice');
    dockerVoice.innerHTML = `<option value="${defaultLocalTtsSpeaker}" selected>VOICEVOX speaker ${defaultLocalTtsSpeaker}</option>`;
    dockerVoice.value = String(voiceSettings.dockerSpeaker);
    dockerVoice.addEventListener('change', async () => {
        updateVoiceStatus();
        clearPreparedLocalTtsAudio();
        try {
            await persistVoiceSettingsFromControls();
        } catch (error) {
            reportVoiceSettingsError(error);
        }
    });

    const browserRateLabel = createVoiceSettingLabel('browser-rate', 'Speech Pace', 'browser-voice-setting');
    const browserRateControl = createVoiceRangeControl({
        id: 'browser-rate',
        value: voiceSettings.browserRate,
        min: 0.7,
        max: 1.2,
        step: 0.05,
        extraClassName: 'browser-voice-setting'
    });
    const browserPitchLabel = createVoiceSettingLabel('browser-pitch', 'Tone Height', 'browser-voice-setting');
    const browserPitchControl = createVoiceRangeControl({
        id: 'browser-pitch',
        value: voiceSettings.browserPitch,
        min: 0.8,
        max: 1.3,
        step: 0.05,
        extraClassName: 'browser-voice-setting'
    });
    const dockerSpeedLabel = createVoiceSettingLabel('docker-speed-scale', 'Speech Pace', 'docker-voice-setting');
    const dockerSpeedControl = createVoiceRangeControl({
        id: 'docker-speed-scale',
        value: voiceSettings.voicevoxProsody.speedScale,
        min: 0.8,
        max: 1.2,
        step: 0.05,
        extraClassName: 'docker-voice-setting'
    });
    const dockerPitchLabel = createVoiceSettingLabel('docker-pitch-scale', 'Tone Height', 'docker-voice-setting');
    const dockerPitchControl = createVoiceRangeControl({
        id: 'docker-pitch-scale',
        value: voiceSettings.voicevoxProsody.pitchScale,
        min: -0.12,
        max: 0.12,
        step: 0.02,
        extraClassName: 'docker-voice-setting'
    });
    const dockerIntonationLabel = createVoiceSettingLabel('docker-intonation-scale', 'Intonation', 'docker-voice-setting');
    const dockerIntonationControl = createVoiceRangeControl({
        id: 'docker-intonation-scale',
        value: voiceSettings.voicevoxProsody.intonationScale,
        min: 0.7,
        max: 1.6,
        step: 0.05,
        extraClassName: 'docker-voice-setting'
    });

    menu.insertBefore(sourceLabel, browserVoiceLabel);
    menu.insertBefore(sourceSelect, browserVoiceLabel);
    menu.insertBefore(dockerVoiceLabel, browserVoice.nextSibling);
    menu.insertBefore(dockerVoice, dockerVoiceLabel.nextSibling);
    menu.append(
        browserRateLabel,
        browserRateControl,
        browserPitchLabel,
        browserPitchControl,
        dockerSpeedLabel,
        dockerSpeedControl,
        dockerPitchLabel,
        dockerPitchControl,
        dockerIntonationLabel,
        dockerIntonationControl
    );

    menu.querySelectorAll('.voice-slider').forEach((input) => {
        input.addEventListener('input', () => {
            updateRangeValue(input.id);
            clearPreparedLocalTtsAudio();
        });
        input.addEventListener('change', async () => {
            try {
                await persistVoiceSettingsFromControls();
            } catch (error) {
                reportVoiceSettingsError(error);
            }
            refreshArticleAudioCacheStatus();
        });
    });

    updateVoiceControlVisibility();
    applyVoiceSettingsToControls(voiceSettings);
    if (getSelectedVoiceSource() === 'docker') {
        populateLocalTtsVoiceOptions();
    }
}

function revokeActiveTtsAudioUrl() {
    if (!activeTtsAudioUrl) {
        return;
    }

    URL.revokeObjectURL(activeTtsAudioUrl);
    activeTtsAudioUrl = null;
}

function clearPreparedLocalTtsAudio() {
    preparedLocalTtsAudioBlobs = null;
    preparedLocalTtsStartIndex = 0;
    preparedLocalTtsConfigKey = '';
}

async function unlockLocalTtsAudio() {
    const audioPlayer = document.getElementById('tts-player');
    if (!audioPlayer || localTtsAudioUnlocked) {
        return true;
    }

    const previousSrc = audioPlayer.getAttribute('src');
    const previousMuted = audioPlayer.muted;
    let unlocked = false;

    try {
        audioPlayer.muted = true;
        audioPlayer.src = silentAudioDataUrl;
        audioPlayer.load();
        await audioPlayer.play();
        audioPlayer.pause();
        localTtsAudioUnlocked = true;
        unlocked = true;
    } catch (error) {
        // Callers can show a clearer page-level message than the browser's play() error.
    } finally {
        audioPlayer.muted = previousMuted;
        if (previousSrc) {
            audioPlayer.src = previousSrc;
        } else {
            audioPlayer.removeAttribute('src');
        }
        audioPlayer.load();
    }

    updateLocalTtsAudioGate();
    return unlocked;
}

async function enableLocalTtsAudio({ statusMessage = 'Docker audio enabled. Tap Read Aloud again.' } = {}) {
    const status = document.getElementById('copy-status');
    const unlocked = await unlockLocalTtsAudio();
    if (unlocked) {
        if (status) {
            status.textContent = statusMessage;
        }
        return true;
    }

    if (status) {
        status.textContent = 'Safari blocked Docker audio. Tap Enable audio directly in the page.';
    }
    updateLocalTtsAudioGate();
    return false;
}

function getSentenceFirstUnitIndex(sentence) {
    const firstUnitId = sentence.unitIds[0];
    return findUnitIndexById(firstUnitId);
}

async function fetchLocalTtsStatus() {
    const response = await fetch('/api/tts/voicevox/status', { cache: 'no-store' });
    const payload = await response.json();

    if (!response.ok) {
        throw new Error(payload.error || `Docker TTS request failed with HTTP ${response.status}.`);
    }

    return payload;
}

async function populateLocalTtsVoiceOptions() {
    const select = document.getElementById('docker-voice');
    const status = document.getElementById('copy-status');
    if (!select || localTtsSpeakersLoaded) {
        return;
    }

    try {
        const payload = await fetchLocalTtsStatus();
        const preferredValue = String(voiceSettings.dockerSpeaker);
        const previousValue = select.value;
        const options = [];
        payload.speakers.forEach((speaker) => {
            speaker.styles.forEach((style) => {
                options.push({
                    id: style.id,
                    label: `${speaker.name} - ${style.name}`
                });
            });
        });

        select.innerHTML = '';
        options.forEach((optionValue) => {
            const option = document.createElement('option');
            option.value = String(optionValue.id);
            option.textContent = optionValue.label;
            select.appendChild(option);
        });

        if (preferredValue && [...select.options].some((option) => option.value === preferredValue)) {
            select.value = preferredValue;
        } else if ([...select.options].some((option) => option.value === previousValue)) {
            select.value = previousValue;
        } else if ([...select.options].some((option) => option.value === String(payload.default_speaker))) {
            select.value = String(payload.default_speaker);
        }

        localTtsSpeakersLoaded = true;
        updateVoiceStatus();
        refreshArticleAudioCacheStatus();
    } catch (error) {
        select.innerHTML = `<option value="${defaultLocalTtsSpeaker}">Start Docker VOICEVOX</option>`;
        updateVoiceStatus();
        if (status && getSelectedVoiceSource() === 'docker') {
            status.textContent = error.message;
        }
    }
}

async function fetchLocalTtsAudio(text, speaker = getSelectedLocalTtsSpeaker()) {
    const voicevoxProsody = getSelectedVoicevoxProsody();
    const response = await fetch('/api/tts/voicevox', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            text,
            speaker,
            voicevoxProsody
        })
    });

    if (!response.ok) {
        let errorMessage = `Docker TTS request failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            if (payload.error) {
                errorMessage = payload.error;
            }
        } catch (error) {
            // Keep the HTTP status fallback if the response is not JSON.
        }

        throw new Error(errorMessage);
    }

    const cacheState = updateLocalTtsCacheStats(response.headers.get('X-Audio-Cache'));
    const blob = await response.blob();
    return { blob, cacheState };
}

async function buildLocalTtsAudioQueue(status, speaker = getSelectedLocalTtsSpeaker()) {
    const audioBlobs = [];
    resetLocalTtsCacheStats();
    for (let index = 0; index < sentenceMeta.length; index += 1) {
        status.textContent = `Generating Docker TTS sentence ${index + 1}/${sentenceMeta.length}...`;
        const audio = await fetchLocalTtsAudio(sentenceMeta[index].ttsText, speaker);
        status.textContent = `Prepared sentence ${index + 1}/${sentenceMeta.length}. ${articleAudioCacheSummary()}`;
        audioBlobs.push(audio);
    }

    return audioBlobs;
}

function playLocalTtsAudioBlob(audioBlob, sentence, sentenceIndex, runId) {
    const audioPlayer = document.getElementById('tts-player');
    const status = document.getElementById('copy-status');

    return new Promise((resolve, reject) => {
        const cleanup = () => {
            audioPlayer.onended = null;
            audioPlayer.onerror = null;
        };

        audioPlayer.onended = () => {
            cleanup();
            clearHighlight();
            resolve();
        };
        audioPlayer.onerror = () => {
            cleanup();
            clearHighlight();
            reject(new Error('Docker TTS audio playback failed.'));
        };

        revokeActiveTtsAudioUrl();
        const blob = audioBlob?.blob || audioBlob;
        const cacheState = normalizeAudioCacheState(audioBlob?.cacheState);
        activeTtsAudioUrl = URL.createObjectURL(blob);
        audioPlayer.src = activeTtsAudioUrl;
        highlightUnit(getSentenceFirstUnitIndex(sentence));
        const cacheLabel = cacheState === 'hit'
            ? 'cached'
            : cacheState === 'miss'
                ? 'generated'
                : 'cache unknown';
        status.textContent = `Playing Docker TTS sentence ${sentenceIndex + 1}/${sentenceMeta.length} (${cacheLabel}). ${articleAudioCacheSummary()}`;

        audioPlayer.play().catch((error) => {
            cleanup();
            clearHighlight();
            reject(error);
        });
    }).then(() => {
        if (runId !== localTtsPlaybackRun) {
            throw new Error('Docker TTS playback was stopped.');
        }
    });
}

async function playLocalTtsQueue({ audioBlobs = null, speaker = getSelectedLocalTtsSpeaker(), startIndex = 0 } = {}) {
    const status = document.getElementById('copy-status');
    const speakButton = document.getElementById('speak-japanese-article');
    const runId = localTtsPlaybackRun + 1;
    const firstIndex = Math.max(0, Math.min(startIndex, sentenceMeta.length));
    const loadAudioBlob = (index) => {
        if (audioBlobs) {
            return Promise.resolve(audioBlobs[index]);
        }

        status.textContent = `Generating Docker TTS sentence ${index + 1}/${sentenceMeta.length}...`;
        return fetchLocalTtsAudio(sentenceMeta[index].ttsText, speaker);
    };

    stopCurrentPlayback();
    if (!audioBlobs) {
        resetLocalTtsCacheStats();
    }
    localTtsPlaybackRun = runId;
    localTtsPlaybackActive = true;
    if (speakButton) {
        setToolbarButtonState(speakButton, 'active');
    }

    try {
        let pendingAudioBlob = firstIndex < sentenceMeta.length ? loadAudioBlob(firstIndex) : null;
        for (let index = firstIndex; index < sentenceMeta.length; index += 1) {
            if (!localTtsPlaybackActive || runId !== localTtsPlaybackRun) {
                throw new Error('Docker TTS playback was stopped.');
            }

            const sentence = sentenceMeta[index];
            const audioBlob = await pendingAudioBlob;
            status.textContent = `Prepared sentence ${index + 1}/${sentenceMeta.length}. ${articleAudioCacheSummary()}`;
            pendingAudioBlob = index + 1 < sentenceMeta.length
                ? loadAudioBlob(index + 1)
                : null;
            await playLocalTtsAudioBlob(audioBlob, sentence, index, runId);
        }

        status.textContent = `Finished Docker TTS reading. ${articleAudioCacheSummary()}`;
    } finally {
        if (runId === localTtsPlaybackRun) {
            localTtsPlaybackActive = false;
            clearHighlight();
            revokeActiveTtsAudioUrl();
            if (speakButton) {
                setToolbarButtonState(speakButton);
            }
        }
    }
}

async function playLocalTtsArticle(startIndex = 0) {
    const status = document.getElementById('copy-status');

    if (localTtsPlaybackActive) {
        stopCurrentPlayback();
        status.textContent = 'Docker TTS stopped.';
        return;
    }

    try {
        status.textContent = 'Preparing Docker TTS...';
        await populateLocalTtsVoiceOptions();
        await playLocalTtsQueue({ startIndex });
    } catch (error) {
        if (!String(error.message).includes('stopped')) {
            status.textContent = error.message;
        }
    }
}

async function speakWithLocalTts(startIndex = 0) {
    const status = document.getElementById('copy-status');
    if (!localTtsPlaybackActive) {
        if (usesIosAudioGate()) {
            const speaker = getSelectedLocalTtsSpeaker();
            const configKey = currentVoicevoxConfigKey();
            const hasPreparedAudio = preparedLocalTtsAudioBlobs
                && preparedLocalTtsStartIndex === startIndex
                && preparedLocalTtsConfigKey === configKey;

            if (!hasPreparedAudio) {
                try {
                    status.textContent = 'Preparing Docker TTS for Safari. Tap Read Aloud again when ready...';
                    await populateLocalTtsVoiceOptions();
                    preparedLocalTtsConfigKey = currentVoicevoxConfigKey();
                    preparedLocalTtsStartIndex = startIndex;
                    preparedLocalTtsAudioBlobs = await buildLocalTtsAudioQueue(status, speaker);
                    status.textContent = 'Docker TTS is ready. Tap Read Aloud again.';
                } catch (error) {
                    clearPreparedLocalTtsAudio();
                    status.textContent = error.message;
                }
                return;
            }

            const audioBlobs = preparedLocalTtsAudioBlobs;
            clearPreparedLocalTtsAudio();
            await playLocalTtsQueue({ audioBlobs, speaker, startIndex });
            return;
        }

        const audioReady = await unlockLocalTtsAudio();
        if (!audioReady) {
            status.textContent = 'Safari blocked Docker audio. Tap Enable audio directly in the page.';
            return;
        }
    }
    await playLocalTtsArticle(startIndex);
}

async function copyBilingualArticle() {
    const status = document.getElementById('copy-status');
    const articleText = buildBilingualArticleText();

    try {
        await navigator.clipboard.writeText(articleText);
        status.textContent = 'Japanese and English article copied to clipboard.';
    } catch (error) {
        status.textContent = 'Copy failed. Your browser may block clipboard access.';
    }
}

function buildStudyNotesText() {
    const studyNotes = document.querySelector('.study-notes-box');
    if (!studyNotes) {
        return '';
    }

    const title = normalizeCopiedText(studyNotes.querySelector('h2')?.textContent);
    const groups = Array.from(studyNotes.querySelectorAll('.study-note-group'))
        .map((group) => {
            const heading = normalizeCopiedText(group.querySelector('h3')?.textContent);
            const items = Array.from(group.querySelectorAll('.study-note-list li'))
                .map((item) => normalizeCopiedText(item.textContent))
                .filter(Boolean);
            return [heading, ...items].filter(Boolean).join('\n');
        })
        .filter(Boolean);

    return [title, ...groups].filter(Boolean).join('\n');
}

function buildVocabularyAndStudyNotesText() {
    const vocabularyBox = document.querySelector('.vocabulary-box');
    const vocabularyText = vocabularyBox
        ? [
            normalizeCopiedText(vocabularyBox.querySelector('h2')?.textContent),
            ...Array.from(vocabularyBox.querySelectorAll('li'))
                .map((item) => normalizeCopiedText(item.textContent))
                .filter(Boolean),
        ].filter(Boolean).join('\n')
        : '';

    return [buildStudyNotesText(), vocabularyText].filter(Boolean).join('\n\n');
}

async function copyVocabularyList() {
    const status = document.getElementById('copy-status');
    const vocabularyText = buildVocabularyAndStudyNotesText();

    if (!vocabularyText) {
        status.textContent = 'No vocabulary list found on this page.';
        return;
    }

    try {
        await navigator.clipboard.writeText(vocabularyText);
        status.textContent = 'Vocabulary and phrases copied to clipboard.';
    } catch (error) {
        status.textContent = 'Copy failed. Your browser may block clipboard access.';
    }
}

function stopCurrentPlayback() {
    const speakButton = document.getElementById('speak-japanese-article');
    const audioPlayer = document.getElementById('tts-player');

    if (browserUtterance) {
        window.speechSynthesis.cancel();
        browserUtterance = null;
    }
    localTtsPlaybackActive = false;
    localTtsPlaybackRun += 1;
    revokeActiveTtsAudioUrl();
    if (audioPlayer) {
        audioPlayer.pause();
        audioPlayer.removeAttribute('src');
        audioPlayer.load();
    }
    clearHighlight();
    speaking = false;
    if (speakButton) {
        setToolbarButtonState(speakButton);
    }
}

function speakWithBrowserSentenceQueue(onComplete = null, startIndex = 0) {
    const status = document.getElementById('copy-status');
    const speakButton = document.getElementById('speak-japanese-article');
    const firstIndex = Math.max(0, Math.min(startIndex, sentenceMeta.length));

    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
        status.textContent = 'Browser speech is not supported here.';
        setToolbarButtonState(speakButton);
        return;
    }

    const selectedVoice = getSelectedBrowserVoice();
    if (!selectedVoice) {
        status.textContent = 'No Japanese browser voice is available.';
        setToolbarButtonState(speakButton);
        return;
    }

    const speakSentenceAt = (sentenceIndex) => {
        if (sentenceIndex >= sentenceMeta.length) {
            speaking = false;
            browserUtterance = null;
            setToolbarButtonState(speakButton);
            status.textContent = 'Finished reading article.';
            clearHighlight();
            if (typeof onComplete === 'function') {
                onComplete();
            }
            return;
        }

        const sentence = sentenceMeta[sentenceIndex];
        const firstUnitId = sentence.unitIds[0];
        const firstUnitIndex = findUnitIndexById(firstUnitId);
        const utterance = new SpeechSynthesisUtterance(sentence.ttsText);
        browserUtterance = utterance;
        utterance.lang = 'ja-JP';
        utterance.rate = clampNumber(document.getElementById('browser-rate')?.value, voiceSettings.browserRate, 0.7, 1.2);
        utterance.pitch = clampNumber(document.getElementById('browser-pitch')?.value, voiceSettings.browserPitch, 0.8, 1.3);
        utterance.voice = selectedVoice;

        utterance.onstart = () => {
            speaking = true;
            setToolbarButtonState(speakButton, 'active');
            highlightUnit(firstUnitIndex);
            status.textContent = `Reading sentence ${sentenceIndex + 1}/${sentenceMeta.length} with ${selectedVoice.name}.`;
        };

        utterance.onend = () => {
            if (!speaking) {
                return;
            }
            clearHighlight();
            speakSentenceAt(sentenceIndex + 1);
        };

        utterance.onerror = () => {
            speaking = false;
            browserUtterance = null;
            setToolbarButtonState(speakButton);
            status.textContent = 'Read aloud failed in this browser.';
            clearHighlight();
        };

        window.speechSynthesis.speak(utterance);
    };

    window.speechSynthesis.cancel();
    clearHighlight();
    speakSentenceAt(firstIndex);
}

async function speakJapaneseArticle() {
    const status = document.getElementById('copy-status');
    const speakButton = document.getElementById('speak-japanese-article');

    if (speaking || localTtsPlaybackActive) {
        stopCurrentPlayback();
        status.textContent = 'Reading stopped.';
        return;
    }

    if (getSelectedVoiceSource() === 'docker') {
        await speakWithLocalTts();
        return;
    }

    setToolbarButtonState(speakButton, 'loading');
    status.textContent = 'Preparing browser voice...';
    speakWithBrowserSentenceQueue();
}

async function speakFromSentence(sentenceIndex) {
    if (!Number.isInteger(sentenceIndex) || sentenceIndex < 0 || sentenceIndex >= sentenceMeta.length) {
        return;
    }

    const status = document.getElementById('copy-status');
    const speakButton = document.getElementById('speak-japanese-article');

    if (speaking || localTtsPlaybackActive) {
        stopCurrentPlayback();
    }

    status.textContent = `Preparing to read from sentence ${sentenceIndex + 1}/${sentenceMeta.length}...`;

    if (getSelectedVoiceSource() === 'docker') {
        await speakWithLocalTts(sentenceIndex);
        return;
    }

    setToolbarButtonState(speakButton, 'loading');
    speakWithBrowserSentenceQueue(null, sentenceIndex);
}

async function fetchRenderedVideoUrl(speaker) {
    const response = await fetch('/api/video/render-url', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            article_id: articleId || currentArticleFile(),
            speaker,
            voicevoxProsody: getSelectedVoicevoxProsody()
        })
    });

    if (!response.ok) {
        let errorMessage = `Video render failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            if (payload.error) {
                errorMessage = payload.error;
            }
        } catch (error) {
            // Keep the HTTP status fallback if the response is not JSON.
        }

        throw new Error(errorMessage);
    }

    const payload = await response.json();
    if (!payload.download_url) {
        throw new Error('Video render response did not include a download URL.');
    }

    return {
        downloadUrl: payload.download_url,
        downloadName: payload.filename || recordingDownloadName
    };
}

function downloadGeneratedFile(url, filename) {
    if (!url) {
        return;
    }

    const downloadLink = document.createElement('a');
    downloadLink.href = url;
    if (filename) {
        downloadLink.download = filename;
    }
    downloadLink.click();
}

function filenameFromContentDisposition(headerValue, fallback) {
    const match = String(headerValue || '').match(/filename="([^"]+)"/i);
    return match?.[1] || fallback;
}

async function fetchRenderedCoverPhoto() {
    const response = await fetch('/api/video/render-cover', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            article_id: articleId || currentArticleFile()
        })
    });

    if (!response.ok) {
        let errorMessage = `Cover render failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            if (payload.error) {
                errorMessage = payload.error;
            }
        } catch (error) {
            // Keep the HTTP status fallback if the response is not JSON.
        }

        throw new Error(errorMessage);
    }

    const blob = await response.blob();
    const fallbackName = recordingDownloadName.replace(/\.mp4$/i, '-cover.png');
    return {
        objectUrl: URL.createObjectURL(blob),
        filename: filenameFromContentDisposition(response.headers.get('Content-Disposition'), fallbackName)
    };
}

function waitForNextPaint() {
    return new Promise((resolve) => {
        requestAnimationFrame(() => {
            requestAnimationFrame(resolve);
        });
    });
}

function ensureVideoRenderProgress() {
    let progress = document.getElementById('video-render-progress');
    if (progress) {
        return progress;
    }

    progress = document.createElement('div');
    progress.className = 'video-render-progress';
    progress.id = 'video-render-progress';
    progress.hidden = true;
    progress.innerHTML = `
        <div class="video-render-progress-header">
            <span class="video-render-progress-title">Rendering video</span>
            <span class="video-render-progress-percent" id="video-render-progress-percent">0%</span>
        </div>
        <div class="video-render-progress-track" role="progressbar" aria-label="Video render progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div class="video-render-progress-bar" id="video-render-progress-bar"></div>
        </div>
        <div class="video-render-progress-message" id="video-render-progress-message" aria-live="polite">Preparing render...</div>`;

    const status = document.getElementById('copy-status');
    if (status) {
        status.insertAdjacentElement('afterend', progress);
    } else {
        document.querySelector('.container')?.prepend(progress);
    }

    return progress;
}

function setVideoRenderProgress(percent, message) {
    const progress = ensureVideoRenderProgress();
    const normalizedPercent = Math.max(0, Math.min(100, Math.round(percent)));
    const track = progress.querySelector('.video-render-progress-track');
    const bar = document.getElementById('video-render-progress-bar');
    const percentLabel = document.getElementById('video-render-progress-percent');
    const messageLabel = document.getElementById('video-render-progress-message');

    progress.hidden = false;
    videoProgressPercent = normalizedPercent;
    track?.setAttribute('aria-valuenow', String(normalizedPercent));
    if (bar) {
        bar.style.width = `${normalizedPercent}%`;
    }
    if (percentLabel) {
        percentLabel.textContent = `${normalizedPercent}%`;
    }
    if (messageLabel && message) {
        messageLabel.textContent = message;
    }
}

function startVideoRenderProgress(message) {
    window.clearInterval(videoProgressTimer);
    let percent = 8;
    const progress = ensureVideoRenderProgress();
    progress.classList.remove('is-complete', 'is-error');
    setVideoRenderProgress(percent, message);
    videoProgressTimer = window.setInterval(() => {
        percent = Math.min(92, percent + Math.max(1, Math.round((92 - percent) * 0.08)));
        setVideoRenderProgress(percent);
    }, 900);
}

function completeVideoRenderProgress(message) {
    window.clearInterval(videoProgressTimer);
    videoProgressTimer = 0;
    ensureVideoRenderProgress().classList.add('is-complete');
    setVideoRenderProgress(100, message);
}

function failVideoRenderProgress(message) {
    window.clearInterval(videoProgressTimer);
    videoProgressTimer = 0;
    ensureVideoRenderProgress().classList.add('is-error');
    setVideoRenderProgress(Math.max(18, videoProgressPercent), message);
}

function hideVideoRenderProgress() {
    const progress = document.getElementById('video-render-progress');
    window.clearInterval(videoProgressTimer);
    videoProgressTimer = 0;
    if (progress) {
        progress.classList.remove('is-complete', 'is-error');
        progress.hidden = true;
    }
}

function clearRecordingMode() {
    document.body.classList.remove('recording-mode', 'recording-preview');
    document.body.style.removeProperty('--recording-title-size');
    document.body.style.removeProperty('--recording-body-size');
    document.body.style.removeProperty('--recording-body-line-height');
    document.body.style.removeProperty('--recording-preview-scale');
}

function openRecordingPreview() {
    const articleRef = articleId || currentArticleFile();
    if (!articleRef) {
        const status = document.getElementById('copy-status');
        if (status) {
            status.textContent = 'This page is missing its article identifier.';
        }
        return;
    }

    const previewUrl = new URL('/api/video/preview', window.location.origin);
    previewUrl.searchParams.set('article_id', articleRef);
    window.location.href = previewUrl.toString();
}

async function renderVideo() {
    const status = document.getElementById('copy-status');
    const renderButton = document.getElementById('render-video');

    if (recordingInProgress) {
        status.textContent = 'Video rendering is already in progress.';
        return;
    }

    if (!(articleId || currentArticleFile())) {
        status.textContent = 'This page is missing its article identifier.';
        return;
    }

    try {
        await populateLocalTtsVoiceOptions();
        const speaker = getSelectedLocalTtsSpeaker();
        setToolbarButtonState(renderButton, 'active');
        recordingInProgress = true;
        stopCurrentPlayback();
        startVideoRenderProgress('Preparing Docker VOICEVOX narration...');
        status.textContent = 'Preparing Docker VOICEVOX narration...';
        await waitForNextPaint();
        setVideoRenderProgress(18, 'Rendering 1080x1920 MP4...');
        status.textContent = 'Rendering 1080x1920 MP4...';

        const { downloadUrl, downloadName } = await fetchRenderedVideoUrl(speaker);
        downloadGeneratedFile(downloadUrl, downloadName);
        completeVideoRenderProgress('MP4 rendered and downloaded.');
        status.textContent = 'MP4 rendered and downloaded.';
    } catch (error) {
        failVideoRenderProgress(error?.message || 'Video rendering failed.');
        status.textContent = error?.message || 'Video rendering failed.';
    } finally {
        recordingInProgress = false;
        setToolbarButtonState(renderButton);
        window.setTimeout(() => {
            if (!recordingInProgress) {
                hideVideoRenderProgress();
            }
        }, 2600);
    }
}

async function handleRenderVideoClick() {
    await renderVideo();
}

async function downloadCoverPhoto() {
    const status = document.getElementById('copy-status');
    const coverButton = document.getElementById('download-cover');

    if (coverDownloadInProgress) {
        status.textContent = 'Cover rendering is already in progress.';
        return;
    }

    if (!(articleId || currentArticleFile())) {
        status.textContent = 'This page is missing its article identifier.';
        return;
    }

    let objectUrl = '';
    try {
        coverDownloadInProgress = true;
        setToolbarButtonState(coverButton, 'active');
        status.textContent = 'Rendering cover photo...';
        const cover = await fetchRenderedCoverPhoto();
        objectUrl = cover.objectUrl;
        downloadGeneratedFile(cover.objectUrl, cover.filename);
        status.textContent = 'Cover photo rendered and downloaded.';
    } catch (error) {
        status.textContent = error?.message || 'Cover rendering failed.';
    } finally {
        coverDownloadInProgress = false;
        setToolbarButtonState(coverButton);
        if (objectUrl) {
            window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        }
    }
}

async function handleDownloadCoverClick() {
    await downloadCoverPhoto();
}

function handlePreviewRecordingModeClick() {
    openRecordingPreview();
}

setupVoiceSettingsMenu();
insertVoiceSourceControls();
document.getElementById('browser-voice')?.addEventListener('change', () => {
    updateVoiceStatus();
    persistVoiceSettingsFromControls().catch(reportVoiceSettingsError);
});
document.getElementById('docker-voice')?.addEventListener('change', refreshArticleAudioCacheStatus);
document.getElementById('copy-bilingual-article')?.addEventListener('click', copyBilingualArticle);
document.getElementById('copy-vocabulary-list')?.addEventListener('click', copyVocabularyList);
document.getElementById('enable-docker-audio')?.addEventListener('click', () => {
    enableLocalTtsAudio().catch((error) => {
        const status = document.getElementById('copy-status');
        if (status) {
            status.textContent = error.message;
        }
    });
});
document.getElementById('speak-japanese-article')?.addEventListener('click', speakJapaneseArticle);
document.getElementById('preview-recording-mode')?.addEventListener('click', handlePreviewRecordingModeClick);
document.getElementById('render-video')?.addEventListener('click', handleRenderVideoClick);
document.getElementById('download-cover')?.addEventListener('click', handleDownloadCoverClick);
document.addEventListener('click', (event) => {
    const button = event.target.closest('.sentence-read-button');
    if (!button) {
        return;
    }

    event.preventDefault();
    speakFromSentence(Number(button.dataset.sentenceIndex));
});
if ('speechSynthesis' in window) {
    window.speechSynthesis.addEventListener('voiceschanged', populateBrowserVoiceOptions);
}
decorateReadingContent();
buildReadingUnits();
buildSentenceMeta();
renderSentencePlaybackButtons();
populateBrowserVoiceOptions();
loadVoiceSettings()
    .then(() => {
        populateBrowserVoiceOptions();
        applyVoiceSettingsToControls(voiceSettings);
        refreshArticleAudioCacheStatus();
    })
    .catch((error) => {
        reportVoiceSettingsError(error);
        refreshArticleAudioCacheStatus();
    });
initializeArticleNavigation();
