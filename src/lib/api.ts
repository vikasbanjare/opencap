import type { Word } from '../captions/types'

export type ProjectMeta = {
  id: string; name: string; created: number; width: number; height: number; fps: number; duration: number
  hasAudio: boolean; playUrl: string; peaksUrl: string; language?: string
  transcribeStatus?: 'running' | 'done' | 'error' | null; transcribeError?: string | null
  transcript?: { language: string; words: Word[]; segments: { start: number; end: number; text: string }[] }
}

const j = async <T>(r: Response): Promise<T> => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json() }

export const api = {
  list: () => fetch('/api/projects').then(j<ProjectMeta[]>),
  get: (id: string) => fetch(`/api/projects/${id}`).then(j<ProjectMeta>),
  status: (id: string) => fetch(`/api/projects/${id}/status`).then(j<{ transcribeStatus: string | null; transcribeError: string | null }>),
  remove: (id: string) => fetch(`/api/projects/${id}`, { method: 'DELETE' }).then(j),
  upload: (file: File, onProgress?: (p: number) => void) => new Promise<ProjectMeta>((res, rej) => {
    const x = new XMLHttpRequest(); const fd = new FormData(); fd.append('file', file)
    x.upload.onprogress = e => onProgress?.(e.loaded / (e.total || 1))
    x.onload = () => x.status < 300 ? res(JSON.parse(x.responseText)) : rej(new Error(x.responseText))
    x.onerror = () => rej(new Error('upload failed'))
    x.open('POST', '/api/projects'); x.send(fd)
  }),
  retranscribe: (id: string, language?: string) => { const fd = new FormData(); if (language) fd.append('language', language); return fetch(`/api/projects/${id}/transcribe`, { method: 'POST', body: fd }).then(j) },
  srt: (cards: { start: number; end: number; text: string }[], format: 'srt' | 'vtt') =>
    fetch('/api/subtitles/srt', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ cards, format }) }).then(r => r.text()),
  audioTool: (id: string, tool: 'denoise' | 'normalize' | 'enhance') => fetch(`/api/projects/${id}/audio/${tool}`, { method: 'POST' }).then(j<{ url: string }>),
  saveRender: (id: string, blob: Blob) => { const fd = new FormData(); fd.append('file', blob, 'render.mp4'); return fetch(`/api/projects/${id}/renders`, { method: 'POST', body: fd }).then(j<{ url: string; name: string }>) },
  renders: (id: string) => fetch(`/api/projects/${id}/renders`).then(j<{ url: string; name: string; size: number }[]>),
  getState: (id: string) => fetch(`/api/projects/${id}/state`).then(j<Record<string, unknown> | null>),
  uploadAsset: (id: string, file: File) => { const fd = new FormData(); fd.append('file', file); return fetch(`/api/projects/${id}/assets`, { method: 'POST', body: fd }).then(j<{ url: string; kind: 'image' | 'video' | 'audio'; name: string; duration?: number; width?: number; height?: number }>) },
  ttsVoices: () => fetch('/api/tts/voices').then(j<{ voices: string[]; ready: boolean; clone: boolean }>),
  tts: (text: string, voice: string, speed: number) => fetch('/api/tts', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text, voice, speed }) }).then(j<{ url: string; duration: number }>),
  clone: (projectId: string, text: string, refStart: number, refEnd: number, speed: number) => fetch('/api/clone', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ projectId, text, refStart, refEnd, speed }) }).then(j<{ url: string; duration: number }>),
  translateLanguages: () => fetch('/api/translate/languages').then(j<{ ready: boolean; available: string[]; installed: string[][] }>),
  translate: (texts: string[], source: string, target: string) => fetch('/api/translate', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ texts, source, target }) }).then(j<{ texts: string[] }>),
  exportServer: (id: string, cuts: { start: number; end: number }[]) =>
    fetch(`/api/projects/${id}/export`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ cuts }) }).then(j<{ url: string }>),
}

export const download = (blobOrUrl: Blob | string, name: string) => {
  const a = document.createElement('a')
  a.href = typeof blobOrUrl === 'string' ? blobOrUrl : URL.createObjectURL(blobOrUrl)
  a.download = name; document.body.appendChild(a); a.click(); a.remove()
}
