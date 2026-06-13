const quizManifestUrl = './data/video-quizzes.json';

let quizzes = [];
let currentQuiz = null;

const elements = {
    quizSelect: document.getElementById('quiz-select'),
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
    footerRight: document.getElementById('stage-footer-right')
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

function renderQuiz(quiz) {
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
        elements.renderVideo.disabled = true;
        elements.status.textContent = 'Rendering 1080x1920 quiz MP4...';
        const response = await fetch('/api/video/render-quiz-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quiz_id: currentQuiz.id })
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
elements.copyComment.addEventListener('click', copyCommentText);
elements.renderVideo.addEventListener('click', renderVideo);

loadQuizzes().catch((error) => {
    elements.status.textContent = error.message;
});
