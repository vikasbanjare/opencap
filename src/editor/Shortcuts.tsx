const KEYS: [string, string][] = [
  ['Space', 'Play / pause'], ['← / →', 'Step one frame (hold Shift: one second)'],
  ['⌘Z', 'Undo'], ['⇧⌘Z or ⌘Y', 'Redo'],
  ['Click a caption', 'Select it (video, timeline or list)'], ['Enter', 'Retype the selected caption'],
  ['Double-click a caption', 'Retype it in place'], ['Delete', 'Remove the selected caption (video stays) or element'],
  ['Drag a caption block', 'Move it in time'], ['Drag a block edge', 'Stretch or shorten it'],
  ['Drag a corner on the video', 'Resize the caption or element'], ['Shift-drag on the timeline', 'Cut that part of the video'],
  ['S', 'Split the clip at the playhead'], ['Esc', 'Clear the selection'], ['?', 'Show this sheet'],
]
export function Shortcuts({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal" onClick={onClose}>
      <div className="modal-body keys" onClick={e => e.stopPropagation()}>
        <h3>Keyboard shortcuts <button className="icon" style={{ marginLeft: 'auto' }} onClick={onClose} title="Close">✕</button></h3>
        <dl>{KEYS.map(([k, d]) => <div key={k}><dt><kbd>{k}</kbd></dt><dd>{d}</dd></div>)}</dl>
      </div>
    </div>
  )
}
