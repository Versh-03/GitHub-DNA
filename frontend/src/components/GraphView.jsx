/**
 * GraphView — renders the dependency graph using @xyflow/react.
 *
 * Layout: compact force-like placement.
 *   1. Build an adjacency list from the edges.
 *   2. Run a simple iterative spring relaxation (no library needed).
 *   3. Scale the result to keep nodes well-spaced but tightly packed.
 */

import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

// Node dimensions
const NODE_W = 200
const NODE_H = 52

/** Dark-theme node color per file_type — saturated but readable on dark bg */
function nodeColor(type) {
  switch (type) {
    case 'source': return '#1c3a5e'   // deep blue
    case 'test':   return '#14412e'   // deep green
    case 'docs':   return '#3d3000'   // amber/dark yellow
    case 'config': return '#2e1f4f'   // dark violet
    default:       return '#1e2329'   // near-black gray
  }
}

/** Border accent per file_type */
function nodeBorder(type) {
  switch (type) {
    case 'source': return '#388bfd'
    case 'test':   return '#3fb950'
    case 'docs':   return '#d29922'
    case 'config': return '#a371f7'
    default:       return '#484f58'
  }
}

/** Minimap color (slightly brighter variant of node fill) */
function minimapColor(type) {
  switch (type) {
    case 'source': return '#1f6feb'
    case 'test':   return '#238636'
    case 'docs':   return '#9e6a03'
    case 'config': return '#6e40c9'
    default:       return '#30363d'
  }
}

// ── Compact spring layout ───────────────────────────────────────────────────

const IDEAL_EDGE_LEN  = 260   // desired distance between connected nodes
const REPULSION       = 18000  // repulsion constant between all node pairs
const SPRING_K        = 0.08   // spring stiffness
const ITERATIONS      = 120    // relaxation iterations
const DAMPING         = 0.85   // velocity damping per step

function springLayout(nodeIds, edges) {
  const n = nodeIds.length
  if (n === 0) return {}

  // Initial positions: place on a circle so the layout always converges
  const radius = Math.max(200, n * 45)
  const pos = {}
  nodeIds.forEach((id, i) => {
    const angle = (2 * Math.PI * i) / n
    pos[id] = {
      x: radius * Math.cos(angle),
      y: radius * Math.sin(angle),
      vx: 0,
      vy: 0,
    }
  })

  // Build edge set for quick lookup
  const edgePairs = edges.map(e => [e.source, e.target])

  for (let iter = 0; iter < ITERATIONS; iter++) {
    const force = {}
    nodeIds.forEach(id => { force[id] = { fx: 0, fy: 0 } })

    // Repulsion between every pair
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = nodeIds[i]
        const b = nodeIds[j]
        const dx = pos[b].x - pos[a].x
        const dy = pos[b].y - pos[a].y
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
        const f = REPULSION / (dist * dist)
        const nx = (dx / dist) * f
        const ny = (dy / dist) * f
        force[a].fx -= nx
        force[a].fy -= ny
        force[b].fx += nx
        force[b].fy += ny
      }
    }

    // Spring attraction along edges
    for (const [src, tgt] of edgePairs) {
      if (!pos[src] || !pos[tgt]) continue
      const dx = pos[tgt].x - pos[src].x
      const dy = pos[tgt].y - pos[src].y
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
      const stretch = dist - IDEAL_EDGE_LEN
      const f = SPRING_K * stretch
      const nx = (dx / dist) * f
      const ny = (dy / dist) * f
      force[src].fx += nx
      force[src].fy += ny
      force[tgt].fx -= nx
      force[tgt].fy -= ny
    }

    // Integrate
    nodeIds.forEach(id => {
      pos[id].vx = (pos[id].vx + force[id].fx) * DAMPING
      pos[id].vy = (pos[id].vy + force[id].fy) * DAMPING
      pos[id].x += pos[id].vx
      pos[id].y += pos[id].vy
    })
  }

  // Center around (0,0) and return plain {x,y}
  let cx = 0, cy = 0
  nodeIds.forEach(id => { cx += pos[id].x; cy += pos[id].y })
  cx /= n; cy /= n
  const result = {}
  nodeIds.forEach(id => {
    result[id] = { x: pos[id].x - cx, y: pos[id].y - cy }
  })
  return result
}

// ── Main builder ─────────────────────────────────────────────────────────────

/** Convert the raw graph payload from /analyze into React Flow node/edge arrays */
function buildFlowData(graph) {
  const nodeIds = graph.nodes.map(n => n.id)
  const positions = springLayout(nodeIds, graph.edges)

  // Build type lookup
  const typeMap = {}
  graph.nodes.forEach(n => { typeMap[n.id] = n.type })

  const nodes = graph.nodes.map(n => {
    const label = n.id.split('/').pop()
    const pos = positions[n.id] || { x: 0, y: 0 }
    const type = n.type
    return {
      id: n.id,
      position: { x: pos.x, y: pos.y },
      data: {
        label: (
          <div style={{ fontSize: '11px', lineHeight: 1.4 }}>
            <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '176px', color: '#e6edf3' }}>
              {label}
            </div>
            <div style={{ color: '#7d8590' }}>
              {type} · {n.commit_count} commits
            </div>
          </div>
        ),
        type,
      },
      style: {
        background: nodeColor(type),
        border: `1px solid ${nodeBorder(type)}`,
        borderRadius: '6px',
        padding: '6px 10px',
        width: NODE_W,
        minHeight: NODE_H,
      },
    }
  })

  const edges = graph.edges.map((e, index) => ({
    id: `e-${index}`,
    source: e.source,
    target: e.target,
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#484f58' },
    style: { stroke: '#484f58', strokeWidth: 1.5 },
  }))

  return { nodes, edges, typeMap }
}

export default function GraphView({ graph }) {
  const { nodes, edges, typeMap } = useMemo(() => buildFlowData(graph), [graph])

  if (nodes.length === 0) {
    return (
      <div style={{ border: '1px solid #30363d', borderRadius: '8px', padding: '2rem', color: '#7d8590', textAlign: 'center', background: '#161b22' }}>
        No nodes in graph.
      </div>
    )
  }

  return (
    <div style={{ border: '1px solid #30363d', borderRadius: '8px', overflow: 'hidden', height: 600, background: '#0d1117' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        minZoom={0.05}
        colorMode="dark"
      >
        <Background color="#21262d" gap={24} size={1} />
        <Controls />
        <MiniMap
          nodeColor={n => minimapColor(n.data?.type || '')}
          maskColor="rgba(13,17,23,0.55)"
          style={{ background: '#161b22' }}
        />
      </ReactFlow>
    </div>
  )
}
