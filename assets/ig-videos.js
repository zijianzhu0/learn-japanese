const manifestUrl = './data/flashcards.json';
const defaultDockerSpeaker = 9;
const dockerSpeakerPreferenceKey = 'learnJapanese.dockerSpeaker';
const wordCount = 5;

let manifestItems = [];
let visibleItems = [];
let currentSetIndex = 0;
let activeAudioUrl = null;
let playbackRun = 0;
let playbackActive = false;

const elements = {
    levelFilter: document.getElementById('level-filter'),
    sourceFilter: document.getElementById('source-filter'),
    dockerVoice: document.getElementById('docker-voice'),
    previousSet: document.getElementById('previous-set'),
    shuffleSet: document.getElementById('shuffle-set'),
    nextSet: document.getElementById('next-set'),
    readSet: document.getElementById('read-set'),
    renderVideo: document.getElementById('render-video'),
    status: document.getElementById('status-line'),
    title: document.getElementById('stage-title'),
    meta: document.getElementById('stage-meta'),
    list: document.getElementById('word-list'),
    counter: document.getElementById('set-counter'),
    audio: document.getElementById('tts-player')
};

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[character]));
}

function selectedSpeaker() {
    const value = Number(elements.dockerVoice?.value);
    return Number.isInteger(value) ? value : defaultDockerSpeaker;
}

function saveSpeaker() {
    try {
        window.localStorage.setItem(dockerSpeakerPreferenceKey, String(selectedSpeaker()));
    } catch (error) {
        // Storage restrictions should not block playback.
    }
}

function savedSpeaker() {
    try {
        const value = Number(window.localStorage.getItem(dockerSpeakerPreferenceKey));
        return Number.isInteger(value) ? value : defaultDockerSpeaker;
    } catch (error) {
        return defaultDockerSpeaker;
    }
}

function itemReading(item) {
    return item.readingHiragana || item.reading || '';
}

function itemTerm(item) {
    return String(item.term || '').split('/')[0].trim();
}

function itemMeaning(item) {
    return String(item.meaning || '').split(';')[0].trim();
}

function itemSourceMatches(item, source) {
    return source === 'all' || item.source === source;
}

function applyFilters() {
    const level = elements.levelFilter.value;
    const source = elements.sourceFilter.value;
    visibleItems = manifestItems.filter((item) => {
        const matchesLevel = level === 'all' || item.level === level;
        return matchesLevel && itemSourceMatches(item, source);
    });
    currentSetIndex = 0;
    renderCurrentSet();
}

function currentSetItems() {
    const start = currentSetIndex * wordCount;
    return visibleItems.slice(start, start + wordCount);
}

function totalSets() {
    return Math.max(1, Math.ceil(visibleItems.length / wordCount));
}

function wordRubyHtml(item) {
    const term = itemTerm(item);
    const reading = itemReading(item);
    if (!reading || reading === term) {
        return escapeHtml(term);
    }
    return `<ruby>${escapeHtml(term)}<rt>${escapeHtml(reading)}</rt></ruby>`;
}

function renderCurrentSet() {
    clearHighlight();
    const items = currentSetItems();
    const level = elements.levelFilter.value === 'all' ? 'Mixed JLPT' : elements.levelFilter.value;
    elements.title.textContent = `${level} · 5 words`;
    elements.meta.textContent = `${items.length}/${wordCount} words · 9:16`;
    elements.counter.textContent = `Set ${Math.min(currentSetIndex + 1, totalSets())}/${totalSets()}`;

    if (!items.length) {
        elements.list.innerHTML = '<li class="word-card"><div class="word-main"><span class="word-term">No words</span><span class="word-meaning">Change the filters.</span></div></li>';
        elements.status.textContent = 'No vocabulary matches the current filters.';
        return;
    }

    elements.list.innerHTML = items.map((item, index) => `
        <li class="word-card" data-word-index="${index}">
            <span class="word-index">${index + 1}</span>
            <span class="word-main">
                <span class="word-term">${wordRubyHtml(item)}</span>
                <span class="word-meaning">${escapeHtml(itemMeaning(item))}</span>
            </span>
            <span class="level-pill">${escapeHtml(item.level)}</span>
        </li>
    `).join('');
    elements.status.textContent = `Showing ${items.length} words from ${visibleItems.length} available vocabulary items.`;
}

function clearHighlight() {
    document.querySelectorAll('.word-card.is-speaking').forEach((card) => card.classList.remove('is-speaking'));
}

function highlightWord(index) {
    clearHighlight();
    const card = document.querySelector(`.word-card[data-word-index="${index}"]`);
    if (card) {
        card.classList.add('is-speaking');
        card.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
}

function revokeActiveAudioUrl() {
    if (activeAudioUrl) {
        URL.revokeObjectURL(activeAudioUrl);
        activeAudioUrl = null;
    }
}

async function fetchLocalTtsStatus() {
    const response = await fetch('/api/tts/voicevox/status', { cache: 'no-store' });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || `VOICEVOX status failed with HTTP ${response.status}.`);
    }
    return payload;
}

async function populateVoiceOptions() {
    try {
        const payload = await fetchLocalTtsStatus();
        const preferred = String(savedSpeaker());
        elements.dockerVoice.innerHTML = '';
        payload.speakers.forEach((speaker) => {
            speaker.styles.forEach((style) => {
                const option = document.createElement('option');
                option.value = String(style.id);
                option.textContent = `${speaker.name} - ${style.name}`;
                elements.dockerVoice.appendChild(option);
            });
        });
        if ([...elements.dockerVoice.options].some((option) => option.value === preferred)) {
            elements.dockerVoice.value = preferred;
        } else {
            elements.dockerVoice.value = String(payload.default_speaker);
        }
    } catch (error) {
        elements.status.textContent = error.message;
    }
}

