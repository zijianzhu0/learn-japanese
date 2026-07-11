const flashcardManifestUrl = './data/flashcards.json';
const flashcardProgressUrl = '/api/flashcards/progress';
const legacyDbName = 'learnJapaneseFlashcards';
const oneDayMs = 24 * 60 * 60 * 1000;
const defaultDockerSpeaker = 9;
const dockerSpeakerPreferenceKey = 'learnJapanese.dockerSpeaker';
const silentAudioDataUrl = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQQAAAAAgICA';

let manifest = { items: [] };
let progressByCardId = new Map();
let studyItems = [];
let visibleItems = [];
let currentItem = null;
let currentCard = null;
let answerRevealed = false;
let skippedCardId = null;
let previousCardId = null;
let pronunciationAudioUnlocked = false;
let activePronunciationUrl = null;
let preparedPronunciation = null;
let pronunciationCacheState = 'unknown';
let pronunciationCacheStatusRun = 0;
let progressServerAvailable = true;

const elements = {
    levelFilter: document.getElementById('level-filter'),
    studyModeFilter: document.getElementById('study-mode-filter'),
    verbFormFilter: document.getElementById('verb-form-filter'),
    dueOnly: document.getElementById('due-only'),
    total: document.getElementById('stat-total'),
    due: document.getElementById('stat-due'),
    shown: document.getElementById('stat-shown'),
    remembered: document.getElementById('stat-remembered'),
    forgot: document.getElementById('stat-forgot'),
    streak: document.getElementById('stat-streak'),
    cardLevel: document.getElementById('card-level'),
    cardSource: document.getElementById('card-source'),
    cardForm: document.getElementById('card-form'),
    cardTerm: document.getElementById('card-term'),
    cardReading: document.getElementById('card-reading'),
    cardBaseVerb: document.getElementById('card-base-verb'),
    cardVerbForms: document.getElementById('card-verb-forms'),
    cardExample: document.getElementById('card-example'),
    cardExampleJa: document.getElementById('card-example-ja'),
    cardExampleEn: document.getElementById('card-example-en'),
    cardExampleCount: document.getElementById('card-example-count'),
    cardMeaning: document.getElementById('card-meaning'),
    answerLabel: document.getElementById('answer-label'),
    flashcard: document.getElementById('flashcard'),
    reveal: document.getElementById('reveal-card'),
    remember: document.getElementById('remember-card'),
    forgotButton: document.getElementById('forgot-card'),
    skip: document.getElementById('skip-card'),
    sourceLink: document.getElementById('source-link'),
    emptyState: document.getElementById('empty-state'),
    pronounceWord: document.getElementById('pronounce-word'),
    pronounceExample: document.getElementById('pronounce-example'),
    pronunciationStatus: document.getElementById('pronunciation-status'),
    audio: document.getElementById('flashcard-audio'),
    exportProgress: document.getElementById('export-progress'),
    importProgress: document.getElementById('import-progress'),
    resetProgress: document.getElementById('reset-progress'),
    progressStorageStatus: document.getElementById('progress-storage-status')
};

function cardIdForItem(item) {
    return item.cardId || `recognition:${item.id}`;
}

function cloneExampleSentences(examples) {
    return Array.isArray(examples)
        ? examples
            .filter((example) => example?.ja && example?.en)
            .map((example) => ({ ja: example.ja, en: example.en }))
        : [];
}

function buildStudyItems(items) {
    const built = [];

    items.forEach((item) => {
        const baseItem = {
            ...item,
            studyType: 'vocabulary',
            cardId: `recognition:${item.id}`
        };
        built.push(baseItem);

        const forms = Array.isArray(item.verbForms) ? item.verbForms : [];
        if (!forms.length) {
            return;
        }

        const companionForms = forms.map((form) => ({
            ...form,
            isCurrent: false
        }));
        const fallbackExamples = cloneExampleSentences(item.exampleSentences);
        const baseReading = item.readingHiragana || item.reading || '';
        forms.forEach((form) => {
            const formExamples = cloneExampleSentences(form.exampleSentences);
            built.push({
                ...item,
                id: `${item.id}:${form.form}`,
                studyType: 'verb-forms',
                cardId: `verb-form:${item.id}:${form.form}`,
                term: form.term || item.term,
                reading: form.readingHiragana || item.reading || '',
                readingHiragana: form.readingHiragana || item.readingHiragana || item.reading || '',
                meaning: form.meaning || item.meaning,
                exampleSentences: formExamples.length ? formExamples : fallbackExamples,
                form: form.form || '',
                formLabel: form.label || form.form || '',
                baseVerbTerm: item.term,
                baseVerbReading: baseReading,
                verbForms: companionForms.map((candidate) => ({
                    ...candidate,
                    isCurrent: candidate.form === form.form
                }))
            });
        });
    });

    return built;
}

