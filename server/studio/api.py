"""Studio HTTP API: tool catalogue, jobs, asset library, characters, settings and usage.

  GET  /api/studio/tools                  catalogue (inputs/outputs per tool, rendered as forms by the web app)
  POST /api/studio/tools/{tool}/run       multipart: fields as form values, files as uploads → job (runs in a thread)
  GET  /api/studio/jobs[?tool=]           history;  GET /api/studio/jobs/{id}  one job (poll until done/error)
  GET  /api/studio/assets                 every generated file;  POST /api/studio/assets  upload into the library
  GET/POST/DELETE /api/studio/characters  locked characters (face refs, voice, wardrobe) reused by generation tools
  GET/PUT /api/studio/settings            API keys + per-capability provider/model routing
  GET  /api/studio/usage                  spend per provider / capability / tool
"""
from __future__ import annotations

import json, os, re, shutil, threading, time, traceback, uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile

from .providers import FREE_PROVIDERS, Out, ProviderError, Router, Settings
from . import tools as T
from . import film  # noqa: F401  registers the Film Studio tools


def make_router(DATA: Path, media_prefix: str = "/media", transcribe=None, local_tts=None) -> APIRouter:
    """transcribe(wav, language) -> {language, words}; local_tts(text, voice, speed) -> Path. Both optional (local models)."""
    S = DATA / "studio"
    for sub in ("jobs", "files", "uploads", "characters", "films"):
        (S / sub).mkdir(parents=True, exist_ok=True)
    # API keys live outside DATA: everything under DATA is publicly served at /media
    settings = Settings(Path(os.environ.get("OPENCAP_STUDIO_SETTINGS", DATA.parent / "studio-settings.json")))
    lock = threading.Lock()
    api = APIRouter(prefix="/api/studio")

    def url_of(p: Path) -> str:
        return f"{media_prefix}/{p.resolve().relative_to(DATA.resolve()).as_posix()}"

    def path_of(url: str) -> Path:
        rel = url.split("?")[0].removeprefix(media_prefix + "/")
        p = (DATA / rel).resolve()
        if DATA.resolve() not in p.parents or not p.exists():
            raise HTTPException(400, f"unknown file {url}")
        return p

    def save_job(j: dict):
        with lock:  # write then rename, so a poll never reads a half-written file
            tmp = S / "jobs" / f".{j['id']}.tmp"
            tmp.write_text(json.dumps(j, ensure_ascii=False)); tmp.replace(S / "jobs" / f"{j['id']}.json")

    def load_job(jid: str) -> dict:
        if not re.fullmatch(r"[a-f0-9]{12}", jid):
            raise HTTPException(400, "bad job id")
        f = S / "jobs" / f"{jid}.json"
        if not f.exists():
            raise HTTPException(404, "job not found")
        return json.loads(f.read_text())

    class Store:
        """Film projects and character locks, shared by the film tools."""
        def film(self, fid: str) -> dict:
            if not re.fullmatch(r"[a-f0-9]{12}", fid or ""):
                raise T.ToolError("Pick a film project")
            f = S / "films" / f"{fid}.json"
            if not f.exists():
                raise T.ToolError("Film project not found")
            return json.loads(f.read_text())

        def save_film(self, film: dict) -> dict:
            film["updated"] = time.time()
            with lock:
                tmp = S / "films" / f".{film['id']}.tmp"; tmp.write_text(json.dumps(film, ensure_ascii=False)); tmp.replace(S / "films" / f"{film['id']}.json")
            return film

        def save_character(self, c: dict, refs: list[Path], front: bool = False) -> dict:
            """Create or update a character; front=True makes the new refs its primary references (a re-cast)."""
            cid = c.get("id") or uuid.uuid4().hex[:12]
            d = S / "characters" / cid; d.mkdir(parents=True, exist_ok=True)
            cur = json.loads((S / "characters" / f"{cid}.json").read_text()) if (S / "characters" / f"{cid}.json").exists() else {"id": cid, "created": time.time(), "refs": []}
            for p in refs:
                dst = d / f"{uuid.uuid4().hex[:6]}{p.suffix}"; shutil.copy(p, dst)
                cur["refs"] = [url_of(dst)] + cur["refs"] if front else cur["refs"] + [url_of(dst)]
            cur.update({k: v for k, v in c.items() if k not in ("refs", "id")}); cur["updated"] = time.time()
            (S / "characters" / f"{cid}.json").write_text(json.dumps(cur, ensure_ascii=False))
            return cur

    store = Store()

    def characters() -> list[dict]:
        return [json.loads(f.read_text()) for f in sorted((S / "characters").glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)]

    # ---------- catalogue ----------

    @api.get("/tools")
    def list_tools():
        return {"categories": T.CATEGORIES, "tools": [t.public() for t in T.TOOLS.values()], "personas": T.PERSONAS}

    # ---------- run ----------

    @api.post("/tools/{tool_id}/run")
    async def run_tool(tool_id: str, request: Request):
        tool = T.TOOLS.get(tool_id)
        if not tool:
            raise HTTPException(404, "unknown tool")
        form = await request.form()
        jid = uuid.uuid4().hex[:12]
        up = S / "uploads" / jid
        values: dict = {}
        for k, v in form.multi_items():
            if hasattr(v, "filename") and hasattr(v, "file"):
                if not v.filename:
                    continue
                up.mkdir(parents=True, exist_ok=True)
                dst = up / f"{uuid.uuid4().hex[:6]}-{re.sub(r'[^A-Za-z0-9._-]+', '_', v.filename)}"
                with dst.open("wb") as f:
                    shutil.copyfileobj(v.file, f)
                values.setdefault(k, []).append(dst)
            else:
                values.setdefault(k, []).append(str(v))
        # library references (asset URLs) arrive as "<field>@url"
        for k in [k for k in values if k.endswith("@url")]:
            values.setdefault(k[:-4], []).extend(path_of(u) for u in values.pop(k) if u)
        params = tool.coerce(values)
        job = {"id": jid, "tool": tool_id, "toolName": tool.name, "created": time.time(), "status": "running", "progress": "Queued",
               "params": {k: (url_of(v) if isinstance(v, Path) else [url_of(x) if isinstance(x, Path) else x for x in v] if isinstance(v, list) else v) for k, v in params.items()},
               "outputs": [], "usage": [], "error": None}
        save_job(job)
        threading.Thread(target=execute, args=(tool, job, params), daemon=True).start()
        return job

    def execute(tool, job: dict, params: dict):
        out = Out(S / "files" / job["id"], "")
        def log(rec): job["usage"].append(rec); save_job(job)
        def progress(msg): job["progress"] = msg; save_job(job)
        ctx = T.Ctx(router=Router(settings, out, log), out=out, progress=progress, characters=characters, url_of=url_of, path_of=path_of, data=DATA,
                  transcribe=transcribe, local_tts=local_tts, store=store)
        try:
            result = tool.fn(ctx, **params)
            job["outputs"] = T.normalize(result, url_of)
            job["status"], job["progress"] = "done", "Done"
        except (ProviderError, T.ToolError) as e:
            job["status"], job["error"] = "error", str(e)
        except Exception as e:  # keep the trace for debugging, show the message in the UI
            job["status"], job["error"] = "error", f"{type(e).__name__}: {e}"
            job["trace"] = traceback.format_exc()[-2000:]
        job["finished"] = time.time()
        save_job(job)
        from . import persist
        persist.flush()  # push this job's results to the saved copy now, not in a minute

    @api.get("/jobs")
    def list_jobs(tool: str | None = None, limit: int = 100):
        files = sorted((S / "jobs").glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        out = []
        for f in files:
            j = json.loads(f.read_text())
            if tool and j["tool"] != tool:
                continue
            out.append(j)
            if len(out) >= limit:
                break
        return out

    @api.get("/jobs/{jid}")
    def get_job(jid: str):
        return load_job(jid)

    @api.delete("/jobs/{jid}")
    def delete_job(jid: str):
        load_job(jid)
        (S / "jobs" / f"{jid}.json").unlink()
        shutil.rmtree(S / "files" / jid, ignore_errors=True); shutil.rmtree(S / "uploads" / jid, ignore_errors=True)
        return {"ok": True}

    # ---------- asset library ----------

    @api.get("/assets")
    def assets(kind: str | None = None):
        items = []
        for j in list_jobs(limit=1000):
            for o in j.get("outputs", []):
                if o.get("url") and (not kind or o["kind"] == kind):
                    items.append({**o, "job": j["id"], "tool": j["tool"], "toolName": j.get("toolName"), "created": j["created"]})
        lib = S / "library"
        if lib.exists():
            for p in sorted(lib.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                k = T.kind_of(p)
                if not kind or k == kind:
                    items.append({"kind": k, "url": url_of(p), "name": p.name, "tool": "upload", "toolName": "Uploaded", "created": p.stat().st_mtime})
        return items

    @api.post("/assets")
    async def upload(file: UploadFile):
        lib = S / "library"; lib.mkdir(exist_ok=True)
        dst = lib / f"{uuid.uuid4().hex[:6]}-{re.sub(r'[^A-Za-z0-9._-]+', '_', file.filename or 'file')}"
        with dst.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"kind": T.kind_of(dst), "url": url_of(dst), "name": dst.name}

    # ---------- characters (continuity locks) ----------

    @api.get("/characters")
    def list_characters():
        return characters()

    @api.post("/characters")
    async def save_character(request: Request):
        form = await request.form()
        cid = str(form.get("id") or uuid.uuid4().hex[:12])
        if not re.fullmatch(r"[a-f0-9]{12}", cid):
            raise HTTPException(400, "bad id")
        f = S / "characters" / f"{cid}.json"
        c = json.loads(f.read_text()) if f.exists() else {"id": cid, "created": time.time(), "refs": []}
        for k in ("name", "description", "wardrobe", "voice", "role", "personality"):
            if form.get(k) is not None:
                c[k] = str(form.get(k))
        d = S / "characters" / cid; d.mkdir(exist_ok=True)
        for v in form.getlist("refs"):
            if getattr(v, "filename", None):
                dst = d / f"{uuid.uuid4().hex[:6]}{Path(v.filename).suffix.lower() or '.png'}"
                with dst.open("wb") as o:
                    shutil.copyfileobj(v.file, o)
                c["refs"].append(url_of(dst))
        for u in form.getlist("refs@url"):
            if u: c["refs"].append(url_of(path_of(str(u))))
        if form.get("removeRef"):
            c["refs"] = [r for r in c["refs"] if r != form.get("removeRef")]
        c["updated"] = time.time()
        f.write_text(json.dumps(c, ensure_ascii=False))
        return c

    @api.delete("/characters/{cid}")
    def delete_character(cid: str):
        if not re.fullmatch(r"[a-f0-9]{12}", cid):
            raise HTTPException(400, "bad id")
        (S / "characters" / f"{cid}.json").unlink(missing_ok=True)
        shutil.rmtree(S / "characters" / cid, ignore_errors=True)
        return {"ok": True}

    # ---------- film projects ----------

    @api.get("/films")
    def list_films():
        return [json.loads(f.read_text()) for f in sorted((S / "films").glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)]

    @api.post("/films")
    def create_film(payload: dict):
        f = {"id": uuid.uuid4().hex[:12], "created": time.time(), "title": str(payload.get("title") or "Untitled film")[:120], "logline": str(payload.get("logline") or ""),
             "genre": payload.get("genre") or "Drama", "aspect": payload.get("aspect") or "16:9", "style": payload.get("style") or "Cinematic realism",
             "script": "", "scenes": [], "cast": [], "score": [], "final": None}
        return store.save_film(f)

    @api.get("/films/{fid}")
    def get_film(fid: str):
        try:
            return store.film(fid)
        except T.ToolError as e:
            raise HTTPException(404, str(e))

    @api.patch("/films/{fid}")
    def patch_film(fid: str, payload: dict):
        f = get_film(fid)
        for k in ("title", "logline", "genre", "aspect", "style", "script", "scenes", "cast"):
            if k in payload: f[k] = payload[k]
        return store.save_film(f)

    @api.delete("/films/{fid}")
    def delete_film(fid: str):
        get_film(fid); (S / "films" / f"{fid}.json").unlink()
        return {"ok": True}

    # ---------- settings & usage ----------

    @api.get("/settings")
    def get_settings():
        return settings.public()

    @api.put("/settings")
    def put_settings(payload: dict):
        s = settings.load()
        for p, k in (payload.get("keys") or {}).items():
            if k is None or k == "":
                s.setdefault("keys", {}).pop(p, None)
            elif not str(k).startswith("•"):
                s.setdefault("keys", {})[p] = str(k).strip()
        for c, r in (payload.get("routes") or {}).items():
            s.setdefault("routes", {})[c] = r
        settings.save(s)
        return settings.public()

    @api.get("/estimate/{tool_id}")
    def estimate(tool_id: str):
        """Rough cost of one run before it starts: one call per capability the tool uses, on the provider it routes to."""
        from .providers import COST
        tool = T.TOOLS.get(tool_id)
        if not tool:
            raise HTTPException(404, "unknown tool")
        rows = [dict(cap=c, provider=p, model=m, usd=0 if p in FREE_PROVIDERS else COST.get(c, 0)) for c in tool.caps for p, m in [settings.route(c)]]
        return {"usd": round(sum(r["usd"] for r in rows), 3), "free": all(r["provider"] in ("free", "cloudflare") for r in rows) and bool(rows),
                "placeholder": any(r["provider"] == "mock" for r in rows), "calls": rows}

    @api.get("/free/status")
    def free_status():
        from . import free
        from . import persist
        return {**free.status(), "storage": persist.status()}

    _selftest: dict = {}

    @api.get("/selftest")
    def selftest(token: str = "", caps: str = "llm,image,tts", provider: str = "free"):
        """Runs one tiny job per capability on the Free provider. Needs ?token= matching the OPENCAP_SELFTEST variable."""
        want = os.environ.get("OPENCAP_SELFTEST")
        if not want or token != want:
            raise HTTPException(403, "set the OPENCAP_SELFTEST variable and pass ?token=")
        from PIL import Image
        out = Out(S / "files" / "selftest", "")
        r = Router(settings, out, lambda rec: None)
        img = out.path(".png"); Image.new("RGB", (512, 512), (40, 90, 160)).save(img)
        mask = out.path(".png"); Image.new("L", (512, 512), 0).save(mask)
        tests = {"llm": lambda: r.llm("Say ok.", provider=provider)[:60],
                 "json": lambda: json.dumps(r.llm_json("Cast a short sci-fi film set on a failing space station. Return {\"roles\": [{\"name\": str, \"casting\": str}]} with 3 roles, casting 40 words each.", provider=provider))[:400], "vision": lambda: r.llm("What colour is this?", images=[img], provider=provider)[:60],
                 "image": lambda: r.image("a red apple on a table", aspect="1:1", provider=provider), "edit": lambda: r.image("make it orange", refs=[img], provider=provider),
                 "video": lambda: r.video("waves on a beach", aspect="16:9", duration=2, provider=provider), "music": lambda: r.music("calm piano, instrumental", 10, provider=provider),
                 "sfx": lambda: r.sfx("door knock", 2, provider=provider), "upscale": lambda: r.upscale(img, 2, provider=provider),
                 "bg_remove": lambda: r.bg_remove(img, provider=provider), "tts": lambda: r.tts("Hello from Pulse Studio.", provider=provider),
                 "inpaint": lambda: r.inpaint(img, mask, "add a small star", provider=provider)}
        res = {}
        for c in [x for x in caps.split(",") if x in tests]:
            t0 = time.time()
            try:
                v = tests[c](); res[c] = {"ok": True, "seconds": round(time.time() - t0, 1), "result": [url_of(p) for p in v] if isinstance(v, list) else v,
                                          "provider": getattr(r, "last", {}).get("provider")}
            except Exception as e:
                res[c] = {"ok": False, "seconds": round(time.time() - t0, 1), "error": f"{type(e).__name__}: {str(e)[:300]}"}
        _selftest.update(res)
        return res

    @api.get("/usage")
    def usage():
        rows = []
        for j in list_jobs(limit=10000):
            for u in j.get("usage", []):
                rows.append({**u, "tool": j["tool"], "job": j["id"], "at": j["created"]})
        agg = lambda key: sorted(({"key": k, "calls": sum(1 for r in rows if r[key] == k), "usd": round(sum(r["usd"] for r in rows if r[key] == k), 3)}
                                  for k in {r[key] for r in rows}), key=lambda x: -x["usd"])
        return {"totalUsd": round(sum(r["usd"] for r in rows), 3), "calls": len(rows), "byProvider": agg("provider"), "byCap": agg("cap"), "byTool": agg("tool"), "recent": rows[:50]}

    return api
