<?php
declare(strict_types=1);

$version = '0.8.26.3';
$repository = 'https://github.com/ediril/hook-line-sync';
$year = (int) date('Y');

function h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#080b10">
    <meta name="description" content="HLS adds project mapping, readable diffs, and deliberate pushes to a simple FTPS workflow.">
    <title>Hook Line Sync — a better way to just FTP it</title>
    <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&amp;family=Space+Mono:wght@400;700&amp;display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/site.css">
    <script src="assets/site.js" defer></script>
</head>
<body>
    <a class="skip-link" href="#main">Skip to content</a>

    <header class="site-header" data-header>
        <a class="brand" href="#top" aria-label="Hook Line Sync home">
            <svg class="brand-mark" viewBox="0 0 48 48" aria-hidden="true">
                <path d="M14 7v24a10 10 0 0 0 20 0V20" />
                <path d="m29 25 5-5 5 5" />
                <circle cx="14" cy="7" r="3" />
            </svg>
            <span>hook<span>/</span>line<span>/</span>sync</span>
        </a>

        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle>
            <span></span><span></span>
            <span class="sr-only">Toggle navigation</span>
        </button>

        <nav class="site-nav" id="site-nav" aria-label="Primary navigation" data-nav>
            <a href="#workflow">Workflow</a>
            <a href="#principles">Safety</a>
            <a class="nav-cta" href="<?= h($repository) ?>">GitHub <span aria-hidden="true">↗</span></a>
        </nav>
    </header>

    <main id="main">
        <section class="hero" id="top">
            <div class="hero-copy">
                <p class="eyebrow"><span class="signal"></span> PRE-ALPHA // v<?= h($version) ?></p>
                <h1>A better way to<br><span>“just FTP it.”</span></h1>
                <p class="hero-lede">
                    Map your local project once. Preview the diff. Push exactly what
                    you intend to shared hosting over FTPS.
                </p>

                <div class="hero-actions">
                    <div class="install-command" aria-label="Installation command">
                        <span aria-hidden="true">$</span>
                        <code>pip install hook-line-sync</code>
                        <button type="button" data-copy="pip install hook-line-sync">
                            <span data-copy-label>copy</span>
                        </button>
                    </div>
                    <a class="text-link" href="#workflow">See the workflow <span aria-hidden="true">↓</span></a>
                </div>

                <div class="hero-meta" aria-label="Project metadata">
                    <div><span class="meta-label">transport</span><span class="meta-value">FTPS / explicit TLS</span></div>
                    <div><span class="meta-label">runtime</span><span class="meta-value">Python 3.10+</span></div>
                    <div><span class="meta-label">license</span><span class="meta-value">MIT</span></div>
                </div>
            </div>

            <div class="terminal-wrap" aria-label="Example HLS terminal session">
                <div class="terminal-glow"></div>
                <div class="terminal">
                    <div class="terminal-bar">
                        <div class="terminal-dots" aria-hidden="true"><i></i><i></i><i></i></div>
                        <span>~/sites/discovery — hls</span>
                        <span class="terminal-state">TLS:ON</span>
                    </div>
                    <div class="terminal-body">
                        <p><span class="prompt">❯</span> <b>hls diff -r --all</b></p>
                        <p class="muted">Checking differences for project 'discovery'...</p>
                        <p class="muted">Comparing directory '.'...</p>
                        <p class="terminal-heading">Local -&gt; Remote for project 'discovery':</p>
                        <p><span class="added">+</span> &nbsp; index.php</p>
                        <p><span class="changed">~</span> &nbsp; assets/site.css</p>
                        <p><span class="added">+</span> <span class="directory">d assets/icons</span></p>
                        <p class="excluded"><span>x</span> <span class="directory-dark">d vendor</span></p>
                        <p class="remote-only"><span>r</span> &nbsp; legacy.php</p>
                        <p class="terminal-gap"><span class="prompt">❯</span> <b>hls push -r</b></p>
                        <p><span class="success">✓</span> Push completed: 3 changes.</p>
                        <span class="cursor" aria-hidden="true"></span>
                    </div>
                </div>
                <span class="coordinate coordinate-a">41.8781° N</span>
                <span class="coordinate coordinate-b">SYNC_CHANNEL_01</span>
            </div>
        </section>

        <section class="ticker" aria-label="Product attributes">
            <div>
                <span>MAP ONCE</span><i>◆</i><span>DIFF FIRST</span><i>◆</i>
                <span>PUSH FILES</span><i>◆</i><span>PRUNE EXPLICITLY</span><i>◆</i>
                <span>MAP ONCE</span><i>◆</i><span>DIFF FIRST</span><i>◆</i>
            </div>
        </section>

        <section class="section workflow" id="workflow">
            <div class="section-heading">
                <p class="eyebrow">01 // THE LOOP</p>
                <h2>Map it once. Check the diff. Push.</h2>
                <p>HLS remembers where the project lives locally and remotely, then shows what will change before any files move.</p>
            </div>

            <ol class="workflow-grid">
                <li>
                    <span class="step-number">01</span>
                    <div class="step-icon" aria-hidden="true">⌖</div>
                    <h3>Map the project</h3>
                    <p>Connect the current local directory to its remote root. HLS recognizes that project from any directory beneath it.</p>
                    <code>hls add prod --host …</code>
                </li>
                <li>
                    <span class="step-number">02</span>
                    <div class="step-icon" aria-hidden="true">⌁</div>
                    <h3>Exclude what doesn’t belong</h3>
                    <p>Exclude files that should never leave your machine. Use an explicit pattern when future matching files should stay excluded too.</p>
                    <code>hls exc --pattern '*.map'</code>
                </li>
                <li>
                    <span class="step-number">03</span>
                    <div class="step-icon" aria-hidden="true">∆</div>
                    <h3>Read the diff</h3>
                    <p>Compare local and remote files before changing either side. Add <code>--all</code> when you also want unchanged and excluded paths.</p>
                    <code>hls diff -r</code>
                </li>
                <li>
                    <span class="step-number">04</span>
                    <div class="step-icon" aria-hidden="true">↥</div>
                    <h3>Push the changes</h3>
                    <p>Upload new and modified files. Remote-only files stay untouched unless you explicitly enable pruning.</p>
                    <code>hls push -r</code>
                </li>
            </ol>
        </section>

        <section class="section principles" id="principles">
            <div class="section-heading split-heading">
                <div>
                    <p class="eyebrow">02 // DESIGN SIGNAL</p>
                    <h2>Safer than manual FTP.<br>Lighter than a deployment stack.</h2>
                </div>
                <p>HLS keeps the familiar FTPS server you already have, while adding the project context, change preview, and deletion safeguards manual uploads are missing.</p>
            </div>

            <div class="principle-grid">
                <article class="principle principle-wide">
                    <span class="principle-index">A</span>
                    <div>
                        <h3>Local files drive the sync</h3>
                        <p>The remote is treated as a deployment target. A file missing locally is reported instead of being copied back unexpectedly.</p>
                    </div>
                    <div class="mini-diff" aria-hidden="true">
                        <span class="added">+</span><i></i><b>new</b>
                        <span class="changed">~</span><i></i><b>changed</b>
                        <span class="remote-only">r</span><i></i><b>remote-only / kept</b>
                        <span class="removed">-</span><i></i><b>pruned with -p</b>
                    </div>
                </article>
                <article class="principle">
                    <span class="principle-index">B</span>
                    <h3>Remote deletion is opt-in</h3>
                    <p>Remote-only paths are reported and preserved unless you explicitly run push with <code>-p</code>.</p>
                </article>
                <article class="principle">
                    <span class="principle-index">C</span>
                    <h3>Path rules stay readable</h3>
                    <p>Quoted and unquoted wildcards select the same existing files. <code>--pattern</code> clearly marks rules that should match future files.</p>
                </article>
                <article class="principle principle-accent">
                    <span class="principle-index">D</span>
                    <h3>Verified FTPS connections</h3>
                    <p>HLS verifies certificates, protects the data channel, and uses structured server listings over explicit TLS.</p>
                    <svg viewBox="0 0 160 80" aria-hidden="true"><path d="M4 60h34l15-36 28 46 19-30 14 20h42" /></svg>
                </article>
            </div>
        </section>

        <section class="section support" id="support">
            <div class="support-panel">
                <div>
                    <p class="eyebrow">03 // OPEN SOURCE</p>
                    <h2>Free to use.<br>Worth supporting.</h2>
                </div>
                <div class="support-copy">
                    <p>HLS is MIT licensed for personal and commercial work. A voluntary Business subscription is planned for teams that want help configuring HLS, reviewing a deployment setup, troubleshooting server compatibility, or triaging a reproducible defect.</p>
                    <div class="support-actions">
                        <a class="button-primary" href="<?= h($repository) ?>">View on GitHub <span aria-hidden="true">↗</span></a>
                        <a class="text-link" href="<?= h($repository) ?>/blob/main/LICENSE">Read the license</a>
                    </div>
                </div>
                <div class="support-orbit" aria-hidden="true"><i></i><i></i><span>HLS</span></div>
            </div>
        </section>
    </main>

    <footer class="site-footer">
        <a class="brand footer-brand" href="#top">hook<span>/</span>line<span>/</span>sync</a>
        <p>Built for the narrow gap between “just FTP it” and deployment infrastructure.</p>
        <p>© <?= h((string) $year) ?> HLS contributors // MIT</p>
    </footer>
</body>
</html>
