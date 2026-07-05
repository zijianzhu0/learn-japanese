const themePreferenceKey = 'learnJapanese.theme';

function storedThemePreference() {
    try {
        const value = window.localStorage.getItem(themePreferenceKey);
        return value === 'dark' || value === 'light' ? value : null;
    } catch (error) {
        return null;
    }
}

function preferredTheme() {
    const stored = storedThemePreference();
    if (stored) {
        return stored;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function themeIcon(theme) {
    if (theme === 'dark') {
        return '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"></path></svg>';
    }
    return '<svg class="nav-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2.5v2.5"></path><path d="M12 19v2.5"></path><path d="m4.9 4.9 1.8 1.8"></path><path d="m17.3 17.3 1.8 1.8"></path><path d="M2.5 12H5"></path><path d="M19 12h2.5"></path><path d="m4.9 19.1 1.8-1.8"></path><path d="m17.3 6.7 1.8-1.8"></path></svg>';
}

function applyTheme(theme, persist = false) {
    const resolvedTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;

    if (persist) {
        try {
            window.localStorage.setItem(themePreferenceKey, resolvedTheme);
        } catch (error) {
            // Ignore storage failures so the UI still works.
        }
    }

    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
        const nextTheme = resolvedTheme === 'dark' ? 'light' : 'dark';
        const label = resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        button.dataset.nextTheme = nextTheme;
        button.setAttribute('aria-label', label);
        button.setAttribute('title', label);
        button.setAttribute('aria-pressed', String(resolvedTheme === 'dark'));
        button.innerHTML = `${themeIcon(resolvedTheme)}<span class="icon-label">${label}</span>`;
    });
}

function initializeThemeToggle() {
    applyTheme(preferredTheme(), false);

    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
        if (button.dataset.themeToggleReady === 'true') {
            return;
        }
        button.dataset.themeToggleReady = 'true';
        button.addEventListener('click', () => {
            applyTheme(button.dataset.nextTheme, true);
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeThemeToggle, { once: true });
} else {
    initializeThemeToggle();
}
