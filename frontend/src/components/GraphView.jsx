/**
 * GraphView — renders the dependency graph using @xyflow/react.
 *
 * Layout strategy:
 *   1. Find all weakly-connected components from the edge list.
 *   2. Components with ≥2 nodes get a dagre TB (hierarchical) layout,
 *      stacked vertically with generous spacing.
 *   3. Truly isolated nodes (no edges at all) are placed in a compact
 *      grid below all the dagre components — never in a single long row.

*
 * File-detail panel:
 *   Clicking a node opens a floating panel anchored near the node inside
 *   the graph container. It is dismissed by the close button or by
 *   clicking another node.
 */

import { useMemo, useCallback, useState } from 'react'
import dagre from 'dagre'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import FileDetailPanel from './FileDetailPanel.jsx'

// ── Sizing constants ──────────────────────────────────────────────────────────
const NODE_W    = 240
const NODE_H    = 80
const NODESEP   = 120
const RANKSEP   = 140
const GRID_COLS = 5
const GRID_GAP  = 30

// Panel dimensions — used only for clamping so it stays within the container
const PANEL_W   = 300
const PANEL_H   = 480  // generous estimate; actual height varies
const CONTAINER_H = 680

// ── Color helpers (dark theme) ────────────────────────────────────────────────

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
  function union(a, b) { parent[find(a)] = find(b) }

  edges.forEach(e => {
    if (parent[e.source] !== undefined && parent[e.target] !== undefined) {
      union(e.source, e.target)
    }
  })

  const groups = {}
  nodeIds.forEach(id => {
    const root = find(id)
    if (!groups[root]) groups[root] = []
    groups[root].push(id)
  })

  return Object.values(groups)
}

// ── Dagre layout for a single component ──────────────────────────────────────

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

  const graphInfo = g.graph()
  return { positions, height: graphInfo.height + 2 * 40 }
}

// ── Full layout ───────────────────────────────────────────────────────────────

function buildLayout(rawNodes, rawEdges) {
  const nodeIds    = rawNodes.map(n => n.id)
  const components = findComponents(nodeIds, rawEdges)

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

  connectedComponents.forEach(comp => {
    const { positions, height } = layoutComponent(comp, rawNodes, rawEdges, 0, currentY)
    Object.assign(allPositions, positions)
    currentY += height + RANKSEP
  })

  const cellW      = NODE_W + GRID_GAP
  const cellH      = NODE_H + GRID_GAP
  const gridStartY = currentY + (isolatedIds.length > 0 && connectedComponents.length > 0
    ? RANKSEP : 0)

  isolatedIds.forEach((id, i) => {
    allPositions[id] = {
      x: (i % GRID_COLS) * cellW,
      y: gridStartY + Math.floor(i / GRID_COLS) * cellH,
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

// ── Edge maps ─────────────────────────────────────────────────────────────────

function buildEdgeMaps(rawEdges) {
  const deps   = {}
  const usedBy = {}
  rawEdges.forEach(e => {
    if (!deps[e.source])   deps[e.source]   = []
    if (!usedBy[e.target]) usedBy[e.target] = []
    deps[e.source].push(e.target)
    usedBy[e.target].push(e.source)
  })
  return { deps, usedBy }
}

// ── Inner component (needs useReactFlow, so must live inside ReactFlowProvider) ──

function GraphInner({ graph }) {
  const { nodes, edges } = useMemo(() => buildFlowData(graph), [graph])
  const { deps, usedBy } = useMemo(() => buildEdgeMaps(graph.edges), [graph.edges])
  const rawNodeMap       = useMemo(() => {
    const m = {}
    graph.nodes.forEach(n => { m[n.id] = n })
    return m
  }, [graph.nodes])

  const { getViewport } = useReactFlow()

  // { detail: {node,deps,usedBy}, panelPos: {top,left} } | null
  const [selection, setSelection] = useState(null)

  const handleNodeClick = useCallback((_event, flowNode) => {
    const raw = rawNodeMap[flowNode.id]
    if (!raw) return

    // Convert node's graph-space top-left corner → pixel position inside
    // the container using the current viewport (zoom + pan).
    const vp   = getViewport()
    const zoom = vp.zoom

    // flowNode.position is the top-left of the node in graph space
    const nodeScreenX = flowNode.position.x * zoom + vp.x
    const nodeScreenY = flowNode.position.y * zoom + vp.y

    // Prefer placing the panel to the right of the node; fall back to left
    const offsetX = 16
    const nodeRight = nodeScreenX + NODE_W * zoom + offsetX
    const left = nodeRight + PANEL_W > window.innerWidth
      ? Math.max(4, nodeScreenX - PANEL_W - offsetX)
      : nodeRight

    // Place panel just below the node top, clamped within the container
    const top = Math.min(
      Math.max(4, nodeScreenY),
      CONTAINER_H - PANEL_H - 4,
    )

    setSelection({
      detail: {
        node:   raw,
        deps:   deps[raw.id]   || [],
        usedBy: usedBy[raw.id] || [],
      },
      panelPos: { top, left },
    })
  }, [rawNodeMap, deps, usedBy, getViewport])

  const handlePaneClick = useCallback(() => {
    setSelection(null)
  }, [])

  return (
    <>
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
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
      >
        <Background color="#21262d" gap={24} size={1} />
        <Controls />
        <MiniMap
          nodeColor={n => minimapColor(n.data?.type || '')}
          maskColor="rgba(13,17,23,0.55)"
          style={{ background: '#161b22' }}
        />
      </ReactFlow>

      {selection && (
        <div style={{
          position: 'absolute',
          top:      selection.panelPos.top,
          left:     selection.panelPos.left,
          width:    PANEL_W,
          zIndex:   10,
          // Prevent the panel from being wider than the container
          maxWidth: 'calc(100% - 8px)',
        }}>
          <FileDetailPanel
            node={selection.detail.node}
            deps={selection.detail.deps}
            usedBy={selection.detail.usedBy}
            onClose={() => setSelection(null)}
          />
        </div>
      )}
    </>
  )
}

// ── Public component ──────────────────────────────────────────────────────────

export default function GraphView({ graph }) {
  if (graph.nodes.length === 0) {
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
      position: 'relative',       // anchor for the absolute-positioned panel
      border: '1px solid #30363d',
      borderRadius: '8px',
      overflow: 'hidden',
      height: CONTAINER_H,
      background: '#0d1117',
    }}>
      <ReactFlowProvider>
        <GraphInner graph={graph} />
      </ReactFlowProvider>
    </div>
  )
}
