"""Offline translation with Argos language packs run directly on CTranslate2 + SentencePiece.

ponytail: argostranslate itself drags in torch + stanza (>2 GB); the .argosmodel packs are plain
CTranslate2 models, so we download the pack and run it ourselves. Sentence splitting is a regex.
"""
from __future__ import annotations

import json, re, urllib.request, zipfile
from pathlib import Path

INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
_index: list[dict] | None = None
_loaded: dict[tuple[str, str], tuple[object, object]] = {}


_CACHE = Path(__file__).parent / "models" / "argos" / "index.json"


def index() -> list[dict]:
    """Package index: disk copy first (instant, works offline), network only when there is none yet."""
    global _index
    if _index is None and _CACHE.exists():
        _index = json.loads(_CACHE.read_text())
    if _index is None:
        with urllib.request.urlopen(urllib.request.Request(INDEX_URL, headers={"User-Agent": "Mozilla/5.0 (Pulse)"}), timeout=10) as r:
            _index = json.load(r)
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(_index))
    return _index


def available_targets(src: str = "en") -> list[str]:
    try:
        return sorted({p["to_code"] for p in index() if p["from_code"] == src} | {p["from_code"] for p in index() if p["to_code"] == src})
    except Exception:
        return []


def pack_dir(models: Path, a: str, b: str) -> Path | None:
    d = models / "argos" / f"{a}_{b}"
    if d.exists() and any(d.rglob("model.bin")):
        return d
    cand = [p for p in index() if p["from_code"] == a and p["to_code"] == b]
    if not cand:
        return None
    links = cand[0].get("links") or []
    if not links:
        return None
    d.mkdir(parents=True, exist_ok=True)
    zpath = d / "pack.zip"
    req = urllib.request.Request(links[0], headers={"User-Agent": "Mozilla/5.0 (Pulse)"})  # the CDN rejects urllib's default UA
    with urllib.request.urlopen(req, timeout=120) as r, zpath.open("wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(d)
    zpath.unlink(missing_ok=True)
    return d


def load(models: Path, a: str, b: str):
    key = (a, b)
    if key in _loaded:
        return _loaded[key]
    import ctranslate2, sentencepiece as spm
    d = pack_dir(models, a, b)
    if d is None:
        raise FileNotFoundError(f"no Argos pack for {a}->{b}")
    model_dir = next(p.parent for p in d.rglob("model.bin"))
    sp_path = next(d.rglob("sentencepiece.model"))
    tr = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8")
    sp = spm.SentencePieceProcessor(model_file=str(sp_path))
    _loaded[key] = (tr, sp)
    return tr, sp


_SENT = re.compile(r"(?<=[.!?。！？])\s+")


def translate_texts(models: Path, texts: list[str], a: str, b: str) -> list[str]:
    if a == b:
        return texts
    try:
        hops = [(a, b)]; load(models, a, b)
    except FileNotFoundError:
        hops = [(a, "en"), ("en", b)]  # pivot through English
    out = texts
    for x, y in hops:
        if x == y:
            continue
        tr, sp = load(models, x, y)
        # translate sentence by sentence, keep the 1:1 mapping with the input list
        sents, owner = [], []
        for i, t in enumerate(out):
            parts = [p for p in _SENT.split(t.strip()) if p] or [""]
            sents += parts; owner += [i] * len(parts)
        toks = [sp.encode(s, out_type=str) for s in sents]
        res = tr.translate_batch(toks, beam_size=2, max_batch_size=16)
        dec = [sp.decode(r.hypotheses[0]) for r in res]
        merged = [""] * len(out)
        for i, s in zip(owner, dec):
            merged[i] = (merged[i] + " " + s).strip()
        out = merged
    return out
