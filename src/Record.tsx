import { useEffect, useRef, useState } from 'react'

/** Camera / screen recorder → MediaRecorder → File. Everything stays in the browser until the user uploads. */
export function Record({ onDone, onClose }: { onDone: (f: File) => void; onClose: () => void }) {
  const [mode, setMode] = useState<'camera' | 'screen'>('camera')
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [rec, setRec] = useState<MediaRecorder | null>(null)
  const [secs, setSecs] = useState(0)
  const [err, setErr] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const chunks = useRef<Blob[]>([])

  const start = async () => {
    setErr(null)
    try {
      const st = mode === 'camera'
        ? await navigator.mediaDevices.getUserMedia({ video: { width: 1080, height: 1920, facingMode: 'user' }, audio: true })
        : await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
      if (mode === 'screen') { // add the mic to screen recordings
        try { const mic = await navigator.mediaDevices.getUserMedia({ audio: true }); mic.getAudioTracks().forEach(t => st.addTrack(t)) } catch { /* no mic */ }
      }
      setStream(st)
      if (videoRef.current) { videoRef.current.srcObject = st; videoRef.current.play() }
      const mime = ['video/mp4;codecs=avc1,mp4a.40.2', 'video/webm;codecs=vp9,opus', 'video/webm'].find(m => MediaRecorder.isTypeSupported(m)) ?? ''
      const r = new MediaRecorder(st, { mimeType: mime, videoBitsPerSecond: 8_000_000 })
      chunks.current = []
      r.ondataavailable = e => { if (e.data.size) chunks.current.push(e.data) }
      r.onstop = () => {
        const type = r.mimeType.split(';')[0]
        const ext = type.includes('mp4') ? 'mp4' : 'webm'
        onDone(new File(chunks.current, `recording-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.${ext}`, { type }))
        st.getTracks().forEach(t => t.stop())
      }
      r.start(1000); setRec(r); setSecs(0)
    } catch (e) { setErr(String(e)) }
  }
  useEffect(() => { if (!rec) return; const id = setInterval(() => setSecs(s => s + 1), 1000); return () => clearInterval(id) }, [rec])
  useEffect(() => () => stream?.getTracks().forEach(t => t.stop()), [stream])

  return (
    <div className="modal" onClick={onClose}>
      <div className="modal-body" onClick={e => e.stopPropagation()}>
        <h3>Record</h3>
        <div className="row">
          <button className={mode === 'camera' ? 'on' : ''} onClick={() => setMode('camera')} disabled={!!rec}>📷 Camera</button>
          <button className={mode === 'screen' ? 'on' : ''} onClick={() => setMode('screen')} disabled={!!rec}>🖥 Screen</button>
          <span style={{ flex: 1 }} />
          {!rec ? <button className="primary" onClick={start}>● Start</button> : <button className="danger" onClick={() => { rec.stop(); setRec(null) }}>■ Stop ({secs}s)</button>}
          <button onClick={onClose}>Close</button>
        </div>
        <video ref={videoRef} muted playsInline style={{ width: '100%', maxHeight: '60vh', background: '#000', borderRadius: 8 }} />
        {err && <p className="warn">{err}</p>}
        <p className="muted small">Recording stays on this machine. Stop to create a project from it; Whisper transcribes it automatically.</p>
      </div>
    </div>
  )
}
