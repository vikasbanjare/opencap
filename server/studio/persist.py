"""Keep the data folder (projects, films, cast, jobs, media) across Space restarts.

A Space's disk is wiped on every restart or redeploy. With HF_TOKEN set, the data folder is restored from a private
Hugging Face dataset at startup and new or changed files are committed back every minute (and right after each job).
Free: dataset storage needs no paid plan. Repo: OPENCAP_DATA_REPO, default "<space id>-data".
"""
from __future__ import annotations

import os, threading, time
from pathlib import Path

state = {"repo": None, "restored": 0, "error": None, "scheduler": None}


def repo() -> str | None:
    r = os.environ.get("OPENCAP_DATA_REPO") or (f"{os.environ['SPACE_ID']}-data" if os.environ.get("SPACE_ID") else "")
    return r if r and r != "off" and os.environ.get("HF_TOKEN") else None


def start(data: Path):
    """Restore, then start the background sync. Never raises: the app runs without sync if anything fails."""
    r = repo()
    if not r:
        return
    state["repo"] = r
    tok = os.environ["HF_TOKEN"].strip()
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.create_repo(r, repo_type="dataset", private=True, exist_ok=True)
    except Exception as e:
        state["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return
    root = data.resolve()
    _pull(r, root, tok, ["**/*.json", "*.json"])  # projects, cast and history first: the site is usable right away
    threading.Thread(target=_finish, args=(api, r, root, tok, data), daemon=True).start()


def _pull(r, root: Path, tok, patterns=None):
    from huggingface_hub import constants, snapshot_download
    constants.HF_HUB_DISABLE_XET = True  # the Xet path failed mid-restore once ("File size mismatch"); plain HTTPS is fine here
    for attempt in range(3):
        try:
            snapshot_download(r, repo_type="dataset", local_dir=root, token=tok, allow_patterns=patterns, max_workers=8)
            return True
        except Exception as e:
            state["error"] = f"restore attempt {attempt + 1}: {type(e).__name__}: {str(e)[:200]}"
            time.sleep(2 + 3 * attempt)
    return False


def _finish(api, r, root: Path, tok, data: Path):
    """Media in the background, then a size check with per-file retries, then the sync starts."""
    from huggingface_hub import CommitScheduler, hf_hub_download
    _pull(r, root, tok)
    restored, failed = [], []
    try:
        infos = [i for i in api.list_repo_tree(r, repo_type="dataset", recursive=True) if getattr(i, "size", None) is not None]
    except Exception as e:
        infos = []; state["error"] = f"list: {type(e).__name__}: {str(e)[:200]}"
    for i in infos:
        dst = root / i.path
        for attempt in range(4):
            if dst.is_file() and dst.stat().st_size == i.size:
                restored.append(dst); break
            if attempt == 3:
                continue
            try:
                hf_hub_download(r, i.path, repo_type="dataset", local_dir=root, token=tok, force_download=True)
            except Exception:
                time.sleep(1 + attempt)
        else:
            failed.append(i.path)
    state["restored"] = len(restored)
    state["error"] = f"{len(failed)} file(s) could not be restored: {failed[:5]}" if failed else None
    try:  # starts even if some files failed: the sync only adds, never deletes
        s = CommitScheduler(repo_id=r, repo_type="dataset", folder_path=data, every=1, private=True, token=tok,
                            ignore_patterns=[".cache/**", "**/.cache/**", "**/selftest/**", "*.tmp", "*.part", "**/*.tmp"])
        for p in restored:
            s.last_uploaded[p] = p.stat().st_mtime
        state["scheduler"] = s
    except Exception as e:
        state["error"] = f"sync: {type(e).__name__}: {str(e)[:300]}"


def flush():
    s = state["scheduler"]
    if s:
        try:
            s.trigger()
        except Exception as e:
            state["error"] = f"{type(e).__name__}: {str(e)[:300]}"


def status() -> dict:
    return {"repo": state["repo"], "on": state["scheduler"] is not None, "restored_files": state["restored"], "error": state["error"]}
