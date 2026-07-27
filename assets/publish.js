const articlesEndpoint = '/api/articles';
const agentEndpoint = '/api/articles/agent';

const state = {
    backupUrl: '/api/articles/backup',
    selectedArticleId: '',
    runtimeArticles: []
};

const elements = {
    brief: document.getElementById('article-brief-input'),
    publish: document.getElementById('publish-article'),
    clearBrief: document.getElementById('clear-brief'),
    status: document.getElementById('publish-status'),
    contentDir: document.getElementById('content-dir'),
    articleCount: document.getElementById('article-count'),
    editingTarget: document.getElementById('editing-target'),
    runtimeArticles: document.getElementById('runtime-articles'),
    downloadBackup: document.getElementById('download-backup'),
    copyContentDir: document.getElementById('copy-content-dir')
};

function setStatus(message, tone = 'default') {
    elements.status.textContent = message;
    elements.status.classList.toggle('is-error', tone === 'error');
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
}

async function copyText(text, label) {
    await navigator.clipboard.writeText(text);
    setStatus(`${label} copied.`);
}

function setEditingState(article = null) {
    state.selectedArticleId = article?.id || '';
    elements.editingTarget.textContent = article
        ? `Revising runtime article ${article.id}`
        : 'Creating a new runtime article';
    elements.publish.textContent = article ? 'Revise & Publish' : 'Draft & Publish';
}

function articleActionsHtml(article) {
    return [
        `<button class="list-button" type="button" data-action="revise" data-article-id="${escapeHtml(article.id)}">Revise</button>`,
        `<button class="list-button is-danger" type="button" data-action="delete" data-article-id="${escapeHtml(article.id)}">Delete</button>`
    ].join('');
}

function articleItemHtml(article) {
    return `<li class="article-card">
        <div class="article-card-copy">
            <a href="${escapeHtml(article.href)}"><strong>${escapeHtml(article.navLabel)}</strong><span>${escapeHtml(article.title)}</span><br><span>Runtime · ${escapeHtml(article.file)}</span></a>
        </div>
        <div class="article-card-actions">${articleActionsHtml(article)}</div>
    </li>`;
}

async function loadRuntimeArticles() {
    const response = await fetch(articlesEndpoint, { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Runtime article list failed with HTTP ${response.status}.`);
    }
    const payload = await response.json();
    state.backupUrl = payload.backup_url || state.backupUrl;
    state.runtimeArticles = Array.isArray(payload.articles)
        ? payload.articles.filter((article) => article.runtime)
        : [];
    elements.contentDir.textContent = payload.content_dir || 'Unavailable';
    elements.articleCount.textContent = String(payload.runtime_count ?? state.runtimeArticles.length);
    elements.runtimeArticles.innerHTML = state.runtimeArticles.length
        ? state.runtimeArticles.map(articleItemHtml).join('')
        : '<li class="meta-item">No runtime-published articles yet.</li>';
}

async function publishWithAgent() {
    const brief = elements.brief.value.trim();
    if (!brief) {
        setStatus('Describe the article you want Codex to create.', 'error');
        return;
    }
    elements.publish.disabled = true;
    elements.clearBrief.disabled = true;
    setStatus('Codex is researching, drafting, validating, and publishing the article. This can take a few minutes.');
    try {
        const response = await fetch(agentEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief, article_id: state.selectedArticleId || undefined })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || `Codex publish failed with HTTP ${response.status}.`);
        }
        const article = payload.article || {};
        setStatus(`Published ${article.id || 'runtime article'}${article.href ? ` — ${article.href}` : ''}`);
        elements.brief.value = '';
        setEditingState();
        await loadRuntimeArticles();
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        elements.publish.disabled = false;
        elements.clearBrief.disabled = false;
    }
}

function reviseRuntimeArticle(articleId) {
    const article = state.runtimeArticles.find((item) => item.id === articleId);
    if (!article) {
        throw new Error('That runtime article is no longer available. Refresh and try again.');
    }
    setEditingState(article);
    elements.brief.value = `Revise ${article.title}: `;
    elements.brief.focus();
    setStatus(`Tell Codex what to change in ${article.id}. Its existing article details will be provided automatically.`);
}

async function deleteRuntimeArticle(articleId) {
    if (!window.confirm(`Delete runtime article ${articleId}? This removes its stored runtime file.`)) {
        return;
    }
    setStatus(`Deleting ${articleId}...`);
    const response = await fetch(`${articlesEndpoint}?article_id=${encodeURIComponent(articleId)}`, { method: 'DELETE' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Delete failed with HTTP ${response.status}.`);
    }
    if (state.selectedArticleId === articleId) {
        elements.brief.value = '';
        setEditingState();
    }
    setStatus(`Deleted ${articleId}.`);
    await loadRuntimeArticles();
}

async function handleRuntimeArticleAction(event) {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    button.disabled = true;
    try {
        if (button.dataset.action === 'revise') {
            reviseRuntimeArticle(button.dataset.articleId);
        } else if (button.dataset.action === 'delete') {
            await deleteRuntimeArticle(button.dataset.articleId);
        }
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        button.disabled = false;
    }
}

elements.publish.addEventListener('click', publishWithAgent);
elements.clearBrief.addEventListener('click', () => {
    elements.brief.value = '';
    setEditingState();
    setStatus('Brief cleared.');
});
elements.downloadBackup.addEventListener('click', () => {
    window.location.href = state.backupUrl;
    setStatus('Backup download started.');
});
elements.copyContentDir.addEventListener('click', () => copyText(elements.contentDir.textContent, 'Content directory').catch((error) => setStatus(error.message, 'error')));
elements.runtimeArticles.addEventListener('click', handleRuntimeArticleAction);

loadRuntimeArticles().catch((error) => {
    setStatus(error.message, 'error');
    elements.contentDir.textContent = 'Unavailable';
    elements.articleCount.textContent = 'Unavailable';
});
