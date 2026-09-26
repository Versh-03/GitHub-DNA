/**
 * FileDetailPanel — shows file details when a graph node is clicked.
 *
 * Props:
 *   node     — { id, type, language, size_bytes, commit_count } | null
 *   deps     — string[] — files this node imports (outgoing edges)
 *   usedBy   — string[] — files that import this node (incoming edges)
 *   onClose  — () => void
 */

const PANEL = {
  background: '#161b22',
  border: '1px solid #30363d',
  borderRadius: '8px',
  padding: '1rem',
  overflowY: 'auto',
  maxHeight: '80vh',
}

const HEADING = {
  fontSize: '0.72rem',
  fontWeight: 600,
  color: '#7d8590',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: '0.5rem',
  marginTop: '1rem',
}

const ROW = {
  display: 'flex',
  justifyContent: 'space-between',
  padding: '4px 0',
  borderBottom: '1px solid #21262d',
  fontSize: '13px',
}

const LABEL = { color: '#7d8590' }
const VALUE = { fontWeight: 600, fontFamily: 'monospace', color: '#e6edf3', wordBreak: 'break-all', textAlign: 'right', maxWidth: '60%' }

const TYPE_COLOR = {
  source: '#388bfd',
  test:   '#3fb950',
  docs:   '#d29922',
  config: '#a371f7',
  other:  '#8b949e',
}

function formatBytes(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function FileBadge({ path }) {
  const name = path.split('/').pop()
  return (
    <div title={path} style={{
      padding: '2px 6px',
      marginBottom: '4px',
      background: '#21262d',
      borderRadius: '4px',
      fontSize: '12px',
      fontFamily: 'monospace',
      color: '#cdd9e5',
      wordBreak: 'break-all',
    }}>
      {name}
      <span style={{ color: '#7d8590', marginLeft: '4px', fontSize: '11px' }}>
        {path.includes('/') ? path.substring(0, path.lastIndexOf('/')) : ''}
      </span>
    </div>
  )
}

function FileList({ items, empty }) {
  if (!items || items.length === 0) {
    return <p style={{ fontSize: '12px', color: '#7d8590' }}>{empty}</p>
  }
  return (
    <div>
      {items.map(p => <FileBadge key={p} path={p} />)}
    </div>
  )
}

export default function FileDetailPanel({ node, deps, usedBy, onClose }) {
  if (!node) return null

  const fileName  = node.id.split('/').pop()
  const repoPath  = node.id
  const fileExt   = fileName.includes('.') ? '.' + fileName.split('.').pop() : '(none)'
  const typeColor = TYPE_COLOR[node.type] || TYPE_COLOR.other

  return (
    <aside style={PANEL}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '14px', color: '#e6edf3', wordBreak: 'break-all' }}>
            {fileName}
          </div>
          <span style={{
            display: 'inline-block',
            marginTop: '4px',
            padding: '1px 7px',
            borderRadius: '12px',
            fontSize: '11px',
            fontWeight: 600,
            border: `1px solid ${typeColor}`,
            color: typeColor,
          }}>
            {node.type}
          </span>
        </div>
        <button
          onClick={onClose}
          title="Close"
          style={{
            background: 'none',
            border: 'none',
            color: '#7d8590',
            cursor: 'pointer',
            fontSize: '16px',
            lineHeight: 1,
            padding: '2px 4px',
            flexShrink: 0,
          }}
        >
          ✕
        </button>
      </div>

      {/* File details */}
      <h2 style={HEADING}>File Details</h2>
      <div style={ROW}>
        <span style={LABEL}>Repository path</span>
        <span style={VALUE}>{repoPath}</span>
      </div>
      <div style={ROW}>
        <span style={LABEL}>File type</span>
        <span style={VALUE}>{fileExt}</span>
      </div>
      <div style={ROW}>
        <span style={LABEL}>Language</span>
        <span style={VALUE}>{node.language}</span>
      </div>
      <div style={ROW}>
        <span style={LABEL}>File size</span>
        <span style={VALUE}>{formatBytes(node.size_bytes)}</span>
      </div>
      <div style={ROW}>
        <span style={LABEL}>Commit count</span>
        <span style={VALUE}>{node.commit_count ?? 0}</span>
      </div>

      {/* Dependencies */}
      <h2 style={{ ...HEADING, marginTop: '1.25rem' }}>
        Dependencies ({deps.length})
      </h2>
      <FileList items={deps} empty="No outgoing imports" />

      {/* Used by */}
      <h2 style={{ ...HEADING, marginTop: '1.25rem' }}>
        Used by ({usedBy.length})
      </h2>
      <FileList items={usedBy} empty="No files import this" />
    </aside>
  )
}