function normalizeAudioCacheState(value) {
    if (value === 'hit' || value === 'miss') {
        return value;
    }
    return 'unknown';
}

function audioCacheLabel(cacheState = pronunciationCacheState) {
    const normalized = normalizeAudioCacheState(cacheState);
    if (normalized === 'hit') {
        return 'Audio cache: hit';
    }
    if (normalized === 'miss') {
        return 'Audio cache: miss';
    }
    return 'Audio cache: unknown';
}

function flashcardAudioTexts() {
    const texts = [];
    if (currentItem?.term) {
        texts.push({ label: 'word', text: currentItem.term });
    }
    const exampleText = elements.cardExampleJa?.textContent?.trim();
    if (exampleText && !elements.cardExample.hidden) {
        texts.push({ label: 'example', text: exampleText });
    }
    return texts;
}

async function fetchPronunciationCacheStatus(texts) {
    const response = await fetch('/api/tts/voicevox/cache-status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            texts: texts.map((item) => item.text),
            speaker: selectedDockerSpeaker()
        })
    });

    if (!response.ok) {
        let message = `Audio cache status failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            if (payload.error) {
                message = payload.error;
            }
        } catch (error) {
            // Keep the HTTP status fallback.
        }
        throw new Error(message);
    }

    return response.json();
}

async function refreshPronunciationCacheStatus() {
    const texts = flashcardAudioTexts();
    const runId = pronunciationCacheStatusRun + 1;
    pronunciationCacheStatusRun = runId;
    if (!texts.length) {
        elements.pronunciationStatus.textContent = 'Audio cache: no pronunciation targets.';
        return;
    }
    elements.pronunciationStatus.textContent = 'Audio cache: checking...';
    try {
        const payload = await fetchPronunciationCacheStatus(texts);
        if (runId !== pronunciationCacheStatusRun) {
            return;
        }
        const statusByLabel = texts.map((item, index) => {
            const result = payload.results?.[index];
            return `${item.label} ${result?.cached ? 'cached' : 'not cached'}`;
        });
        elements.pronunciationStatus.textContent = `Audio cache: ${statusByLabel.join(', ')}.`;
    } catch (error) {
        if (runId === pronunciationCacheStatusRun) {
            elements.pronunciationStatus.textContent = error.message;
        }
    }
}

function usesIosAudioGate() {
    const userAgent = navigator.userAgent || '';
    const platform = navigator.platform || '';
    return /iPad|iPhone|iPod/.test(userAgent)
        || (platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function selectedDockerSpeaker() {
    try {
        const value = Number(window.localStorage.getItem(dockerSpeakerPreferenceKey));
        return Number.isInteger(value) ? value : defaultDockerSpeaker;
    } catch (error) {
        return defaultDockerSpeaker;
    }
}

async function fetchProgress() {
    const response = await fetch(flashcardProgressUrl, { cache: 'no-store' });
    if (!response.ok) {
        progressServerAvailable = false;
        return { cards: [], reviews: [] };
    }

    progressServerAvailable = true;
    const payload = await response.json();
    return {
        cards: Array.isArray(payload.cards) ? payload.cards : [],
        reviews: Array.isArray(payload.reviews) ? payload.reviews : []
    };
}

async function updateProgress(operation, payload = {}) {
    if (!progressServerAvailable) {
        updateProgressStorageStatus();
        return { ok: false, cards: [], reviews: [] };
    }

    const response = await fetch(flashcardProgressUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ operation, ...payload })
    });

    if (!response.ok) {
        progressServerAvailable = false;
        updateProgressStorageStatus();
        return { ok: false, cards: [], reviews: [] };
    }

    progressServerAvailable = true;
    return response.json();
}

async function getAllRecords(storeName) {
    const progress = await fetchProgress();
    return progress[storeName] || [];
}

function legacyRequestToPromise(request) {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function legacyDatabaseExists() {
    if (!indexedDB.databases) {
        return true;
    }

    const databases = await indexedDB.databases();
    return databases.some((database) => database.name === legacyDbName);
}

async function loadLegacyBrowserProgress() {
    if (!('indexedDB' in window) || !(await legacyDatabaseExists())) {
        return { cards: [], reviews: [] };
    }

    const db = await legacyRequestToPromise(indexedDB.open(legacyDbName));
    try {
        const stores = Array.from(db.objectStoreNames || []);
        const readStore = async (storeName) => {
            if (!stores.includes(storeName)) {
                return [];
            }
            const transaction = db.transaction(storeName, 'readonly');
            return legacyRequestToPromise(transaction.objectStore(storeName).getAll());
        };
        const [cards, reviews] = await Promise.all([readStore('cards'), readStore('reviews')]);
        return { cards, reviews };
    } finally {
        db.close();
    }
}

async function putRecord(storeName, value) {
    return updateProgress('put', { store: storeName, record: value });
}

async function addRecord(storeName, value) {
    return updateProgress('add', { store: storeName, record: value });
}

async function replaceProgress(cards, reviews) {
    return updateProgress('replace', { cards, reviews });
}

async function resetStoredProgress() {
    return updateProgress('reset');
}

function defaultCardForItem(item) {
    return {
        card_id: cardIdForItem(item),
        vocab_id: item.id,
        card_type: item.studyType || 'recognition',
        level: item.level,
        shown_count: 0,
        remembered_count: 0,
        forgot_count: 0,
        last_shown_at: null,
        last_answered_at: null,
        due_at: null,
        interval_days: 0,
        ease_factor: 2.5,
        next_example_index: 0,
        state: 'new',
        suspended: false
    };
}

function cardForItem(item) {
    return progressByCardId.get(cardIdForItem(item)) || defaultCardForItem(item);
}

function renderVerbForms(item) {
    const forms = Array.isArray(item.verbForms) ? item.verbForms : [];
    if (!forms.length) {
        elements.cardVerbForms.hidden = true;
        elements.cardVerbForms.replaceChildren();
        return;
    }

    elements.cardVerbForms.replaceChildren(
        ...forms.map((form) => {
            const chip = document.createElement('span');
            chip.className = form.isCurrent ? 'verb-form-chip is-current' : 'verb-form-chip';

            const label = document.createElement('span');
            label.className = 'verb-form-chip-label';
            label.textContent = form.label || form.form || 'Form';

            const term = document.createElement('span');
            term.className = 'verb-form-chip-term';
            term.textContent = form.term || '';

            chip.append(label, term);
            if (form.readingHiragana) {
                const reading = document.createElement('span');
                reading.className = 'verb-form-chip-reading';
                reading.textContent = form.readingHiragana;
                chip.append(reading);
            }
            return chip;
        })
    );
    elements.cardVerbForms.hidden = false;
}

function updateProgressStorageStatus() {
    if (!elements.progressStorageStatus) {
        return;
    }

    if (!progressServerAvailable) {
        elements.progressStorageStatus.textContent = 'Server progress endpoint unavailable. Restart the local server to save progress.';
        return;
    }

    const savedCount = progressByCardId.size;
    const visibleCount = studyItems.filter((item) => progressByCardId.has(cardIdForItem(item))).length;
    const olderCount = Math.max(0, savedCount - visibleCount);
    elements.progressStorageStatus.textContent = olderCount
        ? `Progress is stored on the local server with ${visibleCount} active cards and ${olderCount} older records.`
        : `Progress is stored on the local server with ${visibleCount} saved cards.`;
}

function exampleSentencesForItem(item) {
    return Array.isArray(item.exampleSentences)
        ? item.exampleSentences.filter((example) => example?.ja && example?.en)
        : [];
}

function exampleIndexForCard(card, exampleCount) {
    if (!exampleCount) {
        return 0;
    }
    const index = Number(card.next_example_index || 0);
    return Number.isInteger(index) && index >= 0 ? index % exampleCount : 0;
}

function renderExampleSentence(item, card) {
    const examples = exampleSentencesForItem(item);
    if (!examples.length) {
        elements.cardExample.hidden = true;
        elements.cardExampleJa.textContent = '';
        elements.cardExampleEn.textContent = '';
        elements.cardExampleCount.textContent = '';
        return card;
    }

    const index = exampleIndexForCard(card, examples.length);
    const example = examples[index];
    elements.cardExample.hidden = false;
    elements.cardExampleJa.textContent = example.ja;
    elements.cardExampleEn.textContent = example.en;
    elements.cardExampleCount.textContent = `${index + 1}/${examples.length}`;

    return {
        ...card,
        next_example_index: (index + 1) % examples.length
    };
}

function isDue(card, now = Date.now()) {
    return !card.due_at || Date.parse(card.due_at) <= now;
}

function selectedLevel() {
    return elements.levelFilter?.value || 'all';
}

function selectedStudyMode() {
    return elements.studyModeFilter?.value || 'all';
}

function selectedVerbForm() {
    return elements.verbFormFilter?.value || 'all';
}

function filterItems() {
    const level = selectedLevel();
    const studyMode = selectedStudyMode();
    const verbForm = selectedVerbForm();
    const dueOnly = Boolean(elements.dueOnly?.checked);
    const now = Date.now();

    visibleItems = studyItems.filter((item) => {
        if (level !== 'all' && item.level !== level) {
            return false;
        }

        if (studyMode !== 'all' && item.studyType !== studyMode) {
            return false;
        }

        if (verbForm !== 'all' && item.studyType === 'verb-forms' && item.form !== verbForm) {
            return false;
        }

        if (verbForm !== 'all' && item.studyType !== 'verb-forms') {
            return false;
        }

        const card = cardForItem(item);
        if (card.suspended) {
            return false;
        }

        return !dueOnly || isDue(card, now);
    });
}

function randomItem(items) {
    return items[Math.floor(Math.random() * items.length)];
}

function pickNextItem() {
    const excludedCardId = skippedCardId || previousCardId;
    const candidates = excludedCardId && visibleItems.length > 1
        ? visibleItems.filter((item) => cardIdForItem(item) !== excludedCardId)
        : visibleItems;
    return randomItem(candidates.length ? candidates : visibleItems);
}

function aggregateStats() {
    const level = selectedLevel();
    const studyMode = selectedStudyMode();
    const verbForm = selectedVerbForm();
    const matchingItems = studyItems.filter((item) => {
        if (level !== 'all' && item.level !== level) {
            return false;
        }
        if (studyMode !== 'all' && item.studyType !== studyMode) {
            return false;
        }
        if (verbForm !== 'all' && item.studyType === 'verb-forms' && item.form !== verbForm) {
            return false;
        }
        if (verbForm !== 'all' && item.studyType !== 'verb-forms') {
            return false;
        }
        return true;
    });
    const now = Date.now();
    const totals = {
        cards: matchingItems.length,
        due: 0,
        shown: 0,
        remembered: 0,
        forgot: 0
    };

    matchingItems.forEach((item) => {
        const card = cardForItem(item);
        if (isDue(card, now)) {
            totals.due += 1;
        }
        totals.shown += card.shown_count || 0;
        totals.remembered += card.remembered_count || 0;
        totals.forgot += card.forgot_count || 0;
    });

    return totals;
}

function updateStats() {
    const totals = aggregateStats();
    const answered = totals.remembered + totals.forgot;
    const recall = answered > 0 ? Math.round((totals.remembered / answered) * 100) : 0;

    elements.total.textContent = String(totals.cards);
    elements.due.textContent = String(totals.due);
    elements.shown.textContent = String(totals.shown);
    elements.remembered.textContent = String(totals.remembered);
    elements.forgot.textContent = String(totals.forgot);
    elements.streak.textContent = `${recall}%`;
}

function hideAnswer() {
    answerRevealed = false;
    elements.cardMeaning.hidden = true;
    elements.answerLabel.hidden = true;
    elements.reveal.disabled = false;
    elements.remember.disabled = true;
    elements.forgotButton.disabled = true;
}

function revealAnswer() {
    if (!currentItem) {
        return;
    }

    answerRevealed = true;
    elements.cardMeaning.hidden = false;
    elements.answerLabel.hidden = false;
    elements.reveal.disabled = true;
    elements.remember.disabled = false;
    elements.forgotButton.disabled = false;
}

function setEmptyState(isEmpty) {
    elements.emptyState.hidden = !isEmpty;
    elements.flashcard.hidden = isEmpty;
    elements.reveal.disabled = isEmpty;
    elements.skip.disabled = isEmpty;
    elements.pronounceWord.disabled = isEmpty;
    elements.pronounceExample.disabled = isEmpty;
    elements.remember.disabled = true;
    elements.forgotButton.disabled = true;
    if (isEmpty) {
        elements.cardVerbForms.hidden = true;
        elements.cardVerbForms.replaceChildren();
        elements.cardBaseVerb.hidden = true;
        elements.cardBaseVerb.textContent = '';
    }
}

async function showItem(item) {
    currentItem = item;
    currentCard = { ...cardForItem(item) };
    currentCard = renderExampleSentence(item, currentCard);
    currentCard.shown_count = (currentCard.shown_count || 0) + 1;
    currentCard.last_shown_at = new Date().toISOString();
    progressByCardId.set(currentCard.card_id, currentCard);
    await putRecord('cards', currentCard);

    elements.cardLevel.textContent = item.level;
    const sourceLabel = item.sourceLabel || item.sourceTitle || 'Vocabulary';
    elements.cardSource.textContent = item.studyType === 'verb-forms'
        ? `${sourceLabel} · Verb forms`
        : sourceLabel;
    elements.cardTerm.textContent = item.term;
    elements.cardReading.textContent = item.readingHiragana || item.reading || '';
    elements.cardMeaning.textContent = item.meaning;
    if (item.studyType === 'verb-forms' && item.formLabel) {
        elements.cardForm.hidden = false;
        elements.cardForm.textContent = item.formLabel;
    } else {
        elements.cardForm.hidden = true;
        elements.cardForm.textContent = '';
    }
    if (item.studyType === 'verb-forms' && item.baseVerbTerm) {
        const baseReading = item.baseVerbReading ? ` · ${item.baseVerbReading}` : '';
        elements.cardBaseVerb.hidden = false;
        elements.cardBaseVerb.textContent = `Base verb: ${item.baseVerbTerm}${baseReading}`;
    } else {
        elements.cardBaseVerb.hidden = true;
        elements.cardBaseVerb.textContent = '';
    }
    renderVerbForms(item);

    if (item.sourceHref) {
        elements.sourceLink.href = item.sourceHref;
        elements.sourceLink.hidden = false;
    } else {
        elements.sourceLink.hidden = true;
    }

    hideAnswer();
    elements.pronounceWord.disabled = false;
    elements.pronounceExample.disabled = elements.cardExample.hidden;
    pronunciationCacheState = 'unknown';
    elements.pronunciationStatus.textContent = 'Audio cache: checking...';
    refreshPronunciationCacheStatus();
    updateStats();
    updateProgressStorageStatus();
}

function revokeActivePronunciationUrl() {
    if (!activePronunciationUrl) {
        return;
    }
    URL.revokeObjectURL(activePronunciationUrl);
    activePronunciationUrl = null;
}

function clearPreparedPronunciation() {
    preparedPronunciation = null;
}

async function unlockPronunciationAudio() {
    if (!elements.audio || pronunciationAudioUnlocked) {
        return true;
    }

    const previousSrc = elements.audio.getAttribute('src');
    const previousMuted = elements.audio.muted;
    let unlocked = false;

    try {
        elements.audio.muted = true;
        elements.audio.src = silentAudioDataUrl;
        elements.audio.load();
        await elements.audio.play();
        elements.audio.pause();
        pronunciationAudioUnlocked = true;
        unlocked = true;
    } catch (error) {
        // The caller will show a concise browser-specific message.
    } finally {
        elements.audio.muted = previousMuted;
        if (previousSrc) {
            elements.audio.src = previousSrc;
        } else {
            elements.audio.removeAttribute('src');
        }
        elements.audio.load();
    }

    return unlocked;
}

async function fetchPronunciationAudio(text) {
    const response = await fetch('/api/tts/voicevox', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            text,
            speaker: selectedDockerSpeaker()
        })
    });

    if (!response.ok) {
        let message = `Docker TTS request failed with HTTP ${response.status}.`;
        try {
            const payload = await response.json();
            if (payload.error) {
                message = payload.error;
            }
        } catch (error) {
            // Keep the HTTP status fallback.
        }
        throw new Error(message);
    }

    pronunciationCacheState = normalizeAudioCacheState(response.headers.get('X-Audio-Cache'));
    const blob = await response.blob();
    return { blob, cacheState: pronunciationCacheState };
}

function setPronunciationButtonsDisabled(disabled) {
    elements.pronounceWord.disabled = disabled || !currentItem;
    elements.pronounceExample.disabled = disabled || !currentItem || elements.cardExample.hidden;
}

async function playPronunciation(text, label, key) {
    if (!currentItem || !elements.audio || !text) {
        return;
    }

    if (usesIosAudioGate()) {
        const preparedMatches = preparedPronunciation?.key === key
            && preparedPronunciation?.speaker === selectedDockerSpeaker();
        if (!preparedMatches) {
            setPronunciationButtonsDisabled(true);
            elements.pronunciationStatus.textContent = `Preparing ${label} pronunciation for Safari...`;
            try {
                preparedPronunciation = {
                    key,
                    speaker: selectedDockerSpeaker(),
                    audio: await fetchPronunciationAudio(text)
                };
                elements.pronunciationStatus.textContent = `${label} pronunciation is ready. Tap the speaker again. ${audioCacheLabel(preparedPronunciation.audio.cacheState)}.`;
            } catch (error) {
                clearPreparedPronunciation();
                elements.pronunciationStatus.textContent = error.message;
            } finally {
                setPronunciationButtonsDisabled(false);
            }
            return;
        }
    } else {
        const audioReady = await unlockPronunciationAudio();
        if (!audioReady) {
            elements.pronunciationStatus.textContent = 'Browser blocked audio startup. Tap Pronounce again directly in the page.';
            return;
        }
    }

    setPronunciationButtonsDisabled(true);
    elements.pronunciationStatus.textContent = usesIosAudioGate()
        ? `Playing ${label} pronunciation...`
        : `Generating ${label} pronunciation...`;
    try {
        const audio = preparedPronunciation?.key === key
            ? preparedPronunciation.audio
            : await fetchPronunciationAudio(text);
        pronunciationCacheState = normalizeAudioCacheState(audio?.cacheState);
        clearPreparedPronunciation();
        revokeActivePronunciationUrl();
        activePronunciationUrl = URL.createObjectURL(audio.blob);
        elements.audio.src = activePronunciationUrl;
        elements.audio.onended = () => {
            setPronunciationButtonsDisabled(false);
            elements.pronunciationStatus.textContent = '';
        };
        elements.audio.onerror = () => {
            setPronunciationButtonsDisabled(false);
            elements.pronunciationStatus.textContent = 'Docker pronunciation playback failed.';
        };
        elements.pronunciationStatus.textContent = `Playing ${label}. ${audioCacheLabel()}.`;
        await elements.audio.play();
    } catch (error) {
        setPronunciationButtonsDisabled(false);
        elements.pronunciationStatus.textContent = error.message;
    }
}

async function playCurrentWordPronunciation() {
    await playPronunciation(currentItem?.term, 'word', `${currentItem?.id}:word`);
}

async function playCurrentExamplePronunciation() {
    await playPronunciation(
        elements.cardExampleJa.textContent,
        'example',
        `${currentItem?.id}:example:${elements.cardExampleJa.textContent}`
    );
}

async function showNextCard() {
    filterItems();
    updateStats();

    if (!visibleItems.length) {
        currentItem = null;
        currentCard = null;
        setEmptyState(true);
        elements.cardLevel.textContent = selectedLevel() === 'all' ? 'All' : selectedLevel();
        elements.cardSource.textContent = selectedStudyMode() === 'verb-forms' ? 'No verb-form cards due' : 'No cards due';
        elements.cardTerm.textContent = selectedStudyMode() === 'verb-forms' ? 'No verb-form cards' : 'No cards';
        elements.cardReading.textContent = '';
        elements.cardMeaning.textContent = '';
        elements.cardForm.hidden = true;
        elements.cardForm.textContent = '';
        elements.cardBaseVerb.hidden = true;
        elements.cardBaseVerb.textContent = '';
        elements.cardExample.hidden = true;
        elements.cardExampleJa.textContent = '';
        elements.cardExampleEn.textContent = '';
        elements.cardExampleCount.textContent = '';
        elements.pronounceWord.disabled = true;
        elements.pronounceExample.disabled = true;
        return;
    }

    setEmptyState(false);
    const nextItem = pickNextItem();
    skippedCardId = null;
    previousCardId = cardIdForItem(nextItem);
    await showItem(nextItem);
}

function nextScheduleForAnswer(card, answer) {
    const now = Date.now();
    const previousInterval = Number(card.interval_days || 0);
    const previousEase = Number(card.ease_factor || 2.5);

    if (answer === 'remembered') {
        const nextInterval = previousInterval <= 0
            ? 1
            : previousInterval === 1
                ? 3
                : Math.max(1, Math.round(previousInterval * previousEase));
        const easeFactor = Math.min(3.2, previousEase + 0.08);
        return {
            due_at: new Date(now + nextInterval * oneDayMs).toISOString(),
            interval_days: nextInterval,
            ease_factor: easeFactor,
            state: 'review'
        };
    }

    return {
        due_at: new Date(now + 10 * 60 * 1000).toISOString(),
        interval_days: 0,
        ease_factor: Math.max(1.3, previousEase - 0.2),
        state: 'learning'
    };
}

async function answerCurrentCard(answer) {
    if (!currentItem || !currentCard) {
        return;
    }

    const previous = { ...currentCard };
    const schedule = nextScheduleForAnswer(currentCard, answer);
    const answeredAt = new Date().toISOString();
    const updatedCard = {
        ...currentCard,
        ...schedule,
        last_answered_at: answeredAt,
        remembered_count: (currentCard.remembered_count || 0) + (answer === 'remembered' ? 1 : 0),
        forgot_count: (currentCard.forgot_count || 0) + (answer === 'forgot' ? 1 : 0)
    };

    const review = {
        id: `${updatedCard.card_id}:${Date.now()}:${Math.random().toString(16).slice(2)}`,
        card_id: updatedCard.card_id,
        vocab_id: updatedCard.vocab_id,
        level: updatedCard.level,
        answer,
        shown_at: previous.last_shown_at,
        answered_at: answeredAt,
        previous_due_at: previous.due_at,
        next_due_at: updatedCard.due_at,
        previous_interval_days: previous.interval_days || 0,
        next_interval_days: updatedCard.interval_days || 0,
        previous_ease_factor: previous.ease_factor || 2.5,
        next_ease_factor: updatedCard.ease_factor || 2.5
    };

    progressByCardId.set(updatedCard.card_id, updatedCard);
    await putRecord('cards', updatedCard);
    await addRecord('reviews', review);
    skippedCardId = updatedCard.card_id;
    await showNextCard();
}

async function loadProgress() {
    const progress = await fetchProgress();
    let cards = progress.cards;
    let reviews = progress.reviews;
    if (!cards.length && !reviews.length) {
        const legacyProgress = await loadLegacyBrowserProgress();
        if (legacyProgress.cards.length || legacyProgress.reviews.length) {
            await replaceProgress(legacyProgress.cards, legacyProgress.reviews);
            cards = legacyProgress.cards;
            reviews = legacyProgress.reviews;
        }
    }
    progressByCardId = new Map(cards.map((card) => [card.card_id, card]));
    updateProgressStorageStatus();
}

async function loadManifest() {
    const response = await fetch(flashcardManifestUrl);
    if (!response.ok) {
        throw new Error(`Could not load flashcards: ${response.status}`);
    }
    manifest = await response.json();
    manifest.items = Array.isArray(manifest.items) ? manifest.items : [];
    studyItems = buildStudyItems(manifest.items);
    updateProgressStorageStatus();
}

async function exportProgress() {
    const [cards, reviews] = await Promise.all([
        getAllRecords('cards'),
        getAllRecords('reviews')
    ]);
    const payload = {
        schemaVersion: 2,
        exportedAt: new Date().toISOString(),
        cards,
        reviews
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'learn-japanese-flashcards-progress.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

async function importProgress(file) {
    if (!file) {
        return;
    }

    const text = await file.text();
    const payload = JSON.parse(text);
    const cards = Array.isArray(payload.cards) ? payload.cards : [];
    const reviews = Array.isArray(payload.reviews) ? payload.reviews : [];

    await replaceProgress(cards, reviews);
    await loadProgress();
    await showNextCard();
    updateProgressStorageStatus();
}

async function resetProgress() {
    const confirmed = window.confirm('Reset all flashcard progress on the local server?');
    if (!confirmed) {
        return;
    }

    await resetStoredProgress();
    progressByCardId = new Map();
    await showNextCard();
    updateProgressStorageStatus();
}

function bindEvents() {
    elements.levelFilter.addEventListener('change', showNextCard);
    elements.studyModeFilter.addEventListener('change', showNextCard);
    elements.verbFormFilter.addEventListener('change', showNextCard);
    elements.dueOnly.addEventListener('change', showNextCard);
    elements.flashcard.addEventListener('click', revealAnswer);
    elements.flashcard.addEventListener('keydown', (event) => {
        if ((event.key === 'Enter' || event.key === ' ') && !answerRevealed) {
            event.preventDefault();
            revealAnswer();
        }
    });
    elements.pronounceWord.addEventListener('click', (event) => {
        event.stopPropagation();
        playCurrentWordPronunciation().catch(showError);
    });
    elements.pronounceExample.addEventListener('click', (event) => {
        event.stopPropagation();
        playCurrentExamplePronunciation().catch(showError);
    });
    elements.reveal.addEventListener('click', revealAnswer);
    elements.remember.addEventListener('click', () => answerCurrentCard('remembered'));
    elements.forgotButton.addEventListener('click', () => answerCurrentCard('forgot'));
    elements.skip.addEventListener('click', () => {
        skippedCardId = currentCard?.card_id || null;
        showNextCard().catch(showError);
    });
    elements.exportProgress.addEventListener('click', exportProgress);
    elements.importProgress.addEventListener('change', (event) => {
        importProgress(event.target.files?.[0]).catch(showError);
        event.target.value = '';
    });
    elements.resetProgress.addEventListener('click', () => {
        resetProgress().catch(showError);
    });

    document.addEventListener('keydown', (event) => {
        if (!currentItem) {
            return;
        }
        if (event.target.closest?.('button, input, select, textarea, a')) {
            return;
        }
        if (event.key === ' ' && !answerRevealed) {
            event.preventDefault();
            revealAnswer();
        } else if (event.key === '1' && answerRevealed) {
            answerCurrentCard('remembered').catch(showError);
        } else if (event.key === '2' && answerRevealed) {
            answerCurrentCard('forgot').catch(showError);
        }
    });
}

function showError(error) {
    console.error(error);
    setEmptyState(true);
    elements.emptyState.hidden = false;
    elements.emptyState.textContent = error.message || 'Flashcards could not load.';
    elements.cardSource.textContent = 'Error';
    elements.cardTerm.textContent = 'Flashcards unavailable';
}

async function init() {
    bindEvents();
    await loadManifest();
    await loadProgress();
    await showNextCard();
}

init().catch(showError);
