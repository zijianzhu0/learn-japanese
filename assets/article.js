const recordingDownloadName = document.body.dataset.recordingDownloadName || 'article.webm';
const defaultLocalTtsSpeaker = 3;
const silentAudioDataUrl = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQQAAAAAgICA';
const voicePreferenceKeys = {
    source: 'learnJapanese.voiceSource',
    browserVoice: 'learnJapanese.browserVoice',
    dockerSpeaker: 'learnJapanese.dockerSpeaker'
};
const articleNavigation = [
    {
        "month": "May 2026",
        "href": "./2026-05-29-library-tablets.html",
        "label": "5/29 図書館で多言語タブレット"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-28-cashless-ferry.html",
        "label": "5/28 離島フェリーでキャッシュレス化"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-27-shared-greenhouse.html",
        "label": "5/27 共同温室で若い農家"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-26-city-cooling-mist.html",
        "label": "5/26 駅前広場でミスト設備"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-25-seaweed-export-growth.html",
        "label": "5/25 日本ののり輸出"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-24-station-solar-roof.html",
        "label": "5/24 駅の屋根に太陽光設備"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-23-hotel-robots-support.html",
        "label": "5/23 ホテルで案内ロボット"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-22-hydrogen-port.html",
        "label": "5/22 港で水素燃料"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-21-rural-tourism-train.html",
        "label": "5/21 地方の観光列車"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-20-rice-price-support.html",
        "label": "5/20 米の値上がり対策"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-19-school-ai-guidelines.html",
        "label": "5/19 学校でAIルール"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-18-drone-disaster-drills.html",
        "label": "5/18 災害訓練でドローン"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-15-japan-us-alliance.html",
        "label": "5/15 日米同盟"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-15-alphabet-yen-bonds.html",
        "label": "5/15 グーグルの円社債"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-14-ly-kakaku-offer.html",
        "label": "5/14 価格.com買収資金"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-11-oil-prices-jump.html",
        "label": "5/11 原油価格"
    },
    {
        "month": "May 2026",
        "href": "./2026-05-01-yen-intervention.html",
        "label": "5/1 円安と市場介入"
    },
    {
        "month": "April 2026",
        "href": "./2026-04-11-rapidus-funding.html",
        "label": "4/11 ラピダス追加支援"
    }
];

function currentArticleFile() {
    return decodeURIComponent(window.location.pathname.split('/').pop() || '');
}

