# HLS website

This directory is the complete shared-hosting document root. It requires PHP
8.3 and Apache; there is no build step or package installation.

For local rendering without managing the user's application server:

```console
php -S 127.0.0.1:8080 -t website
```

Deploy the contents of `website/`, including `.htaccess`, directly into the
site's configured remote document root. The page uses Google Fonts for Space
Mono and IBM Plex Mono; Apache's content security policy permits only those
font resources in addition to same-origin assets.

The page derives its canonical URL from the validated request host and exposes
Open Graph and Twitter large-image metadata for `assets/social-preview.jpg`.
The existing hook mark is provided as SVG and 32-pixel PNG favicons, a
multi-size root `favicon.ico`, and a 180-pixel Apple touch icon.
