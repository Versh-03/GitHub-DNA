/**
 * StatsPanel — renders all keys from the metrics dict returned by /analyze.
 */

const PANEL_STYLE = {
  background: '#161b22',
  border: '1px solid #30363d',
  borderRadius: '8px',
  padding: '1rem',
  overflowY: 'auto',
  maxHeight: '80vh',
}

const SECTION_STYLE = {
  marginBottom: '1.25rem',
}

const ROW_STYLE = {
  display: 'flex',
  justifyContent: 'space-between',
  padding: '4px 0',
  borderBottom: '1px solid #21262d',
  fontSize: '13px',
}

const LABEL_STYLE = { color: '#7d8590' }
const VALUE_STYLE = { fontWeight: 600, fontFamily: 'monospace', color: '#e6edf3' }

function StatRow({ label, value }) {
  return (
    <div style={ROW_STYLE}>
      <span style={LABEL_STYLE}>{label}</span>
      <span style={VALUE_STYLE}>{value}</span>
    </div>
  )
}

function FileList({ items, pathKey = 'path', valueKey, valueLabel }) {
  if (!items || items.length === 0) return <p style={{ color: '#7d8590', fontSize: '12px' }}>None</p>
  return (
    <ol style={{ paddingLeft: '1.25rem', fontSize: '12px', lineHeight: 1.7 }}>
      {items.map((item, i) => (
        <li key={i} title={item[pathKey]}>
          <span style={{ fontFamily: 'monospace', wordBreak: 'break-all', color: '#cdd9e5' }}>
            {item[pathKey].split('/').pop()}
          </span>
          {valueKey && (
            <span style={{ color: '#7d8590', marginLeft: '0.4rem' }}>
              ({valueLabel} {item[valueKey]})
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}

export default function StatsPanel({ metrics }) {
  if (!metrics) return null

  const {
    total_files,
    source_files,
    test_files,
    doc_files,
    directories,
    total_edges,
    total_commits,
    contributor_count,
    top_changed_files,
    top_connected_files,
    largest_files,
  } = metrics

  return (
    <aside style={PANEL_STYLE}>
      <h2 style={{ marginBottom: '0.75rem' }}>Repository Metrics</h2>

      {/* Summary counts */}
      <div style={SECTION_STYLE}>
        <StatRow label="Total files"      value={total_files} />
        <StatRow label="Source files"     value={source_files} />
        <StatRow label="Test files"       value={test_files} />
        <StatRow label="Doc files"        value={doc_files} />
        <StatRow label="Directories"      value={directories} />
        <StatRow label="Dependency edges" value={total_edges} />
      </div>

      {/* Git stats */}
      <div style={SECTION_STYLE}>
        <h2>Git History</h2>
        <StatRow label="Total commits" value={total_commits} />
        <StatRow label="Contributors"  value={contributor_count} />
      </div>

      {/* Top changed files */}
      <div style={SECTION_STYLE}>
        <h2>Top Changed Files</h2>
        <FileList
          items={top_changed_files}
          valueKey="commit_count"
          valueLabel="commits:"
        />
      </div>

      {/* Top connected files */}
      <div style={SECTION_STYLE}>
        <h2>Top Connected Files</h2>
        <FileList
          items={top_connected_files}
          valueKey="connections"
          valueLabel="links:"
        />
      </div>

      {/* Largest files */}
      <div style={SECTION_STYLE}>
        <h2>Largest Files</h2>
        <FileList
          items={largest_files}
          valueKey="size_bytes"
          valueLabel="bytes:"
        />
      </div>
    </aside>
  )
}
