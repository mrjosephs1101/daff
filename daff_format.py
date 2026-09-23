"""
daff_format.py
Reference implementation of the DAFF (Dynamic Audio File Format) container.

Binary layout
-------------
Header (12 bytes):
    0..3   b"DAFF"              magic
    4      uint8                format version (currently 1)
    5..7   b"\\x00\\x00\\x00"   reserved
    8..11  uint32 LE            chunk count

Then `chunk count` chunks, back to back, each:
    0..3   ASCII                chunk type, e.g. b"META"
    4..7   uint32 LE            payload length in bytes
    8..N   bytes                payload

Chunk types
-----------
META  (exactly one) - UTF-8 JSON object describing the file:
        { title, artist, album, duration, audioMime, createdWith, createdAt }

STAG  (exactly one) - UTF-8 JSON array of stage/chapter objects, ordered by
        startTime ascending:
        [ { id, label, startTime, endTime (or null = until the end),
            thumbnailId } , ... ]

THMB  (zero or more) - one per embedded thumbnail image:
        1 byte   idLen
        idLen    id (UTF-8) -- matches a stage's thumbnailId
        1 byte   mimeLen
        mimeLen  mime (UTF-8), e.g. "image/png"
        rest     raw image bytes

AUDI  (exactly one, should be written last since it's the largest chunk) -
        raw audio bytes, whatever `audioMime` in META says it is.

Unknown chunk types are legal and must be skipped by readers (their length
is always known), so the format can grow new chunk types later without
breaking older players.
"""

import json
import struct

MAGIC = b"DAFF"
VERSION = 1

HEADER_STRUCT = struct.Struct("<4sB3sI")   # magic, version, reserved, chunk count
CHUNK_HEADER_STRUCT = struct.Struct("<4sI")  # type, payload length


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    if len(chunk_type) != 4:
        raise ValueError(f"chunk type must be 4 bytes, got {chunk_type!r}")
    return CHUNK_HEADER_STRUCT.pack(chunk_type, len(payload)) + payload


def build_daff(meta: dict, stages: list, thumbnails: dict, audio_bytes: bytes) -> bytes:
    """
    meta:        dict, written as the META chunk (must include audioMime)
    stages:      list of stage dicts, written as the STAG chunk
    thumbnails:  { thumbnailId: (mime_str, image_bytes) }
    audio_bytes: raw audio file contents
    """
    chunks = []

    meta_json = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    chunks.append(_chunk(b"META", meta_json))

    stag_json = json.dumps(stages, ensure_ascii=False).encode("utf-8")
    chunks.append(_chunk(b"STAG", stag_json))

    for thumb_id, (mime, img_bytes) in thumbnails.items():
        id_bytes = thumb_id.encode("utf-8")
        mime_bytes = mime.encode("utf-8")
        if len(id_bytes) > 255 or len(mime_bytes) > 255:
            raise ValueError("thumbnail id/mime must each be <= 255 bytes")
        payload = (
            bytes([len(id_bytes)]) + id_bytes +
            bytes([len(mime_bytes)]) + mime_bytes +
            img_bytes
        )
        chunks.append(_chunk(b"THMB", payload))

    chunks.append(_chunk(b"AUDI", audio_bytes))

    header = HEADER_STRUCT.pack(MAGIC, VERSION, b"\x00\x00\x00", len(chunks))
    return header + b"".join(chunks)


def parse_daff(data: bytes) -> dict:
    if len(data) < HEADER_STRUCT.size:
        raise ValueError("file too small to be a DAFF file")

    magic, version, _reserved, chunk_count = HEADER_STRUCT.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError(f"not a DAFF file (bad magic {magic!r})")
    if version > VERSION:
        raise ValueError(f"unsupported DAFF version {version}")

    offset = HEADER_STRUCT.size
    meta = None
    stages = None
    thumbnails = {}
    audio_bytes = None
    unknown_chunks = []

    for _ in range(chunk_count):
        chunk_type, length = CHUNK_HEADER_STRUCT.unpack_from(data, offset)
        offset += CHUNK_HEADER_STRUCT.size
        payload = data[offset:offset + length]
        offset += length

        if chunk_type == b"META":
            meta = json.loads(payload.decode("utf-8"))
        elif chunk_type == b"STAG":
            stages = json.loads(payload.decode("utf-8"))
        elif chunk_type == b"THMB":
            id_len = payload[0]
            thumb_id = payload[1:1 + id_len].decode("utf-8")
            cursor = 1 + id_len
            mime_len = payload[cursor]
            cursor += 1
            mime = payload[cursor:cursor + mime_len].decode("utf-8")
            cursor += mime_len
            img_bytes = payload[cursor:]
            thumbnails[thumb_id] = (mime, img_bytes)
        elif chunk_type == b"AUDI":
            audio_bytes = payload
        else:
            unknown_chunks.append((chunk_type, payload))

    return {
        "version": version,
        "meta": meta or {},
        "stages": stages or [],
        "thumbnails": thumbnails,
        "audio": audio_bytes,
        "unknown_chunks": unknown_chunks,
    }
