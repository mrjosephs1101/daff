# DAFF — full-stack site (Vercel-ready)

A landing page plus three tools — **Player**, **Converter**, and a
**Library** with a real shared database — deployable to Vercel.

## Why this needs two external services

Vercel Functions are stateless: they don't have a persistent local disk,
and different invocations can run on different machines. So the two
things the library needs to persist can't just live on the function's
own filesystem the way the earlier local version did:

| What                         | Where it lives here                          |
|------------------------------|-----------------------------------------------|
| Library metadata (a real SQLite database) | **Turso** — hosted SQLite, reachable over HTTP |
| The actual `.daff` file bytes | **Vercel Blob** — Vercel's own object storage |

Both have free tiers and take a couple of minutes to set up.

## 1. Create a Turso database

1. Sign up at [turso.tech](https://turso.tech) (or `curl -sSfL https://get.tur.so/install.sh | bash` for the CLI).
2. `turso db create daff-library`
3. `turso db show daff-library --url` → this is your `TURSO_DATABASE_URL`
4. `turso db tokens create daff-library` → this is your `TURSO_AUTH_TOKEN`

You don't need to create any tables by hand — the app runs
`CREATE TABLE IF NOT EXISTS` itself on first use.

## 2. Create a Vercel Blob store

1. In your Vercel dashboard: **Project → Storage → Create Database → Blob**
2. This automatically adds a `BLOB_READ_WRITE_TOKEN` environment variable
   to your project.

## 3. Set environment variables

In your Vercel project's **Settings → Environment Variables**, make sure
these three are set (Blob's token is added for you in step 2; you add
the two Turso ones yourself):

```
TURSO_DATABASE_URL=libsql://your-db-yourorg.turso.io
TURSO_AUTH_TOKEN=eyJ...
BLOB_READ_WRITE_TOKEN=vercel_blob_rw_...   (added automatically)
```

## 4. Deploy

```
npm i -g vercel
vercel
```

or connect the repo through the Vercel dashboard directly. Either way,
once the env vars above are set, `index.html`, `player.html`,
`converter.html`, and `library.html` are served as static pages, and
`/api/upload` + `/api/library` are handled by the single Flask function
in `api/index.py`.

## Local development

```
pip install -r requirements.txt
export TURSO_DATABASE_URL=...
export TURSO_AUTH_TOKEN=...
export BLOB_READ_WRITE_TOKEN=...
python3 api/index.py
```

This runs just the API on `http://localhost:5000`. To exercise the
actual pages against it locally, either open the HTML files directly and
point their `fetch()` calls at `http://localhost:5000`, or use
`vercel dev` from the project root, which serves both the static files
and the Python function together the way production does.

## Known limits, and how "unlisted" works

- **Upload size**: server-side uploads through a Vercel Function are
  capped at roughly 4.5MB (a platform limit on request bodies, not
  something this code can raise). `api/upload.py` rejects anything over
  4MB with a clear error rather than failing silently. For bigger audio
  files, the real fix is a **client-direct-upload** flow — the browser
  uploads straight to Vercel Blob using a short-lived token, bypassing
  the function entirely. That's a meaningfully bigger chunk of code
  (a token-issuing endpoint plus the client-side handshake Vercel Blob
  expects) and isn't included here; it's the natural next step if 4MB
  turns out to be too small for your files.
- **"Unlisted" isn't access control.** There's no login system here, so
  a `private`/unlisted entry just means it's excluded from the public
  `/api/library` listing — the file itself is stored with public Blob
  access, so anyone who has (or guesses) the direct link can still open
  it. If you need real per-user access control, that requires adding
  authentication, which is out of scope for this build.
- **I couldn't test the Turso/Blob calls against a live account** — the
  Turso HTTP protocol (`_db.py`) is implemented directly from Turso's
  own published API reference, and the Blob client (`_blob.py`) is
  implemented from Vercel Blob's REST API as used internally by a
  community Python wrapper I inspected. Both should be correct, but
  since I don't have real Turso/Blob credentials to test end-to-end
  against, double-check the first upload after you deploy, and check
  each service's current docs if something doesn't match:
  - <https://docs.turso.tech/sdk/http/quickstart>
  - <https://vercel.com/docs/vercel-blob>

## Files

```
index.html         landing page
player.html         plays a .daff file
converter.html      builds a .daff file in-browser
library.html         browses/uploads/downloads shared .daff files
style.css            shared theme for all four pages
api/index.py          Flask app: /api/upload, /api/library
api/_db.py            Turso (SQLite-over-HTTP) client
api/_blob.py          Vercel Blob client
api/daff_format.py    DAFF binary parser (validates uploads server-side)
requirements.txt
vercel.json
```
