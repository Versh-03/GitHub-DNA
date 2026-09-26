/**
 * GraphView — renders the dependency graph using @xyflow/react.
 *
 * Layout strategy:
 *   1. Find all weakly-connected components from the edge list.
 *   2. Components with ≥2 nodes get a dagre TB (hierarchical) layout,
 *      stacked vertically with generous spacing.
 *   3. Truly isolated nodes (no edges at all) are placed in a compact
 *      grid below all the dagre components — never in a single long row.
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

// ── Sizing constants ──────────────────────────────────────────────────────────
// These are used both for the React Flow node style AND passed to dagre so its
// spacing calculations match the actual rendered dimensions exactly.
const NODE_W    = 240   // rendered node width  (up from 200)
const NODE_H    = 80    // rendered node height (up from 70; accounts for padding + wrapper)
const NODESEP   = 120   // clear px gap between sibling nodes in the same rank
const RANKSEP   = 140   // clear px gap between ranks (rows)
const GRID_COLS = 5     // columns in the isolated-node grid
const GRID_GAP  = 30    // px gap between cells in the isolate grid

// ── Color helpers (dark theme, unchanged) ────────────────────────────────────

function nodeColor(type) {
  switch (type) {
    case 'source': return '#1c3a5e'
    case 'test':   return '#14412e'
    case 'docs':   return '#3d3000'
    case 'config': return '#2e1f4f'
    default:       return '#1e2329'
  }
}

function nodeBorder(type) {
  switch (type) {
    case 'source': return '#388bfd'
    case 'test':   return '#3fb950'
    case 'docs':   return '#d29922'
    case 'config': return '#a371f7'
    default:       return '#484f58'
  }
}

function minimapColor(type) {
  switch (type) {
    case 'source': return '#1f6feb'
    case 'test':   return '#238636'
    case 'docs':   return '#9e6a03'
    case 'config': return '#6e40c9'
    default:       return '#30363d'
  }
}

// ── Connected-component detection (Union-Find) ────────────────────────────────

function findComponents(nodeIds, edges) {
  const parent = {}
  nodeIds.forEach(id => { parent[id] = id })

  function find(x) {
    if (parent[x] !== x) parent[x] = find(parent[x])
    return parent[x]
  }
  function union(a, b) {
    parent[find(a)] = find(b)
  }

  edges.forEach(e => {
    if (parent[e.source] !== undefined && parent[e.target] !== undefined) {
      union(e.source, e.target)
    }
  })

  // Group by root
  const groups = {}
  nodeIds.forEach(id => {
    const root = find(id)
    if (!groups[root]) groups[root] = []
    groups[root].push(id)
  })

  return Object.values(groups)
}

// ── Dagre layout for a single component ──────────────────────────────────────

/**
 * Run dagre on one component's nodes+edges and return positions
 * as top-left corners (React Flow convention), offset by (offsetX, offsetY).
 */
function layoutComponent(componentNodeIds, allNodes, allEdges, offsetX, offsetY) {
  const nodeSet = new Set(componentNodeIds)

  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: 'TB',
    nodesep: NODESEP,
    ranksep: RANKSEP,
    edgesep: 30,
    marginx: 40,
    marginy: 40,
  })
  g.setDefaultEdgeLabel(() => ({}))

  componentNodeIds.forEach(id => {
    g.setNode(id, { width: NODE_W, height: NODE_H })
  })

  allEdges.forEach(e => {
    if (nodeSet.has(e.source) && nodeSet.has(e.target)) {
      g.setEdge(e.source, e.target)
    }
  })

  dagre.layout(g)

  const positions = {}
  componentNodeIds.forEach(id => {
    const n = g.node(id)
    positions[id] = {
      x: offsetX + n.x - NODE_W / 2,
      y: offsetY + n.y - NODE_H / 2,
    }
  })

  // Return positions + the bounding-box height of this component
  const graphInfo = g.graph()
  return { positions, height: graphInfo.height + 2 * 40 }
}

// ── Full layout: dagre components + isolate grid ──────────────────────────────

function buildLayout(rawNodes, rawEdges) {
  const nodeIds = rawNodes.map(n => n.id)
  const components = findComponents(nodeIds, rawEdges)

  // Separate components that have real edges from true singletons
  const edgeNodeSet = new Set()
  rawEdges.forEach(e => { edgeNodeSet.add(e.source); edgeNodeSet.add(e.target) })

  const connectedComponents = components.filter(c =>
    c.some(id => edgeNodeSet.has(id))
  )
  const isolatedIds = components
    .filter(c => c.every(id => !edgeNodeSet.has(id)))
    .flat()

  const allPositions = {}
  let currentY = 0

  // ── 1. Lay out each connected component with dagre, stacked top-to-bottom ──
  connectedComponents.forEach(comp => {
    const { positions, height } = layoutComponent(
      comp, rawNodes, rawEdges, 0, currentY
    )
    Object.assign(allPositions, positions)
    currentY += height + RANKSEP   // gap between consecutive components
  })

  // ── 2. Place isolated nodes in a grid below the dagre area ─────────────────
  const cellW = NODE_W + GRID_GAP
  const cellH = NODE_H + GRID_GAP
  // Add extra breathing room before the grid starts
  const gridStartY = currentY + (isolatedIds.length > 0 && connectedComponents.length > 0
    ? RANKSEP
    : 0)

  isolatedIds.forEach((id, i) => {
    const col = i % GRID_COLS
    const row = Math.floor(i / GRID_COLS)
    allPositions[id] = {
      x: col * cellW,
      y: gridStartY + row * cellH,
    }
  })

  return allPositions
}

// ── React Flow node/edge builders ─────────────────────────────────────────────

function buildFlowData(graph) {
  const positions = buildLayout(graph.nodes, graph.edges)

  const nodes = graph.nodes.map(n => {
    const label = n.id.split('/').pop()
    const pos   = positions[n.id] || { x: 0, y: 0 }
    const type  = n.type
    return {
      id: n.id,
      position: { x: pos.x, y: pos.y },
      data: {
        label: (
          <div style={{ fontSize: '12px', lineHeight: 1.5 }}>
            <div style={{
              fontWeight: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: `${NODE_W - 24}px`,
              color: '#e6edf3',
            }}>
              {label}
            </div>
            <div style={{ color: '#7d8590', marginTop: '2px' }}>
              {type} · {n.commit_count} commits
            </div>
          </div>
        ),
        type,
      },
      style: {
        background: nodeColor(type),
        border: `1px solid ${nodeBorder(type)}`,
        borderRadius: '7px',
        padding: '8px 12px',
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
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: '#58a6ff' },
    style: { stroke: '#58a6ff', strokeWidth: 2.5 },
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
      height: 680,
      background: '#0d1117',
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.08 }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        minZoom={0.04}
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
