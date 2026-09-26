/**
 * GraphView — renders the dependency graph using @xyflow/react.
 *
 * Layout: fixed grid.  Nodes are placed left-to-right, top-to-bottom in the
 * order they arrive from the API — no layout library required.
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

// Grid constants (px)
const CELL_W = 220
const CELL_H = 80
const COLS   = 6   // nodes per row

/** Pick a background colour for each file_type */
function nodeColor(type) {
  switch (type) {
    case 'source': return '#dbeafe'   // blue-100
    case 'test':   return '#dcfce7'   // green-100
    case 'docs':   return '#fef9c3'   // yellow-100
    case 'config': return '#ede9fe'   // violet-100
    default:       return '#f3f4f6'   // gray-100
  }
}

/** Convert the raw graph payload from /analyze into React Flow node/edge arrays */
function buildFlowData(graph) {
  const nodes = graph.nodes.map((n, index) => {
    const col = index % COLS
    const row = Math.floor(index / COLS)
    // Short label: last path segment
    const label = n.id.split('/').pop()
    return {
      id: n.id,
      position: { x: col * CELL_W, y: row * CELL_H },
      data: {
        label: (
          <div style={{ fontSize: '11px', lineHeight: 1.4 }}>
            <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
              {label}
            </div>
            <div style={{ color: '#57606a' }}>
              {n.type} · {n.commit_count} commits
            </div>
          </div>
        ),
      },
      style: {
        background: nodeColor(n.type),
        border: '1px solid #e5e7eb',
        borderRadius: '6px',
        padding: '6px 10px',
        fontSize: '11px',
        width: 200,
      },
    }
  })

  const edges = graph.edges.map((e, index) => ({
    id: `e-${index}`,
    source: e.source,
    target: e.target,
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#57606a' },
    style: { stroke: '#57606a', strokeWidth: 1.5 },
  }))

  return { nodes, edges }
}

export default function GraphView({ graph }) {
  const { nodes, edges } = useMemo(() => buildFlowData(graph), [graph])

  if (nodes.length === 0) {
    return (
      <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '2rem', color: '#57606a', textAlign: 'center' }}>
        No nodes in graph.
      </div>
    )
  }

  // Compute canvas height: enough rows to fit all nodes + some padding
  const rows = Math.ceil(nodes.length / COLS)
  const height = Math.max(500, rows * CELL_H + 100)

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden', height }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        minZoom={0.1}
      >
        <Background color="#e5e7eb" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={n => nodeColor(n.style?.background ? '' : n.data?.type)}
          maskColor="rgba(0,0,0,0.05)"
        />
      </ReactFlow>
    </div>
  )
}