async function fetchLocalTtsAudio(text) {
    const response = await fetch('/api/tts/voicevox', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, speaker: selectedSpeaker() })
    });
    if (!response.ok) {
        let errorMessage = `VOICEVOX TTS failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            errorMessage = payload.error || errorMessage;
        } catch (error) {
            // Keep HTTP fallback.
        }
        throw new Error(errorMessage);
    }
    return response.blob();
}

function playAudioBlob(blob, index, runId) {
    return new Promise((resolve, reject) => {
        elements.audio.onended = () => {
            clearHighlight();
            resolve();
        };
        elements.audio.onerror = () => {
            clearHighlight();
            reject(new Error('Audio playback failed.'));
        };
        revokeActiveAudioUrl();
        activeAudioUrl = URL.createObjectURL(blob);
        elements.audio.src = activeAudioUrl;
        highlightWord(index);
        elements.audio.play().catch(reject);
    }).then(() => {
        if (runId !== playbackRun) {
            throw new Error('Playback stopped.');
        }
    });
}

function stopPlayback() {
    playbackActive = false;
    playbackRun += 1;
    elements.audio.pause();
    elements.audio.removeAttribute('src');
    elements.audio.load();
    revokeActiveAudioUrl();
    clearHighlight();
    elements.readSet.querySelector('span').textContent = 'Read';
}

async function readCurrentSet() {
    if (playbackActive) {
        stopPlayback();
        elements.status.textContent = 'Reading stopped.';
        return;
    }

    const items = currentSetItems();
    if (!items.length) {
        return;
    }

    playbackActive = true;
    const runId = playbackRun + 1;
    playbackRun = runId;
    elements.readSet.querySelector('span').textContent = 'Stop';

    try {
        for (let index = 0; index < items.length; index += 1) {
            if (!playbackActive || runId !== playbackRun) {
                throw new Error('Playback stopped.');
            }
            const text = itemTerm(items[index]);
            elements.status.textContent = `Generating Japanese TTS ${index + 1}/${items.length}: ${text}`;
            const blob = await fetchLocalTtsAudio(text);
            elements.status.textContent = `Reading ${index + 1}/${items.length}: ${text}`;
            await playAudioBlob(blob, index, runId);
        }
        elements.status.textContent = 'Finished reading this set.';
    } catch (error) {
        if (!String(error.message).includes('stopped')) {
            elements.status.textContent = error.message;
        }
    } finally {
        if (runId === playbackRun) {
            playbackActive = false;
            elements.readSet.querySelector('span').textContent = 'Read';
            clearHighlight();
            revokeActiveAudioUrl();
        }
    }
}

async function renderVideo() {
    const items = currentSetItems();
    if (items.length !== wordCount) {
        elements.status.textContent = 'Pick a full set of five words before rendering.';
        return;
    }

    try {
        stopPlayback();
        saveSpeaker();
        elements.renderVideo.disabled = true;
        elements.status.textContent = 'Rendering 1080x1920 MP4 with VOICEVOX...';
        const response = await fetch('/api/video/render-vocab-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                item_ids: items.map((item) => item.id),
                speaker: selectedSpeaker()
            })
        });
        if (!response.ok) {
            let errorMessage = `Video render failed with HTTP ${response.status}.`;
            try {
                const payload = await response.json();
                errorMessage = payload.error || errorMessage;
            } catch (error) {
                // Keep HTTP fallback.
            }
            throw new Error(errorMessage);
        }
        const payload = await response.json();
        const downloadLink = document.createElement('a');
        downloadLink.href = payload.download_url;
        downloadLink.download = payload.filename || 'ig-vocabulary-video.mp4';
        downloadLink.click();
        elements.status.textContent = 'MP4 rendered and downloaded.';
    } catch (error) {
        elements.status.textContent = error.message;
    } finally {
        elements.renderVideo.disabled = false;
    }
}

function moveSet(delta) {
    if (!visibleItems.length) {
        return;
    }
    currentSetIndex = (currentSetIndex + delta + totalSets()) % totalSets();
    renderCurrentSet();
}

function shuffleSet() {
    if (!visibleItems.length) {
        return;
    }
    currentSetIndex = Math.floor(Math.random() * totalSets());
    renderCurrentSet();
}

async function loadManifest() {
    const response = await fetch(manifestUrl, { cache: 'no-cache' });
    if (!response.ok) {
        throw new Error(`Vocabulary manifest failed to load with HTTP ${response.status}.`);
    }
    const payload = await response.json();
    manifestItems = Array.isArray(payload.items) ? payload.items : [];
    applyFilters();
}

elements.levelFilter.addEventListener('change', applyFilters);
elements.sourceFilter.addEventListener('change', applyFilters);
elements.dockerVoice.addEventListener('change', saveSpeaker);
elements.previousSet.addEventListener('click', () => moveSet(-1));
elements.nextSet.addEventListener('click', () => moveSet(1));
elements.shuffleSet.addEventListener('click', shuffleSet);
elements.readSet.addEventListener('click', readCurrentSet);
elements.renderVideo.addEventListener('click', renderVideo);

populateVoiceOptions();
loadManifest().catch((error) => {
    elements.status.textContent = error.message;
});
