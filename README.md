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
`/api/blob-upload` is a small Node/Vercel Blob token endpoint, while
`/api/library` is handled by the Flask function in `api/index.py`. The browser
sends the actual `.daff` bytes directly to Vercel Blob.

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

## Upload architecture and limits

- **Large-file uploads:** the browser uploads `.daff` bytes directly to
  Vercel Blob using a short-lived client-upload token from
  `/api/blob-upload`. The file therefore does **not** pass through the
  Vercel Function request-body limit.
- **Metadata:** after Blob confirms the upload, the browser sends only small
  JSON metadata to `POST /api/library`. The Flask API never receives the file
  bytes.
- **Client-side validation:** the library page still parses the DAFF header
  before allowing an upload. Blob tokens also restrict uploads to `.daff`
  paths, DAFF content types, and a 5 GiB maximum object size.
- **"Unlisted" isn't access control.** There's no login system here, so a
  `private`/unlisted entry just means it's excluded from the public
  `/api/library` listing. The Blob object itself is public, so anyone with
  its direct URL can open it.
- **Blob store:** create a Vercel Blob store connected to this project.
  Vercel supplies `BLOB_READ_WRITE_TOKEN` (or the newer OIDC-backed
  authentication) to the server-side Blob SDK.
- **Dependency:** the project now includes `@vercel/blob` 2.4.x for the
  token endpoint. The static library page loads the matching client module
  from esm.sh.

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
