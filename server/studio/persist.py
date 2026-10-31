"""Keep the data folder (projects, films, cast, jobs, media) across Space restarts.

A Space's disk is wiped on every restart or redeploy. With HF_TOKEN set, the data folder is restored from a private
Hugging Face dataset at startup and new or changed files are committed back every minute (and right after each job).
Free: dataset storage needs no paid plan. Repo: OPENCAP_DATA_REPO, default "<space id>-data".
"""
from __future__ import annotations

import os
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
        from huggingface_hub import CommitScheduler, HfApi, snapshot_download
        api = HfApi(token=tok)
        api.create_repo(r, repo_type="dataset", private=True, exist_ok=True)
        snapshot_download(r, repo_type="dataset", local_dir=data, token=tok)
        root = data.resolve()
        files = [root / f for f in api.list_repo_files(r, repo_type="dataset") if (root / f).is_file()]
        state["restored"] = len(files)
        s = CommitScheduler(repo_id=r, repo_type="dataset", folder_path=data, every=1, private=True, token=tok,
                            ignore_patterns=[".cache/**", "**/.cache/**", "**/selftest/**", "*.tmp", "*.part", "**/*.tmp"])
        for p in files:  # restored files are already in the repo
            s.last_uploaded[p] = p.stat().st_mtime
        state["scheduler"] = s
    except Exception as e:
        state["error"] = f"{type(e).__name__}: {str(e)[:300]}"


def flush():
    s = state["scheduler"]
    if s:
        try:
            s.trigger()
        except Exception as e:
            state["error"] = f"{type(e).__name__}: {str(e)[:300]}"


def status() -> dict:
    return {"repo": state["repo"], "on": state["scheduler"] is not None, "restored_files": state["restored"], "error": state["error"]}
