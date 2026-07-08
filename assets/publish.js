const publishEndpoint = '/api/articles';
const articlesEndpoint = '/api/articles';

const authorPrompt = `Write one article JSON object for the learn-japanese runtime CMS.

Requirements:
- Return one JSON object only. No markdown fences.
- Use the same schema as data/articles/*.json.
- id must look like YYYY-MM-DD-slug.
- file must end in .html and start with the same date as id.
- Include title, titleTranslation, date, month, navLabel, level, downloadFileName, headlineHtml, sourceNote, paragraphs, vocabularyTitle, and vocabulary.
- paragraphs must contain exactly 5 objects.
- Each paragraph html should contain 1-3 Japanese sentences.
- Total visible body text across the 5 paragraph html fields must be 450-500 characters, excluding ruby tags.
- Keep each sentence comfortably under 500 characters.
- vocabulary must be an array of objects with term and meaning.
- Use ruby markup in headlineHtml and paragraph html where helpful for learners.`;

const sampleArticle = {
    _comment: 'Publish rules for new runtime articles: exactly 5 sections in paragraphs, each section must have 1-3 sentences, and the visible body text across those 5 sections must total 450-500 characters. Also keep each individual sentence comfortably under 500 characters so TTS and video rendering stay reliable.',
    id: '2026-07-09-sample-article',
    file: '2026-07-09-sample-article.html',
    title: 'サンプル記事',
    titleTranslation: 'Sample Article',
    date: '2026年7月9日',
    month: 'July 2026',
    navLabel: '7/9 サンプル',
    level: 'N3',
    downloadFileName: '2026-07-09-sample-article.mp4',
    headlineHtml: '<ruby>公開<rt>こうかい</rt></ruby>ページの<ruby>サンプル記事<rt>さんぷるきじ</rt></ruby>',
    sourceNote: 'Sample payload for the publish UI.',
    paragraphs: [
        {
            html: '<ruby>一<rt>ひと</rt></ruby>つ<ruby>目<rt>め</rt></ruby>の<ruby>段落<rt>だんらく</rt></ruby>です。<ruby>形式<rt>けいしき</rt></ruby>を<ruby>見<rt>み</rt></ruby>せるために、<ruby>短<rt>みじか</rt></ruby>すぎない<ruby>文<rt>ぶん</rt></ruby>を<ruby>入<rt>い</rt></ruby>れています。<ruby>公開<rt>こうかい</rt></ruby>の<ruby>検証<rt>けんしょう</rt></ruby>に<ruby>必要<rt>ひつよう</rt></ruby>な<ruby>長<rt>なが</rt></ruby>さもここで<ruby>少<rt>すこ</rt></ruby>しずつ<ruby>確保<rt>かくほ</rt></ruby>し、<ruby>全体<rt>ぜんたい</rt></ruby>の<ruby>形<rt>かたち</rt></ruby>も<ruby>分<rt>わ</rt></ruby>かりやすく<ruby>見<rt>み</rt></ruby>えるようにします。',
            translation: 'This is the first section. It includes text that is not too short so the format is easy to see. It also helps satisfy the length needed for publishing checks.'
        },
        {
            html: '<ruby>二<rt>ふた</rt></ruby>つ<ruby>目<rt>め</rt></ruby>の<ruby>段落<rt>だんらく</rt></ruby>です。<ruby>各段落<rt>かくだんらく</rt></ruby>は<ruby>一<rt>ひと</rt></ruby>つから<ruby>三<rt>みっ</rt></ruby>つまでの<ruby>文<rt>ぶん</rt></ruby>で<ruby>作<rt>つく</rt></ruby>ります。<ruby>英訳<rt>えいやく</rt></ruby>は<ruby>必要<rt>ひつよう</rt></ruby>なら translation に<ruby>入<rt>い</rt></ruby>れ、<ruby>読<rt>よ</rt></ruby>み<ruby>手<rt>て</rt></ruby>が<ruby>意味<rt>いみ</rt></ruby>を<ruby>確認<rt>かくにん</rt></ruby>しやすいように<ruby>後<rt>あと</rt></ruby>から<ruby>足<rt>た</rt></ruby>せます。',
            translation: 'This is the second section. Each section should contain one to three sentences. If needed, the English translation goes in translation and can be added later.'
        },
        {
            html: '<ruby>三<rt>みっ</rt></ruby>つ<ruby>目<rt>め</rt></ruby>では、html に<ruby>本文<rt>ほんぶん</rt></ruby>の ruby <ruby>付<rt>つ</rt></ruby>き<ruby>文字<rt>もじ</rt></ruby>を<ruby>入<rt>い</rt></ruby>れます。<ruby>見出<rt>みだ</rt></ruby>しは headlineHtml、<ruby>本文<rt>ほんぶん</rt></ruby>は paragraphs の html です。vocabulary には<ruby>単語<rt>たんご</rt></ruby>と<ruby>意味<rt>いみ</rt></ruby>を<ruby>入<rt>い</rt></ruby>れ、<ruby>最低限<rt>さいていげん</rt></ruby>の<ruby>語彙欄<rt>ごいらん</rt></ruby>も<ruby>示<rt>しめ</rt></ruby>しておきます。',
            translation: 'In the third section, html contains the ruby-marked body text. The headline uses headlineHtml, the body uses the paragraph html fields, and vocabulary holds terms and meanings.'
        },
        {
            html: '<ruby>四<rt>よっ</rt></ruby>つ<ruby>目<rt>め</rt></ruby>の<ruby>段落<rt>だんらく</rt></ruby>も<ruby>同<rt>おな</rt></ruby>じ<ruby>形<rt>かたち</rt></ruby>です。<ruby>公開前<rt>こうかいまえ</rt></ruby>の validator は<ruby>段落数<rt>だんらくすう</rt></ruby>、<ruby>文数<rt>ぶんすう</rt></ruby>、そして<ruby>全体<rt>ぜんたい</rt></ruby>の<ruby>長<rt>なが</rt></ruby>さを<ruby>見<rt>み</rt></ruby>ます。だから sample もその<ruby>条件<rt>じょうけん</rt></ruby>に<ruby>合<rt>あ</rt></ruby>わせてあり、<ruby>貼<rt>は</rt></ruby>り<ruby>付<rt>つ</rt></ruby>け<ruby>用<rt>よう</rt></ruby>の<ruby>土台<rt>どだい</rt></ruby>としてそのまますぐ<ruby>安心<rt>あんしん</rt></ruby>して<ruby>使<rt>つか</rt></ruby>えます。',
            translation: 'The fourth section keeps the same structure. The validator checks section count, sentence count, and total length, so the sample already matches those rules.'
        },
        {
            html: '<ruby>五<rt>いつ</rt></ruby>つ<ruby>目<rt>め</rt></ruby>の<ruby>段落<rt>だんらく</rt></ruby>です。<ruby>内容<rt>ないよう</rt></ruby>は<ruby>簡単<rt>かんたん</rt></ruby>でかまいませんが、<ruby>形式<rt>けいしき</rt></ruby>はそのまま<ruby>真似<rt>まね</rt></ruby>できます。この sample は<ruby>必要最小限<rt>ひつようさいしょうげん</rt></ruby>の<ruby>基本形<rt>きほんけい</rt></ruby>だけを<ruby>示<rt>しめ</rt></ruby>しつつ、<ruby>公開条件<rt>こうかいじょうけん</rt></ruby>も<ruby>無理<rt>むり</rt></ruby>なく<ruby>満<rt>み</rt></ruby>たすものなので、<ruby>必要<rt>ひつよう</rt></ruby>な<ruby>所<rt>ところ</rt></ruby>だけ<ruby>少<rt>すこ</rt></ruby>し<ruby>書<rt>か</rt></ruby>き<ruby>換<rt>か</rt></ruby>えれば<ruby>使<rt>つか</rt></ruby>えます。',
            translation: 'The fifth section shows a minimal base format. It still satisfies the publish rules, so you can edit only the parts you need and use it directly.'
        }
    ],
    vocabularyTitle: 'N3 Vocabulary',
    vocabulary: [
        {
            term: '形式（けいしき）',
            meaning: 'Format'
        }
    ]
};

