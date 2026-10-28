// Studio API client. Tools are declared on the server; the web app renders their forms from this schema.

export type FieldType = 'text' | 'textarea' | 'select' | 'chips' | 'number' | 'slider' | 'toggle' | 'color'
  | 'image' | 'images' | 'video' | 'audio' | 'media' | 'character' | 'characters' | 'mask' | 'sketch'

export type Field = {
  id: string; label: string; type: FieldType
  options?: (string | { value: string; label: string })[]
  default?: unknown; min?: number; max?: number; step?: number
  help?: string; placeholder?: string; required?: boolean; group?: string
  showIf?: Record<string, unknown[]>
}

export type Tool = {
  id: string; name: string; category: string; icon: string; tagline: string; description: string
  inputs: Field[]; outputs: string[]; caps: string[]; modes?: { id: string; label: string }[]
  link?: string // tools that open an existing Pulse screen instead of running a job
}

export type Output = { kind: 'image' | 'video' | 'audio' | 'text' | 'json' | 'file'; url?: string; text?: string; data?: unknown; label?: string; name?: string }

export type Job = {
  id: string; tool: string; toolName: string; created: number; finished?: number
  status: 'running' | 'done' | 'error'; progress: string; error: string | null
  params: Record<string, unknown>; outputs: Output[]
  usage: { cap: string; provider: string; model: string; seconds: number; usd: number }[]
}

export type Character = { id: string; name: string; description?: string; wardrobe?: string; voice?: string; role?: string; personality?: string; refs: string[] }
export type Asset = Output & { job?: string; tool: string; toolName?: string; created: number }
export type Persona = { id: string; name: string; icon: string; pitch: string; tools: string[] }
export type Catalogue = { categories: { id: string; name: string; blurb: string }[]; tools: Tool[]; personas: Persona[] }

export type SettingsView = {
  providers: { id: string; env: string; configured: boolean; fromEnv: boolean; caps: string[] }[]
  caps: { id: string; label: string; route: { provider: string; model?: string }; active: { provider: string; model: string }; options: Record<string, string[]> }[]
}

export type Usage = { totalUsd: number; calls: number; byProvider: Agg[]; byCap: Agg[]; byTool: Agg[]; recent: { cap: string; provider: string; model: string; usd: number; tool: string; at: number }[] }
type Agg = { key: string; calls: number; usd: number }

const j = async <T>(r: Response): Promise<T> => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json() }
const B = '/api/studio'

export const studio = {
  catalogue: () => fetch(`${B}/tools`).then(j<Catalogue>),
  run: (tool: string, fd: FormData) => fetch(`${B}/tools/${tool}/run`, { method: 'POST', body: fd }).then(j<Job>),
  job: (id: string) => fetch(`${B}/jobs/${id}`).then(j<Job>),
  jobs: (tool?: string) => fetch(`${B}/jobs${tool ? `?tool=${tool}` : ''}`).then(j<Job[]>),
  deleteJob: (id: string) => fetch(`${B}/jobs/${id}`, { method: 'DELETE' }).then(j),
  assets: (kind?: string) => fetch(`${B}/assets${kind ? `?kind=${kind}` : ''}`).then(j<Asset[]>),
  upload: (f: File) => { const fd = new FormData(); fd.append('file', f); return fetch(`${B}/assets`, { method: 'POST', body: fd }).then(j<Asset>) },
  characters: () => fetch(`${B}/characters`).then(j<Character[]>),
  saveCharacter: (fd: FormData) => fetch(`${B}/characters`, { method: 'POST', body: fd }).then(j<Character>),
  deleteCharacter: (id: string) => fetch(`${B}/characters/${id}`, { method: 'DELETE' }).then(j),
  settings: () => fetch(`${B}/settings`).then(j<SettingsView>),
  saveSettings: (p: { keys?: Record<string, string | null>; routes?: Record<string, { provider: string; model?: string }> }) =>
    fetch(`${B}/settings`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(p) }).then(j<SettingsView>),
  usage: () => fetch(`${B}/usage`).then(j<Usage>),
}

/** Poll a job until it finishes. */
export async function waitJob(id: string, onTick: (j: Job) => void): Promise<Job> {
  for (;;) {
    const job = await studio.job(id); onTick(job)
    if (job.status !== 'running') return job
    await new Promise(r => setTimeout(r, 1500))
  }
}
