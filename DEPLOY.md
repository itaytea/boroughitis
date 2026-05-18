# Deploying Boroughitis

The site is fully static (no backend, no build step), so deploy is just
"copy these files to a web host." Cloudflare Pages is the cleanest free
option: unlimited bandwidth, fast global CDN, free custom domains, auto-
deploys on git push.

## One-time setup (~10 minutes)

### 1. Create a GitHub repo

If you don't have GitHub set up:
- Sign up at <https://github.com> (free)
- Install the GitHub Desktop app, or use the CLI:

```bash
# from the project folder
git init
git add .
git commit -m "initial boroughitis"
```

Then create an empty repo on github.com (call it `boroughitis`) and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/boroughitis.git
git branch -M main
git push -u origin main
```

### 2. Connect Cloudflare Pages

- Go to <https://dash.cloudflare.com/> (sign up if needed — free)
- Sidebar → **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**
- Authorize GitHub, pick the `boroughitis` repo
- On the build config screen:
  - **Framework preset:** None
  - **Build command:** *(leave blank)*
  - **Build output directory:** `/`
  - **Root directory:** *(leave blank)*
- Click **Save and Deploy**

Within ~30 seconds you get a URL like `boroughitis-abc.pages.dev`. That's it.

### 3. Custom domain (optional)

In the Pages project → **Custom domains** → **Set up a custom domain** →
type yours (e.g. `boroughitis.com`) → follow DNS instructions. If you bought
the domain through Cloudflare, it's two clicks. Other registrars need a
single CNAME record.

## Updating the site

Every time you push to `main`, Cloudflare rebuilds and deploys automatically:

```bash
git add .
git commit -m "add new munis to schedule"
git push
```

Live in ~30 seconds.

## What gets shipped

The `.gitignore` excludes the things you don't want public:
- `scripts/_cache/` (downloaded TIGER zips and Census responses)
- `.venv/` (your Python virtualenv)
- `__pycache__/`, `.DS_Store`, etc.

What's left in the repo: `index.html`, `styles.css`, `game.js`, `data/`,
`scripts/build_data.py`, `README.md`, `SETUP.md`, `DEPLOY.md`. All
shippable. Total deployed size: ~2-3 MB (mostly the 564 SVG outlines).

## Other hosts

If you ever want to switch:

- **Netlify Drop** (<https://app.netlify.com/drop>) — drag the project
  folder, get a URL in 30 seconds. No git needed.
- **Vercel** — run `npx vercel` from the project root.
- **GitHub Pages** — free, slightly more configuration, ties URL to your
  GitHub username.

All three are interchangeable for a static site like this.