const state = {
    backupUrl: '/api/articles/backup',
    loadedArticleId: '',
    loadedArticleFile: '',
    runtimeArticles: []
};

const elements = {
    input: document.getElementById('article-json-input'),
    publish: document.getElementById('publish-article'),
    format: document.getElementById('format-json'),
    loadSample: document.getElementById('load-sample'),
    copyPrompt: document.getElementById('copy-prompt'),
    copySampleJson: document.getElementById('copy-sample-json'),
    downloadBackup: document.getElementById('download-backup'),
    copyContentDir: document.getElementById('copy-content-dir'),
    clearEditor: document.getElementById('clear-editor'),
    status: document.getElementById('publish-status'),
    contentDir: document.getElementById('content-dir'),
    articleCount: document.getElementById('article-count'),
    editingTarget: document.getElementById('editing-target'),
    runtimeArticles: document.getElementById('runtime-articles')
};

function setStatus(message, tone = 'default') {
    elements.status.textContent = message;
    elements.status.classList.toggle('is-error', tone === 'error');
}

function formatJson(value) {
    return JSON.stringify(value, null, 2);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

async function copyText(text, label) {
    await navigator.clipboard.writeText(text);
    setStatus(`${label} copied.`);
}

function setEditingState(article = null) {
    state.loadedArticleId = article?.id || '';
    state.loadedArticleFile = article?.file || '';
    elements.editingTarget.textContent = article
        ? `Editing runtime article ${article.id}`
        : 'Editing a new runtime article';
}

function parseEditorJson() {
    const raw = elements.input.value.trim();
    if (!raw) {
        throw new Error('Paste an article JSON object first.');
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('The pasted value must be a JSON object.');
    }
    return parsed;
}

function articleActionsHtml(article) {
    return [
        `<button class="list-button" type="button" data-action="edit" data-article-id="${escapeHtml(article.id)}">Edit</button>`,
        `<button class="list-button" type="button" data-action="copy" data-article-id="${escapeHtml(article.id)}">Copy JSON</button>`,
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

async function fetchRuntimeArticle(articleId) {
    const response = await fetch(`${articlesEndpoint}?article_id=${encodeURIComponent(articleId)}`, {
        cache: 'no-store'
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Article load failed with HTTP ${response.status}.`);
    }
    return payload.article;
}

async function loadRuntimeArticle(articleId, announce = true) {
    const article = await fetchRuntimeArticle(articleId);
    elements.input.value = formatJson(article);
    setEditingState(article);
    if (announce) {
        setStatus(`Loaded ${article.id} from runtime storage.`);
    }
    return article;
}

async function publishArticle() {
    let article;
    try {
        article = parseEditorJson();
    } catch (error) {
        setStatus(error.message, 'error');
        return;
    }

    const overwrite = Boolean(state.loadedArticleId) && (
        state.loadedArticleId === article.id || state.loadedArticleFile === article.file
    );

    elements.publish.disabled = true;
    setStatus(overwrite ? 'Saving runtime article...' : 'Publishing runtime article...');

    try {
        const response = await fetch(publishEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ article, overwrite })
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || `Publish failed with HTTP ${response.status}.`);
        }

        elements.input.value = formatJson(article);
        setEditingState(article);
        setStatus(`${overwrite ? 'Saved' : 'Published'} ${payload.article?.id || article.id}\n${payload.article?.json_path || ''}`);
        await loadRuntimeArticles();
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        elements.publish.disabled = false;
    }
}

function loadSampleArticle() {
    elements.input.value = formatJson(sampleArticle);
    setEditingState();
    setStatus('Sample article loaded into the editor.');
}

function clearEditor() {
    elements.input.value = '';
    setEditingState();
    setStatus('Editor cleared.');
}

function formatEditorJson() {
    try {
        elements.input.value = formatJson(parseEditorJson());
        setStatus('JSON formatted.');
    } catch (error) {
        setStatus(error.message, 'error');
    }
}

async function deleteRuntimeArticle(articleId) {
    const confirmed = window.confirm(`Delete runtime article ${articleId}? This removes its JSON file from the runtime content store.`);
    if (!confirmed) {
        return;
    }

    setStatus(`Deleting ${articleId}...`);
    const response = await fetch(`${articlesEndpoint}?article_id=${encodeURIComponent(articleId)}`, {
        method: 'DELETE'
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Delete failed with HTTP ${response.status}.`);
    }

    if (state.loadedArticleId === articleId) {
        setEditingState();
    }
    setStatus(`Deleted ${articleId}.`);
    await loadRuntimeArticles();
}

async function handleRuntimeArticleAction(event) {
    const button = event.target.closest('[data-action]');
    if (!button) {
        return;
    }

    const action = button.dataset.action;
    const articleId = button.dataset.articleId;
    if (!action || !articleId) {
        return;
    }

    button.disabled = true;
    try {
        if (action === 'edit') {
            await loadRuntimeArticle(articleId);
        } else if (action === 'copy') {
            const article = await fetchRuntimeArticle(articleId);
            await copyText(formatJson(article), `${articleId} JSON`);
        } else if (action === 'delete') {
            await deleteRuntimeArticle(articleId);
        }
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        button.disabled = false;
    }
}

function downloadBackup() {
    window.location.href = state.backupUrl;
    setStatus('Backup download started.');
}

elements.publish.addEventListener('click', publishArticle);
elements.loadSample.addEventListener('click', loadSampleArticle);
elements.format.addEventListener('click', formatEditorJson);
elements.copyPrompt.addEventListener('click', () => copyText(authorPrompt, 'Prompt').catch((error) => {
    setStatus(error.message, 'error');
}));
elements.copySampleJson.addEventListener('click', () => copyText(formatJson(sampleArticle), 'Sample JSON').catch((error) => {
    setStatus(error.message, 'error');
}));
elements.downloadBackup.addEventListener('click', downloadBackup);
elements.copyContentDir.addEventListener('click', () => copyText(elements.contentDir.textContent, 'Content directory').catch((error) => {
    setStatus(error.message, 'error');
}));
elements.clearEditor.addEventListener('click', clearEditor);
elements.runtimeArticles.addEventListener('click', (event) => {
    handleRuntimeArticleAction(event);
});

loadSampleArticle();
loadRuntimeArticles().catch((error) => {
    setStatus(error.message, 'error');
    elements.contentDir.textContent = 'Unavailable';
    elements.articleCount.textContent = 'Unavailable';
});
