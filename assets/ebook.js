const ebookLibraryUrl = './data/ebook-library.json';
const ebookStorageKey = 'learnJapanese.ebookMvp.state';
const epubPageWidth = 1200;
const epubPageHeight = 1800;

let collection = null;
let state = loadState();
let currentArticleIndex = 0;
let currentPageIndex = 0;
let speaking = false;

function loadState() {
    const fallback = { currentArticleId: '', hideFurigana: false, showAllTranslations: true, completedIds: [] };
    try {
        const parsed = JSON.parse(window.localStorage.getItem(ebookStorageKey) || 'null');
        return parsed && typeof parsed === 'object'
            ? { ...fallback, ...parsed, completedIds: Array.isArray(parsed.completedIds) ? parsed.completedIds : [] }
            : fallback;
    } catch (error) {
        return fallback;
    }
}

function saveState() {
    try { window.localStorage.setItem(ebookStorageKey, JSON.stringify(state)); } catch (error) { console.error(error); }
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

function currentArticle() { return collection?.articles?.[currentArticleIndex] || null; }
function isArticleComplete(id) { return state.completedIds.includes(id); }

function paragraphPlainText(html) {
    const element = document.createElement('div');
    element.innerHTML = html;
    element.querySelectorAll('rt, rp').forEach((node) => node.remove());
    return (element.textContent || '').replace(/\s+/g, ' ').trim();
}

function titleClasses(article) {
    const titleLength = paragraphPlainText(article.headlineHtml).replace(/\s/g, '').length;
    const translationLength = (article.titleTranslation || '').length;
    const score = titleLength * 1.9 + translationLength * .55;
    if (score >= 105) return ['article-header article-header--compact', 'article-title article-title--compact'];
    if (score >= 80) return ['article-header article-header--balanced', 'article-title article-title--balanced'];
    return ['article-header', 'article-title'];
}

function vocabularyChunks(article) {
    const vocabulary = article.vocabulary || [];
    const size = Math.max(1, Math.ceil(vocabulary.length / article.paragraphs.length));
    return article.paragraphs.map((_, index) => vocabulary.slice(index * size, (index + 1) * size));
}

function audioCard(label, detail) {
    return `<section class="note-card" aria-label="Audio"><div class="audio-card"><span class="audio-label">▶ ${label}<span>${detail}</span></span><audio class="audio-player" controls preload="none"><p>This page includes embedded audio in the EPUB.</p></audio></div></section>`;
}

function overviewPage(article) {
    const [headerClass, titleClass] = titleClasses(article);
    const paragraphs = article.paragraphs.map((paragraph) => `<section class="jp-only-group paragraph"><p class="jp-copy paragraph-japanese">${paragraph.html}</p></section>`).join('');
    return `<div class="page-wrap"><article class="page"><div class="page__inner"><header class="${headerClass}"><p class="article-meta">Chapter ${currentArticleIndex + 1} · ${escapeHtml(article.date)} · ${escapeHtml(article.level || '')}</p><h1 class="${titleClass}">${article.headlineHtml}</h1><div class="title-rule"></div>${audioCard('Article audio', 'Play the full article')}</header><main class="story-body story-body--overview">${paragraphs}</main></div></article></div>`;
}

function sectionPage(article, paragraph, sectionIndex) {
    const items = vocabularyChunks(article)[sectionIndex] || [];
    const vocabulary = items.length
        ? items.map((item) => `<li><strong>${escapeHtml(item.term)}</strong>: ${escapeHtml(item.meaning)}</li>`).join('')
        : '<li>No vocabulary note on this page.</li>';
    const phrase = state.showAllTranslations
        ? `<p class="phrase-note" lang="en">${escapeHtml(paragraph.translation || '')}</p>`
        : '<p class="phrase-note">Phrase note hidden in this preview.</p>';
    const number = sectionIndex + 1;
    return `<div class="page-wrap"><article class="page"><div class="page__inner"><p class="article-meta">Chapter ${currentArticleIndex + 1} · Section ${number} of ${article.paragraphs.length}</p><main class="story-body story-body--section"><div class="section-shell"><p class="section-label">${escapeHtml(article.title)}</p><section class="section-card"><p class="jp-copy paragraph-japanese">${paragraph.html}</p></section><div class="notes-column"><section class="note-card"><h2>Phrase note</h2>${phrase}</section><section class="note-card"><h2>Vocabulary</h2><ul class="vocabulary-list vocabulary-list--section">${vocabulary}</ul></section>${audioCard('Section audio', 'Play this section only')}</div></div><p class="section-footer">Section ${number} study page</p></main></div></article></div>`;
}

function previewDocument(content) {
    const furiganaStyle = state.hideFurigana ? '<style>rt,rp{display:none!important}</style>' : '';
    return `<!doctype html><html lang="ja"><head><base href="${escapeHtml(location.href)}"><meta charset="utf-8"><link rel="stylesheet" href="./assets/epub-layout.css">${furiganaStyle}</head><body>${content}</body></html>`;
}

function resizePreview() {
    const stage = document.getElementById('epub-preview-stage');
    const frame = document.getElementById('epub-preview');
    if (!stage || !frame) return;
    const scale = Math.min(1, stage.clientWidth / epubPageWidth);
    frame.style.transform = `scale(${scale})`;
    stage.style.height = `${Math.ceil(epubPageHeight * scale)}px`;
}

function renderPreview() {
    const article = currentArticle();
    if (!article) return;
    const select = document.getElementById('preview-page');
    select.innerHTML = ['<option value="0">Overview</option>', ...article.paragraphs.map((_, index) => `<option value="${index + 1}">Section ${index + 1}</option>`)].join('');
    select.value = String(currentPageIndex);
    document.getElementById('preview-title').textContent = currentPageIndex === 0 ? `Chapter ${currentArticleIndex + 1} overview` : `Chapter ${currentArticleIndex + 1}, section ${currentPageIndex}`;
    const content = currentPageIndex === 0 ? overviewPage(article) : sectionPage(article, article.paragraphs[currentPageIndex - 1], currentPageIndex - 1);
    document.getElementById('epub-preview').srcdoc = previewDocument(content);
    resizePreview();
}

function renderBookshelf() {
    const bookshelf = document.getElementById('bookshelf');
    bookshelf.innerHTML = collection.articles.map((item, index) => `<button class="book-card ${item.id === currentArticle()?.id ? 'is-active' : ''} ${isArticleComplete(item.id) ? 'is-complete' : ''}" type="button" data-article-id="${escapeHtml(item.id)}"><span class="book-kicker">Chapter ${index + 1}</span><h3 class="book-title">${escapeHtml(item.title)}</h3><p class="book-translation">${escapeHtml(item.titleTranslation || '')}</p><div class="book-meta"><span class="book-pill">${escapeHtml(item.level || 'Reader')}</span></div><p class="book-status">${isArticleComplete(item.id) ? 'Completed' : 'Open preview'}</p></button>`).join('');
    bookshelf.querySelectorAll('[data-article-id]').forEach((button) => button.addEventListener('click', () => setCurrentArticle(button.dataset.articleId)));
}

function render() {
    const article = currentArticle();
    document.getElementById('collection-title').textContent = collection.title;
    document.getElementById('collection-subtitle').textContent = collection.subtitle;
    document.getElementById('collection-description').textContent = collection.description;
    document.getElementById('article-count').textContent = String(collection.articles.length);
    document.getElementById('estimated-minutes').textContent = `${collection.estimatedMinutes} min`;
    document.getElementById('collection-progress').textContent = `${collection.articles.filter((item) => isArticleComplete(item.id)).length}/${collection.articles.length}`;
    document.getElementById('toggle-furigana').checked = state.hideFurigana;
    document.getElementById('toggle-translations').checked = state.showAllTranslations;
    document.getElementById('complete-button').textContent = isArticleComplete(article.id) ? 'Completed' : 'Mark complete';
    document.getElementById('complete-button').classList.toggle('is-active', isArticleComplete(article.id));
    document.getElementById('previous-button').disabled = currentArticleIndex === 0;
    document.getElementById('next-button').disabled = currentArticleIndex === collection.articles.length - 1;
    renderBookshelf();
    renderPreview();
}

function setCurrentArticle(articleId) {
    const index = collection.articles.findIndex((article) => article.id === articleId);
    if (index < 0) return;
    stopSpeaking();
    currentArticleIndex = index;
    currentPageIndex = 0;
    state.currentArticleId = articleId;
    saveState();
    render();
}

function stopSpeaking() {
    window.speechSynthesis.cancel();
    speaking = false;
    document.getElementById('speak-button').textContent = 'Read preview text';
    document.getElementById('speak-button').classList.remove('is-active');
}

function speakCurrentPage() {
    if (speaking) return stopSpeaking();
    const article = currentArticle();
    const blocks = currentPageIndex === 0 ? [article.headlineHtml, ...article.paragraphs.map((item) => item.html)] : [article.paragraphs[currentPageIndex - 1].html];
    speaking = true;
    const button = document.getElementById('speak-button');
    button.textContent = 'Stop reading';
    button.classList.add('is-active');
    const utterance = new SpeechSynthesisUtterance(blocks.map(paragraphPlainText).join(' '));
    utterance.lang = 'ja-JP';
    utterance.rate = .92;
    utterance.onend = stopSpeaking;
    utterance.onerror = stopSpeaking;
    window.speechSynthesis.speak(utterance);
}

function toggleComplete() {
    const id = currentArticle().id;
    state.completedIds = isArticleComplete(id) ? state.completedIds.filter((item) => item !== id) : [...state.completedIds, id];
    saveState();
    render();
}

async function initialize() {
    try {
        const response = await fetch(ebookLibraryUrl, { cache: 'no-cache' });
        const payload = await response.json();
        collection = payload.collections?.[0];
        if (!collection?.articles?.length) throw new Error('No e-book collection found.');
        currentArticleIndex = Math.max(0, collection.articles.findIndex((item) => item.id === state.currentArticleId));
        state.currentArticleId = currentArticle().id;
        document.getElementById('toggle-furigana').addEventListener('change', (event) => { state.hideFurigana = event.target.checked; saveState(); renderPreview(); });
        document.getElementById('toggle-translations').addEventListener('change', (event) => { state.showAllTranslations = event.target.checked; saveState(); renderPreview(); });
        document.getElementById('preview-page').addEventListener('change', (event) => { currentPageIndex = Number(event.target.value); renderPreview(); });
        document.getElementById('speak-button').addEventListener('click', speakCurrentPage);
        document.getElementById('complete-button').addEventListener('click', toggleComplete);
        document.getElementById('previous-button').addEventListener('click', () => currentArticleIndex > 0 && setCurrentArticle(collection.articles[currentArticleIndex - 1].id));
        document.getElementById('next-button').addEventListener('click', () => currentArticleIndex < collection.articles.length - 1 && setCurrentArticle(collection.articles[currentArticleIndex + 1].id));
        new ResizeObserver(resizePreview).observe(document.getElementById('epub-preview-stage'));
        window.addEventListener('beforeunload', stopSpeaking);
        render();
    } catch (error) {
        console.error(error);
        document.querySelector('.page-shell').innerHTML = `<p>${escapeHtml(error.message)}</p>`;
    }
}

document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', initialize, { once: true }) : initialize();
