import { Muxer, ArrayBufferTarget } from 'mp4-muxer'
import type { Cut } from '../captions/types'
import { drawFrame, type FrameInput } from './compositor'
import { keptRanges, outDuration, outToSrc } from './timeline'

export type ExportOpts = {
  videoUrl: string
  audioUrl: string | null       // processed audio (denoised etc.) or null = video's own track
  cuts: Cut[]
  duration: number
  fps: number
  W: number; H: number
  frame: Omit<FrameInput, 'src' | 't' | 'srcW' | 'srcH'>
  onProgress: (p: number, msg: string) => void
  signal?: AbortSignal
}

export const webCodecsOk = () => typeof VideoEncoder !== 'undefined' && typeof AudioEncoder !== 'undefined' && typeof VideoFrame !== 'undefined'

/** Client-side render: seek the source frame by frame, compose on a canvas, encode H.264 + AAC, mux to MP4. */
export async function exportMp4(o: ExportOpts): Promise<Blob> {
  const video = document.createElement('video')
  video.src = o.videoUrl; video.muted = true; video.preload = 'auto'; video.playsInline = true
  await new Promise<void>((res, rej) => { video.onloadeddata = () => res(); video.onerror = () => rej(new Error('video load failed')) })
  const srcW = video.videoWidth, srcH = video.videoHeight
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

  // ---- audio: decode, splice kept ranges, encode AAC ----
  o.onProgress(0, 'decoding audio')
  const audioBuf = await (await fetch(o.audioUrl ?? o.videoUrl)).arrayBuffer()
  const actx = new OfflineAudioContext(2, 1, 48000)
  let decoded: AudioBuffer | null = null
  try { decoded = await actx.decodeAudioData(audioBuf) } catch { decoded = null }
  const aenc = new AudioEncoder({ output: (c, m) => muxer.addAudioChunk(c, m), error: e => { encErr = e } })
  aenc.configure({ codec: 'mp4a.40.2', numberOfChannels: 2, sampleRate: 48000, bitrate: 192000 })
  if (decoded) {
    const sr = 48000
    const spliced = spliceAudio(decoded, keptRanges(o.cuts, o.duration), sr)
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
  const seekTo = (t: number) => new Promise<void>(res => {
    if (Math.abs(video.currentTime - t) < 0.001) return res()
    const done = () => { video.removeEventListener('seeked', done); res() }
    video.addEventListener('seeked', done); video.currentTime = t
  })
  const t0 = performance.now()
  for (let i = 0; i < nFrames; i++) {
    if (o.signal?.aborted) throw new Error('cancelled')
    if (encErr) throw encErr
    const tOut = i / o.fps
    const tSrc = Math.min(o.duration - 0.001, outToSrc(tOut, o.cuts, o.duration))
    await seekTo(tSrc)
    drawFrame(ctx, o.W, o.H, { ...o.frame, src: video, srcW, srcH, t: tSrc })
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
  video.src = ''
  return new Blob([(muxer.target as ArrayBufferTarget).buffer], { type: 'video/mp4' })
}

function spliceAudio(buf: AudioBuffer, ranges: Cut[], sr: number): { length: number; channels: Float32Array[] } {
  const scale = buf.sampleRate / sr
  const total = ranges.reduce((n, r) => n + Math.round((r.end - r.start) * sr), 0)
  const channels = [new Float32Array(total), new Float32Array(total)]
  const srcCh = [buf.getChannelData(0), buf.numberOfChannels > 1 ? buf.getChannelData(1) : buf.getChannelData(0)]
  let pos = 0
  for (const r of ranges) {
    const n = Math.round((r.end - r.start) * sr)
    const s0 = Math.round(r.start * buf.sampleRate)
    for (let i = 0; i < n; i++) {
      const si = Math.min(srcCh[0].length - 1, s0 + Math.round(i * scale))
      // 5 ms fade at range edges to avoid clicks
      const edge = Math.min(1, i / (sr * 0.005), (n - i) / (sr * 0.005))
      channels[0][pos + i] = srcCh[0][si] * edge; channels[1][pos + i] = srcCh[1][si] * edge
    }
    pos += n
  }
  return { length: total, channels }
}
