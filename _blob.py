"""
_blob.py - minimal client for the Vercel Blob REST API.

Stores the actual .daff file bytes. There's no official first-party
Python SDK for Vercel Blob (it's a JS/TS product), so this talks to the
REST API directly with `requests`. Needs one environment variable, set
automatically when you create a Blob store from your Vercel project:
    BLOB_READ_WRITE_TOKEN

Reference: https://vercel.com/docs/vercel-blob
"""

import os
import requests

_API_URL = "https://blob.vercel-storage.com"
_API_VERSION = "4"
_TOKEN_ENV = "BLOB_READ_WRITE_TOKEN"


def _token():
    token = os.environ.get(_TOKEN_ENV, "")
    if not token:
        raise RuntimeError(f"{_TOKEN_ENV} is not set")
    return token


def delete(url: str):
    headers = {
        "authorization": f"Bearer {_token()}",
        "x-api-version": _API_VERSION,
        "content-type": "application/json",
    }
    resp = requests.post(f"{_API_URL}/delete", json={"urls": [url]}, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Vercel Blob delete failed ({resp.status_code}): {resp.text}")
    return resp.json()
