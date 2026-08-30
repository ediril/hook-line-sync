<?php
declare(strict_types=1);

$version = '0.8.30.7';
$repository = 'https://github.com/ediril/hook-line-sync';
$year = (int) date('Y');
$title = 'Hook Line Sync — a better way to "just FTP it"';
$description = 'Map your local project once. Preview the diff. Push exactly what you intend to shared hosting over FTPS.';
$requestHost = (string) ($_SERVER['HTTP_HOST'] ?? '');
$validHost = preg_match('/\A[a-z0-9.-]+(?::[0-9]+)?\z/i', $requestHost) === 1;
$forwardedProtocol = strtolower((string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? ''));
$secureRequest = (
    strtolower((string) ($_SERVER['HTTPS'] ?? '')) === 'on'
    || $forwardedProtocol === 'https'
);
$requestPath = parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH);
$pagePath = is_string($requestPath) && str_starts_with($requestPath, '/')
    ? $requestPath
    : '/';
$origin = $validHost
    ? ($secureRequest ? 'https://' : 'http://') . $requestHost
    : null;
$canonicalUrl = $origin === null ? null : $origin . $pagePath;
$socialImageUrl = $origin === null
    ? null
    : $origin . '/assets/social-preview.jpg';
$structuredData = [
    '@context' => 'https://schema.org',
    '@type' => 'SoftwareApplication',
    'name' => 'Hook Line Sync',
    'alternateName' => 'HLSync',
    'description' => $description,
    'applicationCategory' => 'DeveloperApplication',
    'operatingSystem' => 'Any operating system with Python 3.10+',
    'softwareVersion' => $version,
    'url' => $canonicalUrl ?? $repository,
    'downloadUrl' => 'https://pypi.org/project/hook-line-sync/',
    'sameAs' => $repository,
    'license' => 'https://opensource.org/license/mit',
    'offers' => [
        '@type' => 'Offer',
        'price' => '0',
        'priceCurrency' => 'USD',
    ],
];
if ($socialImageUrl !== null) {
    $structuredData['image'] = $socialImageUrl;
}
$structuredDataJson = json_encode(
    $structuredData,
    JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
        | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
);
if ($structuredDataJson === false) {
    throw new RuntimeException('Could not encode website structured data.');
}

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
    <meta name="description" content="<?= h($description) ?>">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <meta name="author" content="Hook Line Sync contributors">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="en_US">
    <meta property="og:site_name" content="Hook Line Sync">
    <meta property="og:title" content="<?= h($title) ?>">
    <meta property="og:description" content="<?= h($description) ?>">
<?php if ($canonicalUrl !== null && $socialImageUrl !== null): ?>
    <link rel="canonical" href="<?= h($canonicalUrl) ?>">
    <meta property="og:url" content="<?= h($canonicalUrl) ?>">
    <meta property="og:image" content="<?= h($socialImageUrl) ?>">
<?php if ($secureRequest): ?>
    <meta property="og:image:secure_url" content="<?= h($socialImageUrl) ?>">
<?php endif; ?>
<?php endif; ?>
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="Hook Line Sync terminal workflow: diff local files, then push over FTPS.">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?= h($title) ?>">
    <meta name="twitter:description" content="<?= h($description) ?>">
<?php if ($socialImageUrl !== null): ?>
    <meta name="twitter:image" content="<?= h($socialImageUrl) ?>">
    <meta name="twitter:image:alt" content="Hook Line Sync terminal workflow: diff local files, then push over FTPS.">
<?php endif; ?>
    <script type="application/ld+json"><?= $structuredDataJson ?></script>
    <title><?= h($title) ?></title>
    <link rel="describedby" href="/llms.txt" type="text/markdown">
    <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
    <link rel="icon" href="assets/favicon-32x32.png" type="image/png" sizes="32x32">
    <link rel="shortcut icon" href="favicon.ico">
    <link rel="apple-touch-icon" href="assets/apple-touch-icon.png" sizes="180x180">
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
                        <span>~/sites/discovery — hlsync</span>
                        <span class="terminal-state">TLS:ON</span>
                    </div>
                    <div class="terminal-body">
                        <p><span class="prompt">❯</span> <b>hlsync diff -r</b></p>
                        <p class="muted">Checking differences for profile 'discovery'...</p>
                        <p><span class="directory">&nbsp; assets/</span></p>
                        <p><span class="added">+</span> &nbsp; index.php</p>
                        <p><span class="removed">-</span> &nbsp; legacy.php</p>
                        <p>&nbsp; <span class="changed">~</span> &nbsp; site.css</p>
                        <p>&nbsp; <span class="added">+</span> <span class="directory">icons/</span></p>
                        <p class="terminal-gap"><span class="prompt">❯</span> <b>hlsync push</b></p>
                        <p class="muted">Pushing changes...</p>
                        <p>&nbsp; Adding&nbsp;&nbsp;&nbsp;index.php</p>
                        <p>&nbsp; Updating site.css</p>
                        <p>&nbsp; Creating icons/</p>
                        <p>&nbsp; Deleting&nbsp; legacy.php</p>
                        <p><span class="success">✓</span> Push complete: 4 changes.</p>
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
                    <code>hlsync create prod --host …</code>
                </li>
                <li>
                    <span class="step-number">02</span>
                    <div class="step-icon" aria-hidden="true">⌁</div>
                    <h3>Exclude what doesn’t belong</h3>
                    <p>Exclude files that should never leave your machine. Use an explicit pattern when future matching files should stay excluded too.</p>
                    <code>hlsync exc --pattern '*.map'</code>
                </li>
                <li>
                    <span class="step-number">03</span>
                    <div class="step-icon" aria-hidden="true">∆</div>
                    <h3>Read the diff</h3>
                    <p>Compare local and remote files before changing either side. Routine output stays focused on paths that differ; <code>--all</code> reveals the complete comparison.</p>
                    <code>hlsync diff -r</code>
                </li>
                <li>
                    <span class="step-number">04</span>
                    <div class="step-icon" aria-hidden="true">↥</div>
                    <h3>Push the changes</h3>
                    <p>Upload new and modified files, then remove remote-only files in the selected scope. Use <code>-k</code> when remote-only files should stay.</p>
                    <code>hlsync push</code>
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
                        <span class="removed">-</span><i></i><b>remote-only / deleted</b>
                        <span class="remote-only">r</span><i></i><b>kept with -k</b>
                    </div>
                </article>
                <article class="principle">
                    <span class="principle-index">B</span>
                    <h3>Push matches local state</h3>
                    <p>Remote-only paths in the selected scope are deleted after uploads succeed. Use <code>-k</code> when they should be retained.</p>
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
