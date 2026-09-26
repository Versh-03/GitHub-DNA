/**
 * GraphView — renders the dependency graph using @xyflow/react.
 *
 * Layout: dagre directed-graph layout (top → bottom).
 *   - Connected files are placed near each other.
 *   - Dependency direction flows top-to-bottom.
 *   - dagre minimises edge crossings automatically.
 *   - Isolated nodes are tucked below the main graph.
 */

import { useMemo } from 'react'
import dagre from 'dagre'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

// Node dimensions (must match what dagre uses for spacing)
const NODE_W = 200
const NODE_H = 52

/** Dark-theme node fill per file_type */
function nodeColor(type) {
  switch (type) {
    case 'source': return '#1c3a5e'
    case 'test':   return '#14412e'
    case 'docs':   return '#3d3000'
    case 'config': return '#2e1f4f'
    default:       return '#1e2329'
  }
}

/** Accent border per file_type */
function nodeBorder(type) {
  switch (type) {
    case 'source': return '#388bfd'
    case 'test':   return '#3fb950'
    case 'docs':   return '#d29922'
    case 'config': return '#a371f7'
    default:       return '#484f58'
  }
}

/** Minimap highlight colour per file_type */
function minimapColor(type) {
  switch (type) {
    case 'source': return '#1f6feb'
    case 'test':   return '#238636'
    case 'docs':   return '#9e6a03'
    case 'config': return '#6e40c9'
    default:       return '#30363d'
  }
}

// ── Dagre layout ─────────────────────────────────────────────────────────────

/**
 * Run dagre on the raw node/edge lists and return a map of
 * nodeId → { x, y } using the node's top-left corner so React Flow
 * can use the values directly.
 */
function dagreLayout(rawNodes, rawEdges) {
  const g = new dagre.graphlib.Graph()

  g.setGraph({
    rankdir: 'TB',    // top → bottom (dependency direction)
    align: 'UL',      // align to upper-left within each rank
    nodesep: 40,      // horizontal gap between nodes in the same rank
    ranksep: 60,      // vertical gap between ranks
    edgesep: 15,
    marginx: 20,
    marginy: 20,
  })

  g.setDefaultEdgeLabel(() => ({}))

  rawNodes.forEach(n => {
    g.setNode(n.id, { width: NODE_W, height: NODE_H })
  })

  rawEdges.forEach(e => {
    // Guard: dagre crashes if source/target not in graph
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target)
    }
  })

  dagre.layout(g)

  const positions = {}
  rawNodes.forEach(n => {
    const node = g.node(n.id)
    // dagre gives the centre; React Flow wants the top-left corner
    positions[n.id] = {
      x: node.x - NODE_W / 2,
      y: node.y - NODE_H / 2,
    }
  })

  return positions
}

// ── Main builder ─────────────────────────────────────────────────────────────

function buildFlowData(graph) {
  const positions = dagreLayout(graph.nodes, graph.edges)

  const nodes = graph.nodes.map(n => {
    const label = n.id.split('/').pop()
    const pos   = positions[n.id] || { x: 0, y: 0 }
    const type  = n.type
    return {
      id: n.id,
      position: { x: pos.x, y: pos.y },
      data: {
        label: (
          <div style={{ fontSize: '11px', lineHeight: 1.4 }}>
            <div style={{
              fontWeight: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: '176px',
              color: '#e6edf3',
            }}>
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

  const edges = graph.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    type: 'smoothstep',
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#6e7681' },
    style: { stroke: '#6e7681', strokeWidth: 1.5 },
  }))

  return { nodes, edges }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function GraphView({ graph }) {
  const { nodes, edges } = useMemo(() => buildFlowData(graph), [graph])

  if (nodes.length === 0) {
    return (
      <div style={{
        border: '1px solid #30363d',
        borderRadius: '8px',
        padding: '2rem',
        color: '#7d8590',
        textAlign: 'center',
        background: '#161b22',
      }}>
        No nodes in graph.
      </div>
    )
  }

  return (
    <div style={{
      border: '1px solid #30363d',
      borderRadius: '8px',
      overflow: 'hidden',
      height: 620,
      background: '#0d1117',
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.1 }}
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
