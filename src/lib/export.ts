import { Muxer, ArrayBufferTarget } from 'mp4-muxer'
import type { Cut, Music, Word } from '../captions/types'
import { drawFrame, videoOverlaysAt, type FrameInput } from './compositor'
import { keptRanges, outDuration, outToSrc } from './timeline'

export type ExportOpts = {
  videoUrl: string
  audioUrl: string | null       // processed audio (denoised etc.) or null = video's own track
  music: Music | null
  words: Word[]                 // for ducking
  cuts: Cut[]
  duration: number
  fps: number
  W: number; H: number
  frame: Omit<FrameInput, 'src' | 't' | 'srcW' | 'srcH'>
  onProgress: (p: number, msg: string) => void
  signal?: AbortSignal
}

export const webCodecsOk = () => typeof VideoEncoder !== 'undefined' && typeof AudioEncoder !== 'undefined' && typeof VideoFrame !== 'undefined'

const seekEl = (el: HTMLVideoElement, t: number) => new Promise<void>(res => {
  if (Math.abs(el.currentTime - t) < 0.001 || !isFinite(t)) return res()
  const done = () => { el.removeEventListener('seeked', done); res() }
  el.addEventListener('seeked', done); el.currentTime = t
})

/** Client-side render: seek the source frame by frame, compose on a canvas, encode H.264 + AAC, mux to MP4. */
export async function exportMp4(o: ExportOpts): Promise<Blob> {
  const video = document.createElement('video')
  video.src = o.videoUrl; video.muted = true; video.preload = 'auto'; video.playsInline = true
  await new Promise<void>((res, rej) => { video.onloadeddata = () => res(); video.onerror = () => rej(new Error('video load failed')) })
  const srcW = video.videoWidth, srcH = video.videoHeight
  // B-roll clips: own, paused elements so the preview's playing ones are not disturbed
  const brolls = new Map<string, HTMLVideoElement>()
  for (const ov of o.frame.overlays) if (ov.kind === 'video' && ov.src && !brolls.has(ov.src)) {
    const el = document.createElement('video'); el.src = ov.src; el.muted = true; el.preload = 'auto'; el.playsInline = true
    await new Promise<void>(res => { el.onloadeddata = () => res(); el.onerror = () => res() })
    brolls.set(ov.src, el)
  }
  const canvas = document.createElement('canvas'); canvas.width = o.W; canvas.height = o.H
  const ctx = canvas.getContext('2d', { alpha: false })!

  const total = outDuration(o.cuts, o.duration)
  const nFrames = Math.max(1, Math.floor(total * o.fps))
  const muxer = new Muxer({
    target: new ArrayBufferTarget(),
    video: { codec: 'avc', width: o.W, height: o.H, frameRate: o.fps },
    audio: { codec: 'aac', numberOfChannels: 2, sampleRate: 48000 },
    fastStart: 'in-memory',
  })
  let encErr: unknown = null
  const venc = new VideoEncoder({ output: (c, m) => muxer.addVideoChunk(c, m), error: e => { encErr = e } })
  const vcfg: VideoEncoderConfig = { codec: 'avc1.64002A', width: o.W, height: o.H, bitrate: Math.round(o.W * o.H * o.fps * 0.12), framerate: o.fps, latencyMode: 'quality', avc: { format: 'avc' } }
  const sup = await VideoEncoder.isConfigSupported(vcfg)
  if (!sup.supported) { vcfg.codec = 'avc1.4D0028'; vcfg.hardwareAcceleration = 'no-preference' }
  venc.configure(vcfg)

  // ---- audio: decode, splice kept ranges, mix music with ducking, encode AAC ----
  o.onProgress(0, 'decoding audio')
  const sr = 48000
  const actx = new OfflineAudioContext(2, 1, sr)
  const decode = async (url: string) => { try { return await actx.decodeAudioData(await (await fetch(url)).arrayBuffer()) } catch { return null } }
  const decoded = await decode(o.audioUrl ?? o.videoUrl)
  const musicBuf = o.music ? await decode(o.music.url) : null
  const aenc = new AudioEncoder({ output: (c, m) => muxer.addAudioChunk(c, m), error: e => { encErr = e } })
  aenc.configure({ codec: 'mp4a.40.2', numberOfChannels: 2, sampleRate: sr, bitrate: 192000 })
  const ranges = keptRanges(o.cuts, o.duration)
  const spliced = spliceAudio(decoded, ranges, sr)
  if (musicBuf && o.music) mixMusic(spliced, musicBuf, o.music, o.words, ranges, sr)
  {
    const chunk = 4800
    for (let i = 0; i < spliced.length; i += chunk) {
      const n = Math.min(chunk, spliced.length - i)
      const data = new Float32Array(n * 2)
      for (let ch = 0; ch < 2; ch++) data.set(spliced.channels[ch].subarray(i, i + n), ch * n)
      const ad = new AudioData({ format: 'f32-planar', sampleRate: sr, numberOfFrames: n, numberOfChannels: 2, timestamp: Math.round(i / sr * 1e6), data })
      aenc.encode(ad); ad.close()
      if (aenc.encodeQueueSize > 8) await new Promise(r => setTimeout(r, 5))
    }
  }

  // ---- video: seek + draw + encode ----
  const t0 = performance.now()
  for (let i = 0; i < nFrames; i++) {
    if (o.signal?.aborted) throw new Error('cancelled')
    if (encErr) throw encErr
    const tOut = i / o.fps
    const tSrc = Math.min(o.duration - 0.001, outToSrc(tOut, o.cuts, o.duration))
    await seekEl(video, tSrc)
    for (const { o: ov, srcT } of videoOverlaysAt(o.frame.overlays, tSrc)) { const el = brolls.get(ov.src!); if (el) await seekEl(el, Math.min(el.duration - 0.001, srcT)) }
    drawFrame(ctx, o.W, o.H, { ...o.frame, videos: brolls, src: video, srcW, srcH, t: tSrc })
    const vf = new VideoFrame(canvas, { timestamp: Math.round(tOut * 1e6), duration: Math.round(1e6 / o.fps) })
    venc.encode(vf, { keyFrame: i % (o.fps * 2) === 0 }); vf.close()
    if (venc.encodeQueueSize > 6) await new Promise(r => setTimeout(r, 4))
    if (i % 10 === 0) {
      const el = (performance.now() - t0) / 1000, rate = (i + 1) / el
      o.onProgress(i / nFrames, `frame ${i + 1}/${nFrames} · ${rate.toFixed(0)} fps · ~${Math.max(0, (nFrames - i) / rate).toFixed(0)}s left`)
    }
  }
  o.onProgress(0.99, 'finalising')
  await venc.flush(); await aenc.flush()
  venc.close(); aenc.close()
  muxer.finalize()
  video.src = ''; brolls.forEach(el => { el.src = '' })
  return new Blob([(muxer.target as ArrayBufferTarget).buffer], { type: 'video/mp4' })
}

