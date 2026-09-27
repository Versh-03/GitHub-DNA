import { useState } from 'react'
import StatsPanel from './components/StatsPanel.jsx'
import GraphView from './components/GraphView.jsx'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Detect whether the input looks like a GitHub HTTPS URL.
function isGitHubURL(value) {
  return value.trim().startsWith('https://github.com/')
}

export default function App() {
  const [input, setInput] = useState('')
  const [result, setResult] = useState(null)   // { graph, metrics }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const usingGitHub = isGitHubURL(input)

  async function handleAnalyze() {
    const value = input.trim()
    if (!value) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const endpoint = usingGitHub ? `${API_BASE}/analyze-github` : `${API_BASE}/analyze`
      const body = usingGitHub
        ? JSON.stringify({ github_url: value })
        : JSON.stringify({ repo_path: value })

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Server error ${res.status}: ${text}`)
      }

      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleAnalyze()
  }

  // Badge shown next to the input to indicate current mode.
  const modeBadge = usingGitHub
    ? { label: 'GitHub URL', color: '#238636', border: '#2ea043' }
    : { label: 'Local path', color: '#1c2128', border: '#30363d' }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <h1 style={{ marginBottom: '0.5rem', color: '#e6edf3' }}>🧬 Git DNA</h1>
      <p style={{ color: '#7d8590', fontSize: '13px', marginBottom: '1.25rem' }}>
        Enter a <strong style={{ color: '#e6edf3' }}>GitHub URL</strong>
        {' '}(e.g. <code style={{ color: '#79c0ff' }}>https://github.com/owner/repo</code>)
        {' '}or an <strong style={{ color: '#e6edf3' }}>absolute local path</strong> to a Python repository.
      </p>

      {/* Input row */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', alignItems: 'center' }}>
        {/* Mode badge */}
        <span
          style={{
            flexShrink: 0,
            padding: '0.3rem 0.6rem',
            background: modeBadge.color,
            border: `1px solid ${modeBadge.border}`,
            borderRadius: '6px',
            fontSize: '11px',
            fontWeight: 600,
            color: '#e6edf3',
            whiteSpace: 'nowrap',
          }}
        >
          {modeBadge.label}
        </span>

        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="https://github.com/owner/repo  or  /absolute/local/path"
          style={{
            flex: 1,
            padding: '0.5rem 0.75rem',
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '6px',
            fontSize: '14px',
            fontFamily: 'monospace',
            color: '#e6edf3',
            outline: 'none',
          }}
        />
        <button
          onClick={handleAnalyze}
          disabled={loading || !input.trim()}
          style={{
            padding: '0.5rem 1.25rem',
            background: loading ? '#21262d' : '#1f6feb',
            color: loading ? '#7d8590' : '#fff',
            border: '1px solid #30363d',
            borderRadius: '6px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontWeight: 600,
            fontSize: '14px',
            whiteSpace: 'nowrap',
          }}
        >
          {loading
            ? (usingGitHub ? 'Cloning & analyzing…' : 'Analyzing…')
            : 'Analyze'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            background: '#1a0a0a',
            border: '1px solid #6e2020',
            color: '#f97583',
            borderRadius: '6px',
            padding: '0.75rem 1rem',
            marginBottom: '1.5rem',
            fontFamily: 'monospace',
            fontSize: '13px',
            whiteSpace: 'pre-wrap',
          }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '1.5rem', alignItems: 'start' }}>
          <StatsPanel metrics={result.metrics} />
          <GraphView graph={result.graph} />
        </div>
      )}
    </div>
  )
}
