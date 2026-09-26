import { useState } from 'react'
import StatsPanel from './components/StatsPanel.jsx'
import GraphView from './components/GraphView.jsx'
import FileDetailPanel from './components/FileDetailPanel.jsx'

const API_URL = 'http://localhost:8000/analyze'

export default function App() {
  const [repoPath, setRepoPath] = useState('')
  const [result, setResult] = useState(null)   // { graph, metrics }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)  // { node, deps, usedBy }

  async function handleAnalyze() {
    if (!repoPath.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    setSelectedNode(null)

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath.trim() }),
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

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <h1 style={{ marginBottom: '1rem', color: '#e6edf3' }}>🧬 Git DNA</h1>

      {/* Input row */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <input
          type="text"
          value={repoPath}
          onChange={e => setRepoPath(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Absolute path to a local Python repository…"
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
          disabled={loading || !repoPath.trim()}
          style={{
            padding: '0.5rem 1.25rem',
            background: loading ? '#21262d' : '#1f6feb',
            color: loading ? '#7d8590' : '#fff',
            border: '1px solid #30363d',
            borderRadius: '6px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontWeight: 600,
            fontSize: '14px',
          }}
        >
          {loading ? 'Analyzing…' : 'Analyze'}
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
          }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '1.5rem', alignItems: 'start' }}>
          <StatsPanel metrics={result.metrics} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <GraphView
              graph={result.graph}
              onNodeSelect={setSelectedNode}
            />
            {selectedNode && (
              <FileDetailPanel
                node={selectedNode.node}
                deps={selectedNode.deps}
                usedBy={selectedNode.usedBy}
                onClose={() => setSelectedNode(null)}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