type Pcm = { length: number; channels: Float32Array[] }

function spliceAudio(buf: AudioBuffer | null, ranges: Cut[], sr: number): Pcm {
  const total = ranges.reduce((n, r) => n + Math.round((r.end - r.start) * sr), 0)
  const channels = [new Float32Array(total), new Float32Array(total)]
  if (!buf) return { length: total, channels }
  const scale = buf.sampleRate / sr
  const srcCh = [buf.getChannelData(0), buf.numberOfChannels > 1 ? buf.getChannelData(1) : buf.getChannelData(0)]
  let pos = 0
  for (const r of ranges) {
    const n = Math.round((r.end - r.start) * sr)
    const s0 = Math.round(r.start * buf.sampleRate)
    for (let i = 0; i < n; i++) {
      const si = Math.min(srcCh[0].length - 1, s0 + Math.round(i * scale))
      const edge = Math.min(1, i / (sr * 0.005), (n - i) / (sr * 0.005)) // 5 ms fade at range edges
      channels[0][pos + i] = srcCh[0][si] * edge; channels[1][pos + i] = srcCh[1][si] * edge
    }
    pos += n
  }
  return { length: total, channels }
}

/** Music bed under the (already spliced) speech. Gain in dB, ducked by duckDb while a word is being spoken; 150 ms ramps. */
function mixMusic(out: Pcm, music: AudioBuffer, m: Music, words: Word[], ranges: Cut[], sr: number) {
  const mCh = [music.getChannelData(0), music.numberOfChannels > 1 ? music.getChannelData(1) : music.getChannelData(0)]
  const scale = music.sampleRate / sr
  const base = Math.pow(10, m.gainDb / 20), ducked = Math.pow(10, (m.gainDb + m.duckDb) / 20)
  const live = words.filter(w => !w.deleted)
  let pos = 0, g = base
  const ramp = 1 / (sr * 0.15)
  for (const r of ranges) {
    const n = Math.round((r.end - r.start) * sr)
    for (let i = 0; i < n; i++) {
      const tSrc = r.start + i / sr
      const mt = tSrc - m.start
      if (mt >= 0) {
        const mi = Math.round(mt * scale)
        if (mi < mCh[0].length) {
          const speaking = m.duck && live.some(w => tSrc >= w.start - 0.1 && tSrc < w.end + 0.25)
          const target = speaking ? ducked : base
          g += Math.sign(target - g) * Math.min(Math.abs(target - g), ramp * Math.abs(base - ducked) || ramp)
          out.channels[0][pos + i] += mCh[0][mi] * g; out.channels[1][pos + i] += mCh[1][mi] * g
        }
      }
    }
    pos += n
  }
  // soft clip
  for (const ch of out.channels) for (let i = 0; i < ch.length; i++) { const x = ch[i]; if (x > 0.98 || x < -0.98) ch[i] = Math.tanh(x) }
}
