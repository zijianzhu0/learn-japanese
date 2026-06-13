const quizManifestUrl = './data/video-quizzes.json';
const defaultDockerSpeaker = 9;
const dockerSpeakerPreferenceKey = 'learnJapanese.dockerSpeaker';

let quizzes = [];
let currentQuiz = null;
let activeAudioUrl = null;
let playbackRun = 0;
let playbackActive = false;

const elements = {
    quizSelect: document.getElementById('quiz-select'),
    dockerVoice: document.getElementById('docker-voice'),
    readStory: document.getElementById('read-story'),
    copyComment: document.getElementById('copy-comment'),
    renderVideo: document.getElementById('render-video'),
    status: document.getElementById('status-line'),
    commentText: document.getElementById('comment-text'),
    answerLabel: document.getElementById('answer-label'),
    kicker: document.getElementById('stage-kicker'),
    title: document.getElementById('stage-title'),
    meta: document.getElementById('stage-meta'),
    question: document.getElementById('quiz-question'),
    optionList: document.getElementById('option-list'),
    footerLeft: document.getElementById('stage-footer-left'),
    footerRight: document.getElementById('stage-footer-right'),
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

function optionLetter(index) {
    return String.fromCharCode(65 + index);
}

function buildCommentText(quiz) {
    return quiz.passage
        .map((line) => `${line.jp}\n${line.en}`)
        .join('\n\n');
}

function correctOption(quiz) {
    return quiz.options.find((option) => option.id === quiz.answerId);
}

function selectedSpeaker() {
    const value = Number(elements.dockerVoice?.value);
    return Number.isInteger(value) ? value : defaultDockerSpeaker;
}

function savedSpeaker() {
    try {
        const value = Number(window.localStorage.getItem(dockerSpeakerPreferenceKey));
        return Number.isInteger(value) ? value : defaultDockerSpeaker;
    } catch (error) {
        return defaultDockerSpeaker;
    }
}

function saveSpeaker() {
    try {
        window.localStorage.setItem(dockerSpeakerPreferenceKey, String(selectedSpeaker()));
    } catch (error) {
        // Storage restrictions should not block playback.
    }
}

function renderQuiz(quiz) {
    stopPlayback();
    currentQuiz = quiz;
    const correct = correctOption(quiz);

    elements.kicker.textContent = quiz.kicker;
    elements.title.textContent = quiz.title;
    elements.meta.textContent = quiz.level ? `${quiz.level} · Multiple choice` : 'Multiple choice';
    elements.question.textContent = quiz.question;
    elements.footerLeft.textContent = quiz.footerLeft || 'Read the passage in comments';
    elements.footerRight.textContent = quiz.footerRight || 'A-D';
    elements.answerLabel.textContent = correct ? `Answer: ${correct.label}` : '';
    elements.commentText.value = buildCommentText(quiz);
    elements.optionList.innerHTML = quiz.options.map((option, index) => `
        <li class="option-card">
            <span class="option-letter">${optionLetter(index)}</span>
            <span class="option-text">${escapeHtml(option.label)}</span>
        </li>
    `).join('');
    elements.status.textContent = 'Ready.';
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

function revokeActiveAudioUrl() {
    if (activeAudioUrl) {
        URL.revokeObjectURL(activeAudioUrl);
        activeAudioUrl = null;
    }
}

function stopPlayback() {
    playbackActive = false;
    playbackRun += 1;
    revokeActiveAudioUrl();
    if (elements.audio) {
        elements.audio.pause();
        elements.audio.removeAttribute('src');
        elements.audio.load();
    }
    elements.readStory.querySelector('span').textContent = 'Read Story';
}

function playAudioBlob(blob, runId) {
    return new Promise((resolve, reject) => {
        elements.audio.onended = resolve;
        elements.audio.onerror = () => reject(new Error('Audio playback failed.'));
        revokeActiveAudioUrl();
        activeAudioUrl = URL.createObjectURL(blob);
        elements.audio.src = activeAudioUrl;
        elements.audio.play().catch(reject);
    }).then(() => {
        if (runId !== playbackRun) {
            throw new Error('Playback stopped.');
        }
    });
}

async function readStory() {
    if (!currentQuiz) {
        return;
    }

    if (playbackActive) {
        stopPlayback();
        elements.status.textContent = 'Reading stopped.';
        return;
    }

    const lines = currentQuiz.passage.map((line) => line.jp);
    playbackActive = true;
    const runId = playbackRun + 1;
    playbackRun = runId;
    elements.readStory.querySelector('span').textContent = 'Stop';
    saveSpeaker();

    try {
        for (let index = 0; index < lines.length; index += 1) {
            if (!playbackActive || runId !== playbackRun) {
                throw new Error('Playback stopped.');
            }
            elements.status.textContent = `Generating Japanese TTS ${index + 1}/${lines.length}...`;
            const blob = await fetchLocalTtsAudio(lines[index]);
            elements.status.textContent = `Reading story ${index + 1}/${lines.length}.`;
            await playAudioBlob(blob, runId);
        }
        elements.status.textContent = 'Finished reading story.';
    } catch (error) {
        if (!String(error.message).includes('stopped')) {
            elements.status.textContent = error.message;
        }
    } finally {
        if (runId === playbackRun) {
            playbackActive = false;
            revokeActiveAudioUrl();
            elements.readStory.querySelector('span').textContent = 'Read Story';
        }
    }
}

async function copyCommentText() {
    if (!currentQuiz) {
        return;
    }

    try {
        await navigator.clipboard.writeText(buildCommentText(currentQuiz));
        elements.status.textContent = 'JP/EN comment text copied.';
    } catch (error) {
        elements.commentText.select();
        elements.status.textContent = 'Clipboard copy failed. Text is selected.';
    }
}

async function renderVideo() {
    if (!currentQuiz) {
        return;
    }

    try {
        stopPlayback();
        saveSpeaker();
        elements.renderVideo.disabled = true;
        elements.status.textContent = 'Rendering 1080x1920 quiz MP4 with Japanese TTS...';
        const response = await fetch('/api/video/render-quiz-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quiz_id: currentQuiz.id,
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
        downloadLink.download = payload.filename || 'story-quiz-video.mp4';
        downloadLink.click();
        elements.status.textContent = 'MP4 rendered and downloaded.';
    } catch (error) {
        elements.status.textContent = error.message;
    } finally {
        elements.renderVideo.disabled = false;
    }
}

function populateQuizSelect() {
    elements.quizSelect.innerHTML = quizzes.map((quiz) => (
        `<option value="${escapeHtml(quiz.id)}">${escapeHtml(quiz.title)}</option>`
    )).join('');
}

async function loadQuizzes() {
    const response = await fetch(quizManifestUrl, { cache: 'no-cache' });
    if (!response.ok) {
        throw new Error(`Quiz manifest failed to load with HTTP ${response.status}.`);
    }
    const payload = await response.json();
    quizzes = Array.isArray(payload.quizzes) ? payload.quizzes : [];
    if (!quizzes.length) {
        throw new Error('No quiz stories found.');
    }
    populateQuizSelect();
    renderQuiz(quizzes[0]);
}

elements.quizSelect.addEventListener('change', () => {
    const quiz = quizzes.find((item) => item.id === elements.quizSelect.value);
    if (quiz) {
        renderQuiz(quiz);
    }
});
elements.dockerVoice.addEventListener('change', saveSpeaker);
elements.readStory.addEventListener('click', readStory);
elements.copyComment.addEventListener('click', copyCommentText);
elements.renderVideo.addEventListener('click', renderVideo);

populateVoiceOptions();
loadQuizzes().catch((error) => {
    elements.status.textContent = error.message;
});