function normalizeArticleHref(href) {
    return href.replace(/^\.\//, '');
}

function getCurrentArticleIndex() {
    const currentFile = currentArticleFile();
    return articleNavigation.findIndex((article) => normalizeArticleHref(article.href) === currentFile);
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

function readVoicePreference(key) {
    try {
        return window.localStorage.getItem(key);
    } catch (error) {
        return null;
    }
}

function writeVoicePreference(key, value) {
    try {
        window.localStorage.setItem(key, value);
    } catch (error) {
        // Private browsing or storage policy restrictions should not block playback.
    }
}

function topNavLink(href, label, title, icon) {
    return `<a class="top-nav-link" href="${href}" aria-label="${label}" title="${title}">${icon}<span class="icon-label">${label}</span></a>`;
}

function renderTopNavigation() {
    const topNav = document.querySelector('.top-nav');
    if (!topNav) {
        return;
    }

    const currentIndex = getCurrentArticleIndex();
    const nextArticle = currentIndex >= 0
        ? articleNavigation[(currentIndex + 1) % articleNavigation.length]
        : articleNavigation[0];
    const lastArticle = articleNavigation[articleNavigation.length - 1];
    const homeIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"></path><path d="M6.5 10.5V20h15v-9.5"></path><path d="M10 20v-5h4v5"></path></svg>';
    const nextIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>';
    const lastIcon = '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 18 6-6-6-6"></path><path d="M17 6v12"></path></svg>';

    topNav.innerHTML = [
        topNavLink('./index.html', 'Home', 'Home', homeIcon),
        topNavLink(nextArticle.href, 'Next Page', 'Next page', nextIcon),
        topNavLink(lastArticle.href, 'Last Page', 'Last page', lastIcon)
    ].join('');
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
        const isCurrent = normalizeArticleHref(article.href) === currentFile;
        const className = isCurrent ? 'article-nav-link is-current' : 'article-nav-link';
        const ariaCurrent = isCurrent ? ' aria-current="page"' : '';
        return `                        <li><a class="${className}" href="${article.href}"${ariaCurrent}>${escapeHtml(article.label)}</a></li>`;
    }).join('\n')}
                    </ul>
                </div>`).join('');
}

function renderArticleNavigation() {
    const sidebar = document.querySelector('.article-sidebar');
    if (!sidebar) {
        return;
    }

    const currentFile = currentArticleFile();
    const groupsHtml = articleNavigationGroupsHtml(currentFile);
    const menuIcon = '<svg class="nav-svg menu-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path></svg>';
    const closeIcon = '<svg class="nav-svg close-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>';

    sidebar.innerHTML = `
        <h2 class="site-title">Japanese Reading</h2>
        <p class="site-subtitle">Quick links to every article.</p>
        <nav class="desktop-article-nav">${groupsHtml}
        </nav>
        <details class="mobile-article-menu">
            <summary aria-label="Article navigation" title="Article navigation">${menuIcon}${closeIcon}<span class="icon-label">Article Navigation</span></summary>
            <nav class="mobile-nav-content" aria-label="Folded article navigation">${groupsHtml}
            </nav>
        </details>`;
}

let speaking = false;
let readingUnits = [];
let currentUnitIndex = -1;
let browserUtterance = null;
let sentenceMeta = [];
let availableBrowserVoices = [];
let recordingInProgress = false;
let activeMediaRecorder = null;
let activeRecordingStream = null;
let localTtsPlaybackActive = false;
let localTtsPlaybackRun = 0;
let activeTtsAudioUrl = null;
let localTtsAudioUnlocked = false;
let localTtsSpeakersLoaded = false;

function extractRubyBaseText(element) {
    const clone = element.cloneNode(true);
    clone.querySelectorAll('rt, rp').forEach((node) => node.remove());
    return clone.textContent.replace(/\s+/g, ' ').trim();
}

function buildJapaneseArticleText() {
    const title = extractRubyBaseText(document.querySelector('h1'));
    const paragraphs = Array.from(document.querySelectorAll('.article-paragraph'))
        .map((paragraph) => extractRubyBaseText(paragraph));
    return [title, ...paragraphs].join('\n\n');
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

        sentences.forEach((sentence) => {
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
                unitIds
            });
        });
    });

    sentenceMeta = metadata;
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
        return;
    }

    const voices = window.speechSynthesis.getVoices().filter((voice) => voice.lang === 'ja-JP');
    availableBrowserVoices = voices;

    const savedValue = readVoicePreference(voicePreferenceKeys.browserVoice);
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
}

function getSelectedBrowserVoice() {
    const select = document.getElementById('browser-voice');
    return availableBrowserVoices.find((voice) => voice.name === select.value) || null;
}

function getSelectedVoiceSource() {
    const select = document.getElementById('voice-source');
    return select?.value === 'docker' ? 'docker' : 'browser';
}

function getSelectedLocalTtsSpeaker() {
    const select = document.getElementById('docker-voice');
    const speaker = Number(select?.value);
    return Number.isInteger(speaker) ? speaker : defaultLocalTtsSpeaker;
}

function updateVoiceControlVisibility() {
    const source = getSelectedVoiceSource();
    const browserVoice = document.getElementById('browser-voice');
    const browserVoiceLabel = document.querySelector('label[for="browser-voice"]');
    const dockerVoice = document.getElementById('docker-voice');
    const dockerVoiceLabel = document.querySelector('label[for="docker-voice"]');

    if (browserVoice && browserVoiceLabel) {
        const isBrowser = source === 'browser';
        browserVoice.hidden = !isBrowser;
        browserVoiceLabel.hidden = !isBrowser;
    }

    if (dockerVoice && dockerVoiceLabel) {
        const isDocker = source === 'docker';
        dockerVoice.hidden = !isDocker;
        dockerVoiceLabel.hidden = !isDocker;
    }
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

function insertVoiceSourceControls() {
    const toolbar = document.querySelector('.article-toolbar');
    const browserVoice = document.getElementById('browser-voice');
    const browserVoiceLabel = document.querySelector('label[for="browser-voice"]');
    if (!toolbar || !browserVoice || !browserVoiceLabel || document.getElementById('voice-source')) {
        return;
    }

    const sourceLabel = document.createElement('label');
    sourceLabel.className = 'toolbar-label';
    sourceLabel.htmlFor = 'voice-source';
    sourceLabel.textContent = 'Voice Source';

    const sourceSelect = document.createElement('select');
    sourceSelect.className = 'voice-select';
    sourceSelect.id = 'voice-source';
    sourceSelect.setAttribute('aria-label', 'Voice source');
    sourceSelect.innerHTML = [
        '<option value="browser" selected>Browser Voice</option>',
        '<option value="docker">Docker VOICEVOX</option>'
    ].join('');
    const savedSource = readVoicePreference(voicePreferenceKeys.source);
    if (savedSource === 'browser' || savedSource === 'docker') {
        sourceSelect.value = savedSource;
    }
    sourceSelect.addEventListener('change', () => {
        writeVoicePreference(voicePreferenceKeys.source, getSelectedVoiceSource());
        updateVoiceControlVisibility();
        if (getSelectedVoiceSource() === 'docker') {
            populateLocalTtsVoiceOptions();
        }
    });

    const dockerVoiceLabel = document.createElement('label');
    dockerVoiceLabel.className = 'toolbar-label';
    dockerVoiceLabel.htmlFor = 'docker-voice';
    dockerVoiceLabel.textContent = 'Docker Voice';

    const dockerVoice = document.createElement('select');
    dockerVoice.className = 'voice-select';
    dockerVoice.id = 'docker-voice';
    dockerVoice.setAttribute('aria-label', 'Docker VOICEVOX voice');
    dockerVoice.innerHTML = `<option value="${defaultLocalTtsSpeaker}" selected>VOICEVOX speaker ${defaultLocalTtsSpeaker}</option>`;
    const savedSpeaker = readVoicePreference(voicePreferenceKeys.dockerSpeaker);
    if (savedSpeaker) {
        dockerVoice.value = savedSpeaker;
    }
    dockerVoice.addEventListener('change', () => {
        writeVoicePreference(voicePreferenceKeys.dockerSpeaker, dockerVoice.value);
    });

    toolbar.insertBefore(sourceLabel, browserVoiceLabel);
    toolbar.insertBefore(sourceSelect, browserVoiceLabel);
    toolbar.insertBefore(dockerVoiceLabel, browserVoice.nextSibling);
    toolbar.insertBefore(dockerVoice, dockerVoiceLabel.nextSibling);
    updateVoiceControlVisibility();
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

    return unlocked;
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
        const savedValue = readVoicePreference(voicePreferenceKeys.dockerSpeaker);
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

        if (savedValue && [...select.options].some((option) => option.value === savedValue)) {
            select.value = savedValue;
        } else if ([...select.options].some((option) => option.value === previousValue)) {
            select.value = previousValue;
        } else if ([...select.options].some((option) => option.value === String(payload.default_speaker))) {
            select.value = String(payload.default_speaker);
        }

        localTtsSpeakersLoaded = true;
    } catch (error) {
        select.innerHTML = `<option value="${defaultLocalTtsSpeaker}">Start Docker VOICEVOX</option>`;
        if (status && getSelectedVoiceSource() === 'docker') {
            status.textContent = error.message;
        }
    }
}

async function fetchLocalTtsAudio(text, speaker = getSelectedLocalTtsSpeaker()) {
    const response = await fetch('/api/tts/voicevox', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            text,
            speaker
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

    return response.blob();
}

async function buildLocalTtsAudioQueue(status, speaker = getSelectedLocalTtsSpeaker()) {
    const audioBlobs = [];
    for (let index = 0; index < sentenceMeta.length; index += 1) {
        status.textContent = `Generating Docker TTS sentence ${index + 1}/${sentenceMeta.length}...`;
        audioBlobs.push(await fetchLocalTtsAudio(sentenceMeta[index].text, speaker));
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
        activeTtsAudioUrl = URL.createObjectURL(audioBlob);
        audioPlayer.src = activeTtsAudioUrl;
        highlightUnit(getSentenceFirstUnitIndex(sentence));
        status.textContent = `Playing Docker TTS sentence ${sentenceIndex + 1}/${sentenceMeta.length}.`;

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

async function playLocalTtsQueue({ audioBlobs = null, speaker = getSelectedLocalTtsSpeaker() } = {}) {
    const status = document.getElementById('copy-status');
    const speakButton = document.getElementById('speak-japanese-article');
    const runId = localTtsPlaybackRun + 1;

    stopCurrentPlayback();
    localTtsPlaybackRun = runId;
    localTtsPlaybackActive = true;
    if (speakButton) {
        speakButton.textContent = 'Stop Reading';
    }

    try {
        for (let index = 0; index < sentenceMeta.length; index += 1) {
            if (!localTtsPlaybackActive || runId !== localTtsPlaybackRun) {
                throw new Error('Docker TTS playback was stopped.');
            }

            const sentence = sentenceMeta[index];
            const audioBlob = audioBlobs
                ? audioBlobs[index]
                : await fetchLocalTtsAudio(sentence.text, speaker);
            await playLocalTtsAudioBlob(audioBlob, sentence, index, runId);
        }

        status.textContent = 'Finished Docker TTS reading.';
    } finally {
        if (runId === localTtsPlaybackRun) {
            localTtsPlaybackActive = false;
            clearHighlight();
            revokeActiveTtsAudioUrl();
            if (speakButton) {
                speakButton.textContent = 'Read Aloud';
            }
        }
    }
}

async function playLocalTtsArticle() {
    const status = document.getElementById('copy-status');

    if (localTtsPlaybackActive) {
        stopCurrentPlayback();
        status.textContent = 'Docker TTS stopped.';
        return;
    }

    try {
        status.textContent = 'Preparing Docker TTS...';
        await populateLocalTtsVoiceOptions();
        await playLocalTtsQueue();
    } catch (error) {
        if (!String(error.message).includes('stopped')) {
            status.textContent = error.message;
        }
    }
}

async function speakWithLocalTts() {
    const status = document.getElementById('copy-status');
    if (!localTtsPlaybackActive) {
        const audioReady = await unlockLocalTtsAudio();
        if (!audioReady) {
            status.textContent = 'Browser blocked Docker TTS audio startup. Click Read Aloud again directly in the page.';
            return;
        }
    }
    await playLocalTtsArticle();
}

async function copyJapaneseArticle() {
    const status = document.getElementById('copy-status');
    const articleText = buildJapaneseArticleText();

    try {
        await navigator.clipboard.writeText(articleText);
        status.textContent = 'Japanese article copied to clipboard.';
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
        speakButton.textContent = 'Read Aloud';
    }
}

function speakWithBrowserSentenceQueue(onComplete = null) {
    const status = document.getElementById('copy-status');
    const speakButton = document.getElementById('speak-japanese-article');

    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
        status.textContent = 'Browser speech is not supported here.';
        return;
    }

    const selectedVoice = getSelectedBrowserVoice();
    if (!selectedVoice) {
        status.textContent = 'No Japanese browser voice is available.';
        return;
    }

    const speakSentenceAt = (sentenceIndex) => {
        if (sentenceIndex >= sentenceMeta.length) {
            speaking = false;
            browserUtterance = null;
            speakButton.textContent = 'Read Aloud';
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
        const utterance = new SpeechSynthesisUtterance(sentence.text);
        browserUtterance = utterance;
        utterance.lang = 'ja-JP';
        utterance.rate = 0.9;
        utterance.pitch = 1;
        utterance.voice = selectedVoice;

        utterance.onstart = () => {
            speaking = true;
            speakButton.textContent = 'Stop Reading';
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
            speakButton.textContent = 'Read Aloud';
            status.textContent = 'Read aloud failed in this browser.';
            clearHighlight();
        };

        window.speechSynthesis.speak(utterance);
    };

    window.speechSynthesis.cancel();
    clearHighlight();
    speakSentenceAt(0);
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

    speakButton.textContent = 'Preparing Audio...';
    status.textContent = 'Preparing browser voice...';
    speakWithBrowserSentenceQueue();
}

function chooseRecorderMimeType() {
    const candidates = [
        'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
        'video/mp4;codecs=h264,aac',
        'video/mp4',
        'video/webm;codecs=vp9,opus',
        'video/webm;codecs=vp8,opus',
        'video/webm'
    ];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || '';
}

function recordingExtensionForMimeType(mimeType) {
    return mimeType.startsWith('video/mp4') ? 'mp4' : 'webm';
}

function recordingDownloadNameForMimeType(mimeType) {
    const extension = recordingExtensionForMimeType(mimeType);
    return recordingDownloadName.replace(/\.[^.]+$/, `.${extension}`);
}

async function convertRecordingToMp4(videoBlob) {
    const response = await fetch('/api/video/convert-mp4', {
        method: 'POST',
        headers: {
            'Content-Type': videoBlob.type || 'video/webm'
        },
        body: videoBlob
    });

    if (!response.ok) {
        let errorMessage = `MP4 conversion failed with HTTP ${response.status}.`;
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

    return response.blob();
}

function waitForNextPaint() {
    return new Promise((resolve) => {
        requestAnimationFrame(() => {
            requestAnimationFrame(resolve);
        });
    });
}

function isRecordingPreviewMode() {
    return new URLSearchParams(window.location.search).has('recording-preview');
}

async function fitRecordingPageText() {
    const container = document.querySelector('.container');
    if (!container) {
        return;
    }

    document.body.style.removeProperty('--recording-title-size');
    document.body.style.removeProperty('--recording-body-size');
    document.body.style.removeProperty('--recording-body-line-height');
    await waitForNextPaint();

    const pageWidth = container.clientWidth || window.innerWidth;
    let bodySize = Math.max(22, Math.min(58, pageWidth * 0.035));
    let titleSize = bodySize * 1.32;
    let lineHeight = 1.68;

    const applySizes = () => {
        document.body.style.setProperty('--recording-title-size', `${titleSize}px`);
        document.body.style.setProperty('--recording-body-size', `${bodySize}px`);
        document.body.style.setProperty('--recording-body-line-height', String(lineHeight));
    };

    applySizes();
    await waitForNextPaint();

    while (container.scrollHeight > container.clientHeight && bodySize > 12) {
        bodySize -= 1;
        titleSize = bodySize * 1.32;
        if (bodySize < 18) {
            lineHeight = 1.48;
        } else if (bodySize < 22) {
            lineHeight = 1.56;
        }
        applySizes();
        await waitForNextPaint();
    }
}

async function renderVideo() {
    const status = document.getElementById('copy-status');
    const renderButton = document.getElementById('render-video');

    if (recordingInProgress) {
        status.textContent = 'Video recording is already in progress.';
        return;
    }

    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getDisplayMedia !== 'function') {
        status.textContent = 'This browser cannot record the current tab.';
        return;
    }

    if (typeof MediaRecorder === 'undefined') {
        status.textContent = 'MediaRecorder is not available in this browser.';
        return;
    }

    const useLocalTts = getSelectedVoiceSource() === 'docker';
    let localTtsAudioBlobs = null;
    if (useLocalTts) {
        try {
            await populateLocalTtsVoiceOptions();
            localTtsAudioBlobs = await buildLocalTtsAudioQueue(status);
        } catch (error) {
            status.textContent = error.message;
            return;
        }
    }

    const stopRecorder = () => {
        if (activeMediaRecorder && activeMediaRecorder.state !== 'inactive') {
            activeMediaRecorder.stop();
        }
    };

    try {
        renderButton.textContent = 'Recording...';
        status.textContent = useLocalTts
            ? 'Share the current tab and enable audio to record Docker TTS narration.'
            : 'Share the current tab and enable audio to record the highlighted reading.';
        activeRecordingStream = await navigator.mediaDevices.getDisplayMedia({
            video: { frameRate: 30 },
            audio: true,
            preferCurrentTab: true
        });

        const mimeType = chooseRecorderMimeType();
        const recordedChunks = [];
        activeMediaRecorder = mimeType
            ? new MediaRecorder(activeRecordingStream, { mimeType })
            : new MediaRecorder(activeRecordingStream);

        activeMediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };

        activeMediaRecorder.onstop = async () => {
            const outputMimeType = activeMediaRecorder.mimeType || 'video/webm';
            let blob = new Blob(recordedChunks, {
                type: outputMimeType
            });
            let downloadName = recordingDownloadNameForMimeType(outputMimeType);
            let conversionFailed = false;

            if (!outputMimeType.startsWith('video/mp4')) {
                status.textContent = 'Converting recording to MP4...';
                try {
                    blob = await convertRecordingToMp4(blob);
                    downloadName = recordingDownloadNameForMimeType('video/mp4');
                } catch (error) {
                    conversionFailed = true;
                    status.textContent = `${error.message} Downloading WebM instead.`;
                }
            }

            const videoUrl = URL.createObjectURL(blob);
            const downloadLink = document.createElement('a');
            downloadLink.href = videoUrl;
            downloadLink.download = downloadName;
            downloadLink.click();
            URL.revokeObjectURL(videoUrl);

            activeRecordingStream.getTracks().forEach((track) => track.stop());
            activeRecordingStream = null;
            activeMediaRecorder = null;
            recordingInProgress = false;
            document.body.classList.remove('recording-mode');
            document.body.style.removeProperty('--recording-title-size');
            document.body.style.removeProperty('--recording-body-size');
            document.body.style.removeProperty('--recording-body-line-height');
            renderButton.textContent = 'Render Video';
            if (!conversionFailed) {
                status.textContent = downloadName.endsWith('.mp4')
                    ? 'MP4 rendered and downloaded.'
                    : 'Video rendered and downloaded.';
            }
        };

        recordingInProgress = true;
        document.body.classList.add('recording-mode');
        stopCurrentPlayback();
        await fitRecordingPageText();
        await waitForNextPaint();
        activeMediaRecorder.start();

        if (useLocalTts) {
            playLocalTtsQueue({ audioBlobs: localTtsAudioBlobs, updateButton: false })
                .then(stopRecorder)
                .catch((error) => {
                    status.textContent = error.message;
                    stopRecorder();
                });
        } else {
            speakWithBrowserSentenceQueue(stopRecorder);
        }
    } catch (error) {
        if (activeRecordingStream) {
            activeRecordingStream.getTracks().forEach((track) => track.stop());
            activeRecordingStream = null;
        }
        activeMediaRecorder = null;
        recordingInProgress = false;
        document.body.classList.remove('recording-mode');
        document.body.style.removeProperty('--recording-title-size');
        document.body.style.removeProperty('--recording-body-size');
        document.body.style.removeProperty('--recording-body-line-height');
        renderButton.textContent = 'Render Video';
        status.textContent = 'Video recording was cancelled or blocked.';
    }
}

async function handleRenderVideoClick() {
    if (getSelectedVoiceSource() === 'docker') {
        const status = document.getElementById('copy-status');
        const audioReady = await unlockLocalTtsAudio();
        if (!audioReady) {
            status.textContent = 'Browser blocked Docker TTS audio startup. Click Render Video again directly in the page.';
            return;
        }
    }
    await renderVideo();
}

renderTopNavigation();
renderArticleNavigation();
insertVoiceSourceControls();
document.getElementById('browser-voice')?.addEventListener('change', (event) => {
    writeVoicePreference(voicePreferenceKeys.browserVoice, event.target.value);
});
document.getElementById('copy-japanese-article')?.addEventListener('click', copyJapaneseArticle);
document.getElementById('speak-japanese-article')?.addEventListener('click', speakJapaneseArticle);
document.getElementById('render-video')?.addEventListener('click', handleRenderVideoClick);
if ('speechSynthesis' in window) {
    window.speechSynthesis.addEventListener('voiceschanged', populateBrowserVoiceOptions);
}
decorateReadingContent();
buildReadingUnits();
buildSentenceMeta();
populateBrowserVoiceOptions();
if (isRecordingPreviewMode()) {
    document.body.classList.add('recording-mode');
    fitRecordingPageText();
}
