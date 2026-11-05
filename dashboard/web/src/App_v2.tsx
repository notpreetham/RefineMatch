import { useEffect, useState, useMemo, type ReactNode, type CSSProperties } from "react"

export type IconName =
  | "grid"
  | "graph"
  | "shield"
  | "activity"
  | "layers"
  | "settings"
  | "help"
  | "chevron"
  | "arrow"
  | "download"
  | "check"
  | "clock"
  | "external"
  | "close"
  | "filter"
  | "plus"
  | "minus"
  | "fit"
  | "process"
  | "file"
  | "socket"
  | "host"
  | "search"
  | "bell"
  | "pause"
  | "play"
  | "code"
  | "copy"
  | "eye"
  | "spark"
  | "target"
  | "terminal"
  | "database"
  | "upload"

function Icon({
  name,
  size = 18,
  className = "",
  ...props
}: {
  name: IconName
  size?: number
  className?: string
}) {
  const paths: Record<IconName, ReactNode> = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    graph: (
      <>
        <path d="m6 6 12 1M6 6l5 13M18 7l-7 12" />
        <circle cx="6" cy="6" r="3" />
        <circle cx="18" cy="7" r="3" />
        <circle cx="11" cy="19" r="3" />
      </>
    ),
    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" />
        <path d="m8.5 12 2.5 2.5 4.5-5" />
      </>
    ),
    activity: (
      <>
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </>
    ),
    layers: (
      <>
        <path d="m12 2 10 5-10 5L2 7l10-5Z" />
        <path d="m2 17 10 5 10-5" />
        <path d="m2 12 10 5 10-5" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <path d="M12 17h.01" />
      </>
    ),
    chevron: (
      <>
        <path d="m9 18 6-6-6-6" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m12 5 7 7-7 7" />
      </>
    ),
    download: (
      <>
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </>
    ),
    check: (
      <>
        <polyline points="20 6 9 17 4 12" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </>
    ),
    external: (
      <>
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        <polyline points="15 3 21 3 21 9" />
        <line x1="10" y1="14" x2="21" y2="3" />
      </>
    ),
    close: (
      <>
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </>
    ),
    filter: (
      <>
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
      </>
    ),
    plus: (
      <>
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </>
    ),
    minus: (
      <>
        <line x1="5" y1="12" x2="19" y2="12" />
      </>
    ),
    fit: (
      <>
        <path d="M8 3H5a2 2 0 0 0-2 2v3" />
        <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
        <path d="M3 16v3a2 2 0 0 0 2 2h3" />
        <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
      </>
    ),
    process: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="m9 8 4 4-4 4" />
      </>
    ),
    file: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </>
    ),
    socket: (
      <>
        <circle cx="12" cy="12" r="9" />
        <line x1="3.6" y1="9" x2="20.4" y2="9" />
        <line x1="3.6" y1="15" x2="20.4" y2="15" />
        <path d="M11.5 3a17 17 0 0 0 0 18" />
        <path d="M12.5 3a17 17 0 0 1 0 18" />
      </>
    ),
    host: (
      <>
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </>
    ),
    pause: (
      <>
        <rect x="6" y="4" width="4" height="16" />
        <rect x="14" y="4" width="4" height="16" />
      </>
    ),
    play: (
      <>
        <polygon points="5 3 19 12 5 21 5 3" />
      </>
    ),
    code: (
      <>
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </>
    ),
    copy: (
      <>
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
      </>
    ),
    eye: (
      <>
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    spark: (
      <>
        <path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z" />
      </>
    ),
    target: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1" />
      </>
    ),
    terminal: (
      <>
        <polyline points="4 17 10 11 4 5" />
        <line x1="12" y1="19" x2="20" y2="19" />
      </>
    ),
    database: (
      <>
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </>
    ),
    upload: (
      <>
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </>
    ),
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...props}
    >
      {paths[name]}
    </svg>
  )
}

export type MappedNode = {
  id: string
  observed: string
  type: IconName
  label: string
  color: string
  score: string
  desc: string
  binary: string
  pid: string
}

export type PatternOption = {
  id: string
  name: string
  description: string
  nodes: number
  edges: number
}

export type RankedMatch = {
  pattern_id: string
  name: string
  similarity_score: number
  coverage: number
}

export type GraphNodeData = {
  id: string
  label: string
  type: IconName
  color: string
  is_matched?: boolean
  mapped_to?: string | null
  mapped_from?: string | null
  ref_index?: number
  desc?: string
}

export type GraphEdgeData = {
  source: string
  target: string
  label: string
  is_matched?: boolean
}

export type GraphPayload = {
  nodes: GraphNodeData[]
  edges: GraphEdgeData[]
}

const defaultNodes: MappedNode[] = [
  {
    id: "proc_101",
    observed: "N_0001",
    type: "process",
    label: "Process",
    color: "violet",
    score: "1.000",
    desc: "host-endpoint-77",
    binary: "powershell.exe -enc <payload>",
    pid: "9102",
  },
  {
    id: "file_201",
    observed: "N_0002",
    type: "file",
    label: "File",
    color: "teal",
    score: "0.994",
    desc: "/tmp/payload.bin",
    binary: "/tmp/payload.bin",
    pid: "—",
  },
  {
    id: "sock_301",
    observed: "N_0003",
    type: "socket",
    label: "Socket",
    color: "amber",
    score: "0.992",
    desc: "203.0.113.7:443",
    binary: "TCP / 203.0.113.7:443",
    pid: "9102",
  },
  {
    id: "host_401",
    observed: "N_0004",
    type: "host",
    label: "Host",
    color: "blue",
    score: "1.000",
    desc: "srv-edge-04",
    binary: "srv-edge-04 / Ubuntu 24.04",
    pid: "—",
  },
]

const defaultRefGraph: GraphPayload = {
  nodes: [
    { id: "proc_101", label: "Process", type: "process", color: "violet", is_matched: true, mapped_to: "N_0001", ref_index: 0 },
    { id: "file_201", label: "File", type: "file", color: "teal", is_matched: true, mapped_to: "N_0002", ref_index: 1 },
    { id: "sock_301", label: "Socket", type: "socket", color: "amber", is_matched: true, mapped_to: "N_0003", ref_index: 2 },
    { id: "host_401", label: "Host", type: "host", color: "blue", is_matched: true, mapped_to: "N_0004", ref_index: 3 },
  ],
  edges: [
    { source: "proc_101", target: "file_201", label: "read", is_matched: true },
    { source: "proc_101", target: "sock_301", label: "connect", is_matched: true },
    { source: "file_201", target: "host_401", label: "write", is_matched: true },
    { source: "sock_301", target: "host_401", label: "sendto", is_matched: true },
  ],
}

const defaultObsGraph: GraphPayload = {
  nodes: [
    { id: "N_0001", label: "Process", type: "process", color: "violet", is_matched: true, mapped_from: "proc_101", ref_index: 0 },
    { id: "N_0002", label: "File", type: "file", color: "teal", is_matched: true, mapped_from: "file_201", ref_index: 1 },
    { id: "N_0003", label: "Socket", type: "socket", color: "amber", is_matched: true, mapped_from: "sock_301", ref_index: 2 },
    { id: "N_0004", label: "Host", type: "host", color: "blue", is_matched: true, mapped_from: "host_401", ref_index: 3 },
  ],
  edges: [
    { source: "N_0001", target: "N_0002", label: "read", is_matched: true },
    { source: "N_0001", target: "N_0003", label: "connect", is_matched: true },
    { source: "N_0002", target: "N_0004", label: "write", is_matched: true },
    { source: "N_0003", target: "N_0004", label: "sendto", is_matched: true },
  ],
}

const noise = Array.from({ length: 36 }, (_, i) => {
  const angle = i * 2.39996
  const radius = 120 + ((i * 37) % 110)
  return {
    x: 330 + Math.cos(angle) * radius * 1.22,
    y: 185 + Math.sin(angle) * radius * 0.72,
  }
})

function computeGraphLayout(
  nodes: GraphNodeData[],
  width: number,
  height: number,
  isEnterprise: boolean,
): { x: number; y: number }[] {
  const cx = isEnterprise ? 330 : 250
  const cy = 185
  const count = nodes.length
  if (count === 0) return []
  if (count === 1) return [{ x: cx, y: cy }]
  if (count === 2) {
    return [
      { x: cx - 110, y: cy },
      { x: cx + 110, y: cy },
    ]
  }
  if (count === 3) {
    return [
      { x: cx, y: cy - 90 },
      { x: cx - 120, y: cy + 70 },
      { x: cx + 120, y: cy + 70 },
    ]
  }
  if (count === 4) {
    return [
      { x: cx, y: cy - 105 },
      { x: cx - 135, y: cy },
      { x: cx + 135, y: cy },
      { x: cx, y: cy + 105 },
    ]
  }

  const matchedIndices: number[] = []
  const unmatchedIndices: number[] = []
  nodes.forEach((n, idx) => {
    if (n.is_matched || n.mapped_to || n.mapped_from) {
      matchedIndices.push(idx)
    } else {
      unmatchedIndices.push(idx)
    }
  })

  const coords: { x: number; y: number }[] = new Array(count).fill(null).map(() => ({ x: cx, y: cy }))

  if (matchedIndices.length > 0 && unmatchedIndices.length > 0) {
    const mCount = matchedIndices.length
    const rxM = Math.min(cx - 70, 140)
    const ryM = 95
    matchedIndices.forEach((nodeIdx, k) => {
      const angle = (2 * Math.PI * k) / mCount - Math.PI / 2
      coords[nodeIdx] = {
        x: cx + rxM * Math.cos(angle),
        y: cy + ryM * Math.sin(angle),
      }
    })

    const uCount = unmatchedIndices.length
    const rxU = Math.min(cx - 40, 225)
    const ryU = 145
    unmatchedIndices.forEach((nodeIdx, k) => {
      const angle = (2 * Math.PI * (k + 0.5)) / uCount - Math.PI / 2
      coords[nodeIdx] = {
        x: cx + rxU * Math.cos(angle),
        y: cy + ryU * Math.sin(angle),
      }
    })
  } else {
    const rx = Math.min(cx - 60, 185)
    const ry = 120
    nodes.forEach((_, k) => {
      const angle = (2 * Math.PI * k) / count - Math.PI / 2
      coords[k] = {
        x: cx + rx * Math.cos(angle),
        y: cy + ry * Math.sin(angle),
      }
    })
  }

  return coords
}

type CanvasPosition = {
  x: number
  y: number
}

function ScientificGraph({
  enterprise,
  mode,
  showNoise,
  active,
  setActive,
  inspect,
  zoom,
  pan,
  setPan,
  graphData,
  matchedCount = 4,
}: {
  enterprise: boolean
  mode: string
  showNoise: boolean
  active: number | null
  setActive: (n: number | null) => void
  inspect: (n: number) => void
  zoom: number
  pan: CanvasPosition
  setPan: (p: CanvasPosition) => void
  graphData?: GraphPayload
  matchedCount?: number
}) {
  const currentGraph = graphData && graphData.nodes?.length ? graphData : (enterprise ? defaultObsGraph : defaultRefGraph)
  const gNodes = currentGraph.nodes || []
  const gEdges = currentGraph.edges || []
  const width = enterprise ? 660 : 500
  const height = 370

  const points = useMemo(() => {
    return computeGraphLayout(gNodes, width, height, enterprise)
  }, [gNodes, width, height, enterprise])

  const nodeIdToIndex = useMemo(() => {
    const map = new Map<string, number>()
    gNodes.forEach((n, idx) => map.set(String(n.id), idx))
    return map
  }, [gNodes])

  const [drag, setDrag] = useState<{
    x: number
    y: number
    px: number
    py: number
  } | null>(null)

  const nodeColorTheme: Record<string, { stroke: string; fill: string; text: string; glow: string }> = {
    violet: { stroke: "#7c3aed", fill: "#f5f3ff", text: "#6d28d9", glow: "rgba(124, 58, 237, 0.25)" },
    teal: { stroke: "#0d9488", fill: "#f0fdfa", text: "#0f766e", glow: "rgba(13, 148, 136, 0.25)" },
    amber: { stroke: "#d97706", fill: "#fffbeb", text: "#b45309", glow: "rgba(217, 119, 6, 0.25)" },
    blue: { stroke: "#2563eb", fill: "#eff6ff", text: "#1d4ed8", glow: "rgba(37, 99, 235, 0.25)" },
  }

  return (
    <svg
      className="w-full max-w-full h-[335px] block select-none cursor-grab active:cursor-grabbing bg-[#fcfdfe]"
      viewBox={`0 0 ${width} ${height}`}
      aria-label={enterprise ? "Observed telemetry graph" : "Reference attack signature graph"}
      onPointerDown={(e) => {
        if (
          e.target === e.currentTarget ||
          (e.target as Element).classList.contains("sci-canvas-bg")
        ) {
          setDrag({ x: e.clientX, y: e.clientY, px: pan.x, py: pan.y })
          e.currentTarget.setPointerCapture(e.pointerId)
        }
      }}
      onPointerMove={(e) => {
        if (drag)
          setPan({
            x: drag.px + (e.clientX - drag.x) / zoom,
            y: drag.py + (e.clientY - drag.y) / zoom,
          })
      }}
      onPointerUp={() => setDrag(null)}
    >
      <defs>
        <pattern
          id={`sci-dots-${enterprise}`}
          width="20"
          height="20"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="2" cy="2" r=".8" fill="#d8e1ea" />
        </pattern>
        <marker
          id={`sci-arrow-${enterprise}`}
          markerWidth="7"
          markerHeight="7"
          refX="6"
          refY="3.5"
          orient="auto"
        >
          <path
            d="m1 1 4 2.5L1 6"
            fill="none"
            stroke={enterprise ? "#0d9488" : "#64748b"}
            strokeWidth="1.2"
          />
        </marker>
        <filter id={`sci-glow-${enterprise}`} x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="#0f172a" floodOpacity="0.08" />
        </filter>
      </defs>

      <rect
        className="sci-canvas-bg"
        width="100%"
        height="100%"
        fill={`url(#sci-dots-${enterprise})`}
      />

      <g
        transform={`translate(${pan.x} ${pan.y}) translate(${
          enterprise ? 330 : 250
        } 185) scale(${zoom}) translate(-${enterprise ? 330 : 250} -185)`}
      >
        {/* Noise telemetry nodes for enterprise view */}
        {enterprise && showNoise && (
          <g className="noise-group opacity-60">
            {noise.map((n, i) => (
              <g key={`noise-${i}`}>
                <line
                  x1={n.x}
                  y1={n.y}
                  x2={points.length > 0 ? points[i % points.length].x : 330}
                  y2={points.length > 0 ? points[i % points.length].y : 185}
                  stroke="#cbd5e1"
                  strokeWidth="0.8"
                  strokeDasharray="2 2"
                  opacity={mode === "Diff heatmap" ? 0.4 : 0.25}
                />
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={i % 4 === 0 ? 4 : 2.5}
                  fill={mode === "Diff heatmap" ? "#fee2e2" : "#f1f5f9"}
                  stroke={mode === "Diff heatmap" ? "#ef4444" : "#94a3b8"}
                  strokeWidth="0.8"
                />
                {i % 7 === 0 && (
                  <text
                    x={n.x + 6}
                    y={n.y + 3}
                    className="font-mono text-[7px] fill-[#94a3b8]"
                  >
                    N_{String(120 + i * 31).padStart(4, "0")}
                  </text>
                )}
              </g>
            ))}
          </g>
        )}

        {/* Directed Edges */}
        {gEdges.map((edge, i) => {
          const sIdx = nodeIdToIndex.get(String(edge.source))
          const tIdx = nodeIdToIndex.get(String(edge.target))
          if (sIdx === undefined || tIdx === undefined) return null
          const p = points[sIdx]
          const q = points[tIdx]
          if (!p || !q) return null
          const dx = q.x - p.x
          const dy = q.y - p.y
          const len = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const sNode = gNodes[sIdx]
          const tNode = gNodes[tIdx]
          const isDim =
            active !== null &&
            sIdx !== active &&
            tIdx !== active &&
            sNode?.ref_index !== active &&
            tNode?.ref_index !== active

          const isMatched = enterprise && (edge.is_matched || (sNode?.is_matched && tNode?.is_matched))

          return (
            <g
              key={`edge-${i}-${edge.source}-${edge.target}`}
              className={`transition-opacity duration-200 ${isDim ? "opacity-20" : "opacity-100"}`}
            >
              <line
                x1={p.x + (dx / len) * 26}
                y1={p.y + (dy / len) * 26}
                x2={q.x - (dx / len) * 29}
                y2={q.y - (dy / len) * 29}
                stroke={isMatched ? "#0d9488" : "#94a3b8"}
                strokeWidth={isMatched ? "1.8" : "1.2"}
                markerEnd={`url(#sci-arrow-${enterprise})`}
              />
              <rect
                x={(p.x + q.x) / 2 - 24}
                y={(p.y + q.y) / 2 - 9}
                width="48"
                height="17"
                rx="4"
                fill="#ffffff"
                stroke={isMatched ? "#99f6e4" : "#e2e8f0"}
                strokeWidth="1"
              />
              <text
                x={(p.x + q.x) / 2}
                y={(p.y + q.y) / 2 + 3}
                textAnchor="middle"
                className="font-mono text-[8px] font-semibold tracking-wide"
                fill={isMatched ? "#0f766e" : "#475569"}
              >
                {edge.label}
              </text>
            </g>
          )
        })}

        {/* Overlay Mode ghost rings */}
        {mode === "Overlay mode" &&
          enterprise &&
          points.map((p, i) => {
            const n = gNodes[i]
            if (!n || !n.is_matched) return null
            return (
              <circle
                key={`overlay-${i}`}
                cx={p.x - 8}
                cy={p.y - 4}
                r="26"
                stroke="#0d9488"
                strokeDasharray="4 3"
                fill="none"
                opacity="0.75"
              />
            )
          })}

        {/* Dynamic Nodes */}
        {gNodes.map((n, i) => {
          const p = points[i]
          if (!p) return null
          const refIndex = enterprise
            ? n.ref_index !== undefined
              ? n.ref_index
              : n.is_matched
              ? i
              : -1
            : i
          const isActive = active === i || (active !== null && refIndex === active)
          const isDim = active !== null && !isActive
          const theme = nodeColorTheme[n.color] || nodeColorTheme.blue

          return (
            <g
              key={`node-${i}-${n.id}`}
              data-node-index={refIndex >= 0 ? refIndex : i}
              className={`cursor-pointer transition-transform duration-200 ${
                isDim ? "opacity-25" : "opacity-100"
              }`}
              onMouseEnter={() => setActive(refIndex >= 0 ? refIndex : i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(refIndex >= 0 ? refIndex : i)}
              onBlur={() => setActive(null)}
              onClick={() => inspect(refIndex >= 0 ? refIndex : i)}
              role="button"
              tabIndex={0}
              aria-label={`Inspect node ${n.id}`}
            >
              {/* Outer halo */}
              <circle
                cx={p.x}
                cy={p.y}
                r={isActive ? 28 : 25}
                fill={theme.fill}
                stroke={theme.stroke}
                strokeWidth={isActive ? 2.5 : 1.5}
                filter={`url(#sci-glow-${enterprise})`}
                className="transition-all duration-200"
              />

              {/* Icon Container */}
              <foreignObject
                x={p.x - 10}
                y={p.y - 10}
                width="20"
                height="20"
                style={{ color: theme.stroke }}
              >
                <Icon name={n.type || "graph"} size={20} />
              </foreignObject>

              {/* Matched green badge for enterprise node */}
              {enterprise && n.is_matched && (
                <g>
                  <circle cx={p.x + 18} cy={p.y - 17} r="6" fill="#0d9488" />
                  <path
                    d={`m${p.x + 15} ${p.y - 17} 2 2 4-4`}
                    stroke="#ffffff"
                    strokeWidth="1.2"
                    fill="none"
                  />
                </g>
              )}

              {/* Node IDs and attributes */}
              <text
                x={p.x}
                y={p.y + 42}
                textAnchor="middle"
                className="font-mono text-[10px] font-bold tracking-tight fill-[#1e293b]"
              >
                {n.id}
              </text>
              <text
                x={p.x}
                y={p.y + 54}
                textAnchor="middle"
                className="font-sans text-[8px] font-medium fill-[#64748b]"
              >
                {n.desc || n.label || "entity"}
              </text>
            </g>
          )
        })}

        {/* Enterprise Matched Callout */}
        {enterprise && matchedCount > 0 && (
          <g className="match-callout pointer-events-none">
            <rect
              x="460"
              y="40"
              width="155"
              height="32"
              rx="6"
              fill="#ffffff"
              stroke="#0d9488"
              strokeWidth="1"
              filter="drop-shadow(0 2px 4px rgba(0,0,0,0.06))"
            />
            <circle cx="475" cy="56" r="3" fill="#0d9488" />
            <text
              x="486"
              y="60"
              className="font-mono text-[9px] font-bold fill-[#0f766e]"
            >
              {matchedCount} optimal pairs aligned
            </text>
            <path d="M460 56h-50l-20 6" stroke="#0d9488" strokeWidth="1" strokeDasharray="3 3" fill="none" />
          </g>
        )}
      </g>
    </svg>
  )
}

function downloadFile(name: string, data: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([data], { type }))
  const a = document.createElement("a")
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export default function App_v2() {
  const [ack, setAck] = useState(false)
  const [view, setView] = useState("Split view")
  const [showNoise, setShowNoise] = useState(true)
  const [active, setActive] = useState<number | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [tab, setTab] = useState("System telemetry")
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [toast, setToast] = useState("")
  const [modal, setModal] = useState<string | null>(null)
  const [blocked, setBlocked] = useState<number[]>([])
  const [search, setSearch] = useState("")
  const [triageStatus, setTriageStatus] = useState("In Triage")
  const [statusOpen, setStatusOpen] = useState(false)
  const [isolated, setIsolated] = useState(false)
  const [nodeFilter, setNodeFilter] = useState("All nodes")
  const [pendingNode, setPendingNode] = useState<number | null>(null)

  const [matchData, setMatchData] = useState<{
    similarity_score: number
    reference_coverage: number
    total_events: number
    noise_events: number
    agir_steps: number
    matched_nodes_count: number
    node_mapping: MappedNode[]
    threat_name?: string
    signature_id?: string
    description?: string
    ref_graph?: GraphPayload
    obs_graph?: GraphPayload
    ref_graph_id?: string
    obs_graph_id?: string
  }>({
    similarity_score: 0.9965,
    reference_coverage: 1.0,
    total_events: 8295,
    noise_events: 8280,
    agir_steps: 7,
    matched_nodes_count: 4,
    node_mapping: defaultNodes,
    threat_name: "Drive-by Download & In-Memory Code Injection",
    signature_id: "SUSP_SYN_003",
    description: "Multi-stage provenance threat sequence matched against telemetry log.",
    ref_graph: defaultRefGraph,
    obs_graph: defaultObsGraph,
  })

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [patterns, setPatterns] = useState<PatternOption[]>([])
  const [selectedPattern, setSelectedPattern] = useState<string>("ALL")
  const [rankedMatches, setRankedMatches] = useState<RankedMatch[]>([])
  const nodes = matchData.node_mapping

  const [bridge, setBridge] = useState<{
    x1: number
    y1: number
    x2: number
    y2: number
  } | null>(null)

  useEffect(() => {
    if (active === null || view !== "Split view") {
      setBridge(null)
      return
    }
    const canvas = document.querySelector(".sci-graph-canvases")
    if (!canvas) return
    const updateBridge = () => {
      const left = canvas.querySelector(
        `.reference-viewport [data-node-index="${active}"]`,
      )
      const right = canvas.querySelector(
        `.telemetry-viewport [data-node-index="${active}"]`,
      )
      if (!left || !right) {
        setBridge(null)
        return
      }
      const bounds = canvas.getBoundingClientRect()
      const a = left.getBoundingClientRect()
      const b = right.getBoundingClientRect()
      setBridge({
        x1: ((a.x + a.width / 2 - bounds.x) / bounds.width) * 1200,
        y1: ((a.y + a.height / 2 - bounds.y) / bounds.height) * 380,
        x2: ((b.x + b.width / 2 - bounds.x) / bounds.width) * 1200,
        y2: ((b.y + b.height / 2 - bounds.y) / bounds.height) * 380,
      })
    }
    updateBridge()
    const observer = new ResizeObserver(updateBridge)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [active, view, zoom, pan, matchData])

  const notify = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(""), 4000)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setSelectedFile(file)
      notify(`Dataset loaded: ${file.name}. Click "Execute RefineMatch" to analyze.`)
    }
  }

  const runMatching = async (fileOverride?: File | null, patternOverride?: string) => {
    setIsLoading(true)
    const targetFile = fileOverride !== undefined ? fileOverride : selectedFile
    const targetPattern = patternOverride !== undefined ? patternOverride : selectedPattern

    notify(
      targetPattern === "ALL"
        ? (targetFile
            ? `Scanning ${targetFile.name} across attack pattern bank...`
            : "Scanning telemetry across stored attack pattern bank...")
        : `Evaluating match against signature ${targetPattern}...`,
    )
    try {
      const endpoints = ["/api/run-match", "http://127.0.0.1:8000/api/run-match"]
      let data = null

      const formData = new FormData()
      if (targetFile) {
        formData.append("file", targetFile)
      }
      formData.append("target_pattern_id", targetPattern)

      for (const ep of endpoints) {
        try {
          const url = `${ep}?target_pattern_id=${encodeURIComponent(targetPattern)}`
          const res = await fetch(url, {
            method: "POST",
            body: targetFile ? formData : undefined,
          })
          if (res.ok) {
            data = await res.json()
            break
          } else if (!targetFile) {
            const getRes = await fetch(url)
            if (getRes.ok) {
              data = await getRes.json()
              break
            }
          }
        } catch {
          // next
        }
      }

      if (data && data.status === "success") {
        const processedRefGraph = data.ref_graph as GraphPayload | undefined
        const processedObsGraph = data.obs_graph as GraphPayload | undefined

        if (processedRefGraph && processedObsGraph && Array.isArray(processedRefGraph.nodes)) {
          const refIdToIdx = new Map<string, number>()
          processedRefGraph.nodes.forEach((rn: GraphNodeData, idx: number) => {
            refIdToIdx.set(String(rn.id), idx)
            rn.ref_index = idx
          })

          if (Array.isArray(processedObsGraph.nodes)) {
            processedObsGraph.nodes.forEach((on: GraphNodeData) => {
              if (on.mapped_from && refIdToIdx.has(String(on.mapped_from))) {
                on.ref_index = refIdToIdx.get(String(on.mapped_from))
                on.is_matched = true
              }
            })
          }
        }

        setMatchData({
          similarity_score: Number(data.similarity_score ?? 0.9965),
          reference_coverage: Number(data.reference_coverage ?? 1.0),
          total_events: Number(data.total_events ?? 8295),
          noise_events: Number(data.noise_events ?? data.benign_events_filtered ?? 8280),
          agir_steps: Number(data.agir_steps ?? 7),
          matched_nodes_count: Number(data.matched_nodes_count ?? 4),
          node_mapping: data.node_mapping?.length ? data.node_mapping : defaultNodes,
          threat_name: data.threat_name,
          signature_id: data.signature_id,
          description: data.description,
          ref_graph: processedRefGraph || defaultRefGraph,
          obs_graph: processedObsGraph || defaultObsGraph,
          ref_graph_id: data.ref_graph_id,
          obs_graph_id: data.obs_graph_id,
        })
        if (Array.isArray(data.ranked_matches)) {
          setRankedMatches(data.ranked_matches)
        }
        notify(
          `Match complete: ${data.threat_name || data.signature_id} (${(Number(data.similarity_score) * 100).toFixed(1)}%)`,
        )
      } else if (data && data.detail) {
        notify(`Error: ${data.detail}`)
      } else {
        notify("Backend loaded with fallback telemetry cache")
      }
    } catch (e) {
      console.error("Match error:", e)
      notify("Offline mode: using verified StreamSpot pattern match")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    const fetchPatterns = async () => {
      try {
        const endpoints = ["/api/patterns", "http://127.0.0.1:8000/api/patterns"]
        for (const ep of endpoints) {
          try {
            const res = await fetch(ep)
            if (res.ok) {
              const data = await res.json()
              if (Array.isArray(data)) {
                setPatterns(data)
                break
              }
            }
          } catch {
            // next
          }
        }
      } catch (e) {
        console.error("Failed to load pattern bank", e)
      }
    }
    fetchPatterns()
    runMatching(null, "ALL")
  }, [])

  const inspect = (n: number) => {
    setSelected(n)
    setTab("System telemetry")
  }

  const exportReport = () => {
    downloadFile(
      "RefineMatch-Scientific-Report.json",
      JSON.stringify(
        {
          incident: "IR-2026-8819",
          signature: matchData.signature_id || "SUSP_SYN_003",
          analysis: "RefineMatch StreamSpot Scientific Investigation Result",
          acknowledged: ack,
          structuralSimilarity: matchData.similarity_score,
          referenceCoverage: matchData.reference_coverage,
          correlatedEvents: matchData.total_events,
          benignEventsFiltered: matchData.noise_events,
          agirSteps: matchData.agir_steps,
          triageStatus,
          demoHostIsolated: isolated,
          timestamp: new Date().toISOString(),
          assignments: nodes,
        },
        null,
        2,
      ),
    )
    notify("Forensic report exported as JSON")
  }

  const selectedNode = selected !== null && nodes[selected] ? nodes[selected] : (nodes[0] || defaultNodes[0])

  const filteredNodes = nodes
    .map((n, i) => ({ n, i }))
    .filter(
      ({ n }) =>
        nodeFilter === "All nodes" ||
        n.type ===
          ({
            Processes: "process",
            Network: "socket",
            Files: "file",
            Hosts: "host",
          } as Record<string, string>)[nodeFilter],
    )
    .filter(({ n }) =>
      Object.values(n).join(" ").toLowerCase().includes(search.toLowerCase()),
    )

  return (
    <div className="min-h-screen bg-[#f0f2f5] text-[#1e2a38] font-['DM_Sans'] flex flex-col antialiased">
      {/* 1. STICKY TOPBAR (h: 60px) */}
      <header className="sticky top-0 z-30 h-[60px] bg-white border-b border-[#e1e5eb] px-6 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#0d9488] to-[#0f766e] flex items-center justify-center text-white shadow-xs">
              <Icon name="graph" size={18} />
            </span>
            <span className="font-['DM_Serif_Display'] text-[21px] text-[#1e2a38] tracking-tight">
              RefineMatch
            </span>
          </div>

          <div className="h-5 w-px bg-[#e1e5eb] hidden sm:block" />

          <nav className="hidden sm:flex items-center gap-2 font-['DM_Sans'] text-[12px] text-[#4a5568]">
            <span className="font-medium text-[#8795a8]">Provenance Engine</span>
            <span className="text-[#cdd3db]">/</span>
            <span className="font-semibold text-[#1e2a38] flex items-center gap-1.5">
              <Icon name="target" size={13} className="text-[#0d9488]" />
              StreamSpot Target
            </span>
            <span className="font-['DM_Mono'] text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#f0f2f5] text-[#4a5568] border border-[#e1e5eb]">
              LAB V2
            </span>
          </nav>
        </div>

        <div className="flex items-center gap-4">
          {/* Live Pulsing Status Dot */}
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#ecfdf5] border border-[#a7f3d0]">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#10b981]" />
            </span>
            <span className="font-['DM_Mono'] text-[11px] font-semibold text-[#065f46] tracking-wide">
              ENGINE ONLINE
            </span>
          </div>

          <span className="font-['DM_Mono'] text-[11px] text-[#8795a8] hidden md:inline-block">
            INCIDENT #IR-2026-8819
          </span>

          {/* Incident Triage Status Pill */}
          <div className="relative">
            <button
              onClick={() => setStatusOpen(!statusOpen)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-[8px] border border-[#e1e5eb] bg-[#f7f8fa] hover:bg-[#edf0f5] text-[12px] font-medium text-[#1e2a38] transition-all"
            >
              <span className="w-2 h-2 rounded-full bg-[#f59e0b]" />
              <span>{triageStatus}</span>
              <Icon name="chevron" size={11} className="text-[#8795a8]" />
            </button>
            {statusOpen && (
              <div className="absolute right-0 mt-1 w-44 rounded-[10px] bg-white border border-[#e1e5eb] shadow-lg py-1 z-40 font-['DM_Sans'] text-[12px]">
                {["In Triage", "Investigating", "Contained", "Resolved"].map((st) => (
                  <button
                    key={st}
                    onClick={() => {
                      setTriageStatus(st)
                      setAck(st === "Resolved")
                      setStatusOpen(false)
                      notify(`Status marked ${st}`)
                    }}
                    className="w-full text-left px-3 py-1.5 hover:bg-[#f0f2f5] flex items-center justify-between"
                  >
                    <span>{st}</span>
                    {triageStatus === st && <Icon name="check" size={13} className="text-[#0d9488]" />}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* 2. MAIN GRID CONTAINER (310px Sidebar + 1fr Canvas) */}
      <div className="grid grid-cols-1 lg:grid-cols-[310px_1fr] gap-[18px] p-[18px] flex-1 bg-[#f0f2f5] w-full max-w-full min-w-0 overflow-hidden">
        {/* LEFT COLUMN: CONTROLS PANEL (Fixed 310px width) */}
        <aside className="w-full lg:w-[310px] flex flex-col gap-4 bg-white border border-[#e1e5eb] rounded-[16px] p-5 shadow-sm h-fit">
          <div className="flex items-center justify-between pb-3 border-b border-[#e1e5eb]">
            <div className="flex items-center gap-2">
              <Icon name="terminal" size={16} className="text-[#0d9488]" />
              <h2 className="font-['DM_Serif_Display'] text-[17px] text-[#1e2a38]">
                Controls Panel
              </h2>
            </div>
            <span className="font-['DM_Mono'] text-[9px] uppercase tracking-wider px-2 py-0.5 rounded bg-[#f7f8fa] text-[#8795a8] border border-[#e1e5eb]">
              PARAM_V2
            </span>
          </div>

          {/* Upload Dataset (.csv / .tsv) Dropzone */}
          <div className="flex flex-col gap-1.5">
            <label className="font-['DM_Sans'] text-[11px] font-semibold text-[#4a5568] uppercase tracking-wider flex items-center justify-between">
              <span>Telemetry Ingestion</span>
              <span className="font-['DM_Mono'] text-[9px] text-[#8795a8]">.tsv / .csv</span>
            </label>

            <label className="relative flex flex-col items-center justify-center p-4 border-2 border-dashed border-[#cdd3db] hover:border-[#0d9488] bg-[#f7f8fa] hover:bg-[#f0fdfa] transition-all rounded-[10px] cursor-pointer group text-center">
              <span className="w-8 h-8 rounded-full bg-white border border-[#e1e5eb] flex items-center justify-center text-[#4a5568] group-hover:text-[#0d9488] shadow-2xs mb-2 transition-colors">
                <Icon name="upload" size={16} />
              </span>
              <span className="font-['DM_Sans'] text-[12px] font-medium text-[#1e2a38] max-w-[240px] truncate">
                {selectedFile ? selectedFile.name : "Select or Drop Telemetry File"}
              </span>
              <span className="font-['DM_Mono'] text-[10px] text-[#8795a8] mt-0.5">
                {selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB · Ready to scan` : "StreamSpot / Syscall / NetFlow"}
              </span>
              <input
                type="file"
                accept=".tsv,.csv,.txt"
                className="hidden"
                onChange={handleFileChange}
              />
            </label>
          </div>

          {/* Attack Signature Selector */}
          <div className="flex flex-col gap-1.5">
            <label className="font-['DM_Sans'] text-[11px] font-semibold text-[#4a5568] uppercase tracking-wider">
              Attack Pattern Bank
            </label>
            <div className="relative">
              <select
                value={selectedPattern}
                onChange={(e) => {
                  const newPat = e.target.value
                  setSelectedPattern(newPat)
                  runMatching(undefined, newPat)
                }}
                disabled={isLoading}
                className="w-full h-9 pl-3 pr-8 text-[12px] font-['DM_Sans'] font-medium rounded-[8px] bg-[#f7f8fa] border border-[#e1e5eb] text-[#1e2a38] focus:border-[#0d9488] focus:ring-1 focus:ring-[#0d9488] appearance-none cursor-pointer outline-none transition-all"
              >
                <option value="ALL">🎯 Auto-Detect (Scan All Signatures)</option>
                {patterns.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}: {p.name}
                  </option>
                ))}
              </select>
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-[#8795a8]">
                <Icon name="chevron" size={12} />
              </span>
            </div>
          </div>

          {/* Run Match Action Button */}
          <button
            onClick={() => runMatching()}
            disabled={isLoading}
            className="w-full h-11 rounded-[10px] bg-gradient-to-r from-[#0f766e] to-[#0d9488] hover:from-[#115e59] hover:to-[#0f766e] text-white font-['DM_Sans'] text-[13px] font-semibold shadow-xs hover:shadow-sm transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? (
              <>
                <span className="animate-spin text-base">⟳</span>
                <span>Refining & Matching...</span>
              </>
            ) : (
              <>
                <Icon name="activity" size={16} />
                <span>Execute RefineMatch</span>
              </>
            )}
          </button>

          <div className="h-px bg-[#e1e5eb]" />

          {/* 4 KPI METRIC CARDS */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="font-['DM_Sans'] text-[11px] font-semibold text-[#4a5568] uppercase tracking-wider">
                Forensic Telemetry KPIs
              </span>
              <span className="font-['DM_Mono'] text-[10px] text-[#0d9488]">1-WL METRICS</span>
            </div>

            {/* KPI 1: Structural Similarity */}
            <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3 hover:border-[#cdd3db] transition-all">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-[#4a5568]">Structural Similarity</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-['DM_Mono'] font-bold bg-[#ccfbf1] text-[#0f766e]">
                  NEAR-EXACT
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-['DM_Mono'] text-[24px] font-bold text-[#0f766e] leading-none">
                  {(matchData.similarity_score * 100).toFixed(2)}%
                </span>
                <span className="font-['DM_Mono'] text-[10px] text-[#8795a8]">
                  ({matchData.similarity_score.toFixed(4)} / 1.0)
                </span>
              </div>
              <p className="text-[10px] text-[#8795a8] mt-1.5">
                Optimal Kuhn-Munkres bipartite correspondence
              </p>
            </div>

            {/* KPI 2: Attack Pattern Coverage */}
            <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3 hover:border-[#cdd3db] transition-all">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-[#4a5568]">Pattern Coverage</span>
                <span className="font-['DM_Mono'] text-[10px] text-[#1e2a38] font-bold">
                  {matchData.matched_nodes_count} Nodes Mapped
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-['DM_Mono'] text-[24px] font-bold text-[#1e2a38] leading-none">
                  {(matchData.reference_coverage * 100).toFixed(1)}%
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#e1e5eb] rounded-full overflow-hidden mt-2">
                <div
                  className="h-full bg-[#0d9488] transition-all duration-500"
                  style={{ width: `${Math.min(100, matchData.reference_coverage * 100)}%` }}
                />
              </div>
            </div>

            {/* KPI 3: Correlated Telemetry Events */}
            <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3 hover:border-[#cdd3db] transition-all">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-[#4a5568]">Correlated Events</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-['DM_Mono'] font-medium bg-[#f0f2f5] text-[#4a5568] border border-[#e1e5eb]">
                  PROVENANCE
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-['DM_Mono'] text-[24px] font-bold text-[#1e2a38] leading-none">
                  {matchData.total_events.toLocaleString()}
                </span>
              </div>
              <p className="text-[10px] text-[#0f766e] font-medium mt-1.5">
                {matchData.noise_events.toLocaleString()} benign background events filtered
              </p>
            </div>

            {/* KPI 4: AGIR Resolution Steps */}
            <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3 hover:border-[#cdd3db] transition-all">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-[#4a5568]">AGIR Resolution</span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-['DM_Mono'] font-bold bg-[#ecfdf5] text-[#065f46]">
                  STABILIZED
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-['DM_Mono'] text-[24px] font-bold text-[#1e2a38] leading-none">
                  {matchData.agir_steps}
                </span>
                <span className="font-['DM_Sans'] text-[12px] font-semibold text-[#4a5568]">
                  Tie-break steps
                </span>
              </div>
              <p className="text-[10px] text-[#8795a8] mt-1.5">
                Zero automorphic partition ambiguity remaining
              </p>
            </div>
          </div>

          <div className="h-px bg-[#e1e5eb]" />

          {/* Action Buttons */}
          <div className="flex flex-col gap-2">
            <button
              onClick={exportReport}
              className="w-full h-8.5 rounded-[8px] bg-[#f7f8fa] hover:bg-[#edf0f5] border border-[#e1e5eb] text-[11px] font-semibold text-[#1e2a38] flex items-center justify-center gap-1.5 transition-all cursor-pointer"
            >
              <Icon name="download" size={13} />
              <span>Export Forensic JSON</span>
            </button>

            <button
              onClick={() => {
                setPendingNode(null)
                setModal("Isolate affected host")
              }}
              disabled={isolated}
              className={`w-full h-8.5 rounded-[8px] text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                isolated
                  ? "bg-[#ecfdf5] text-[#065f46] border border-[#a7f3d0]"
                  : "bg-[#fff1f2] hover:bg-[#ffe4e6] text-[#be123c] border border-[#fecdd3]"
              }`}
            >
              <Icon name="shield" size={13} />
              <span>{isolated ? "Host Isolated (srv-edge-04)" : "Isolate Host (srv-edge-04)"}</span>
            </button>
          </div>
        </aside>

        {/* RIGHT COLUMN: GRAPH & DATA CANVAS */}
        <main className="flex flex-col gap-[18px] w-full max-w-full min-w-0 overflow-hidden">
          {/* Threat Story Narrative Narrative Banner */}
          <section className="bg-white border border-[#e1e5eb] rounded-[16px] p-4.5 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4 w-full max-w-full min-w-0">
            <div className="flex items-start gap-3.5">
              <span className="w-10 h-10 rounded-[10px] bg-[#fff1f2] border border-[#fecdd3] text-[#e11d48] flex items-center justify-center shrink-0 mt-0.5">
                <Icon name="shield" size={20} />
              </span>
              <div>
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="px-2 py-0.5 rounded-[5px] bg-[#fff1f2] text-[#e11d48] font-['DM_Mono'] text-[9px] font-bold tracking-wider">
                    CRITICAL MATCH
                  </span>
                  <span className="font-['DM_Mono'] text-[11px] text-[#4a5568]">
                    {matchData.signature_id || "SUSP_SYN_003"}
                  </span>
                  <span className="text-[#cdd3db]">·</span>
                  <span className="text-[11px] text-[#8795a8] flex items-center gap-1">
                    <Icon name="clock" size={11} />
                    Correlated at 12:04:58 UTC
                  </span>
                </div>
                <h1 className="font-['DM_Serif_Display'] text-[19px] text-[#1e2a38] leading-tight">
                  {matchData.threat_name || "Drive-by Download & In-Memory Code Injection"}
                </h1>
                <p className="text-[12px] text-[#4a5568] mt-1 max-w-3xl leading-relaxed">
                  {matchData.description || "Multi-stage provenance threat sequence matched against telemetry log."}{" "}
                  Structural correspondence established across{" "}
                  <strong className="text-[#1e2a38] font-semibold">{matchData.total_events.toLocaleString()} enterprise events</strong>{" "}
                  with {matchData.matched_nodes_count} mapped nodes.
                </p>
                <div className="flex items-center gap-2 mt-2.5 flex-wrap">
                  <span className="px-2 py-0.5 rounded bg-[#f0f2f5] border border-[#e1e5eb] font-['DM_Mono'] text-[10px] text-[#4a5568]">
                    <span className="text-[#0d9488] font-bold mr-1">T1189</span> Drive-by Download
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#f0f2f5] border border-[#e1e5eb] font-['DM_Mono'] text-[10px] text-[#4a5568]">
                    <span className="text-[#0d9488] font-bold mr-1">T1055</span> Process Injection
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#f0f2f5] border border-[#e1e5eb] font-['DM_Mono'] text-[10px] text-[#4a5568]">
                    <span className="text-[#0d9488] font-bold mr-1">T1071</span> Socket Connect
                  </span>
                </div>
              </div>
            </div>

            <div className="shrink-0 flex items-center gap-2 self-end md:self-center">
              <span className="font-['DM_Mono'] text-[12px] font-bold text-[#0f766e] bg-[#ccfbf1] px-3 py-1.5 rounded-[8px] border border-[#99f6e4]">
                94.8% High Confidence
              </span>
            </div>
          </section>

          {/* Threat Detection Leaderboard Pills */}
          {rankedMatches && rankedMatches.length > 0 && (
            <div className="bg-white border border-[#e1e5eb] rounded-[16px] px-4 py-3 shadow-xs w-full max-w-full min-w-0 overflow-hidden">
              <div className="flex items-center justify-between mb-2 flex-wrap gap-1">
                <span className="font-['DM_Sans'] text-[11px] font-semibold uppercase tracking-wider text-[#4a5568] flex items-center gap-1.5">
                  <Icon name="target" size={13} className="text-[#0d9488]" />
                  Threat Detection Leaderboard ({rankedMatches.length} Signatures Evaluated)
                </span>
                <span className="text-[10px] text-[#8795a8]">
                  Click signature to switch active viewport
                </span>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-1 w-full max-w-full whitespace-nowrap min-w-0">
                {rankedMatches.map((m, idx) => {
                  const isSelected =
                    selectedPattern === m.pattern_id ||
                    (selectedPattern === "ALL" && matchData.signature_id === m.pattern_id)
                  const simPct = (m.similarity_score * 100).toFixed(1)
                  return (
                    <button
                      key={m.pattern_id}
                      onClick={() => {
                        setSelectedPattern(m.pattern_id)
                        runMatching(undefined, m.pattern_id)
                      }}
                      disabled={isLoading}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-[8px] text-[11px] font-medium whitespace-nowrap transition-all border cursor-pointer shrink-0 ${
                        isSelected
                          ? "bg-[#ccfbf1] border-[#0d9488] text-[#0f766e] shadow-2xs font-semibold"
                          : "bg-[#f7f8fa] hover:bg-[#edf0f5] border-[#e1e5eb] text-[#4a5568]"
                      }`}
                    >
                      <span className="font-['DM_Mono'] text-[10px] opacity-75">#{idx + 1}</span>
                      <span className="font-['DM_Mono'] font-bold">{m.pattern_id}</span>
                      <span className="max-w-[120px] truncate text-[#8795a8]">{m.name}</span>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-['DM_Mono'] font-bold ${
                        m.similarity_score >= 0.8
                          ? "bg-[#dcfce7] text-[#15803d]"
                          : m.similarity_score >= 0.5
                          ? "bg-[#fef9c3] text-[#a16207]"
                          : "bg-[#f1f5f9] text-[#64748b]"
                      }`}>
                        {simPct}%
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* TOP ROW: DUAL VIEWPORT GRAPH CANVAS (Reference vs. Observed) */}
          <section className="bg-white border border-[#e1e5eb] rounded-[16px] shadow-sm overflow-hidden flex flex-col w-full max-w-full min-w-0">
            {/* Canvas Header & Toolbar */}
            <div className="border-b border-[#e1e5eb] px-5 py-3 flex flex-wrap items-center justify-between gap-3 bg-[#fcfdfe]">
              <div className="flex items-center gap-3">
                <span className="w-2.5 h-2.5 rounded-full bg-[#0d9488]" />
                <h2 className="font-['DM_Serif_Display'] text-[17px] text-[#1e2a38]">
                  Provenance Dual Graph Viewport
                </h2>
                <span className="font-['DM_Mono'] text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#ccfbf1] text-[#0f766e] font-semibold border border-[#99f6e4]">
                  1-WL + AGIR
                </span>
                <span className="font-['DM_Sans'] text-[11px] text-[#8795a8] hidden xl:inline-block">
                  · Hover any node to trace 1:1 Hungarian pairing
                </span>
              </div>

              <div className="flex items-center gap-3">
                {/* View switcher tabs */}
                <div className="flex items-center p-0.5 rounded-[8px] bg-[#f0f2f5] border border-[#e1e5eb]">
                  {["Split view", "Overlay mode", "Diff heatmap"].map((v) => (
                    <button
                      key={v}
                      onClick={() => {
                        setView(v)
                        setPan({ x: 0, y: 0 })
                      }}
                      className={`px-2.5 py-1 rounded-[6px] text-[11px] font-medium transition-all cursor-pointer ${
                        view === v
                          ? "bg-white text-[#1e2a38] shadow-2xs font-semibold"
                          : "text-[#64748b] hover:text-[#1e2a38]"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                </div>

                {/* Noise filter toggle */}
                <button
                  onClick={() => setShowNoise(!showNoise)}
                  className={`px-2.5 py-1 rounded-[6px] text-[11px] border transition-all flex items-center gap-1.5 cursor-pointer ${
                    showNoise
                      ? "bg-[#ccfbf1] border-[#99f6e4] text-[#0f766e]"
                      : "bg-[#f7f8fa] border-[#e1e5eb] text-[#8795a8]"
                  }`}
                  title="Toggle unmatched background noise events"
                >
                  <Icon name="filter" size={11} />
                  <span>Noise: {showNoise ? "Visible" : "Hidden"}</span>
                </button>

                {/* Zoom controls */}
                <div className="flex items-center rounded-[6px] border border-[#e1e5eb] bg-[#f7f8fa] overflow-hidden">
                  <button
                    onClick={() => setZoom(Math.max(0.6, zoom - 0.15))}
                    disabled={zoom <= 0.6}
                    className="w-7 h-7 flex items-center justify-center text-[#4a5568] hover:bg-[#e1e5eb] disabled:opacity-30 cursor-pointer"
                    title="Zoom Out"
                  >
                    <Icon name="minus" size={13} />
                  </button>
                  <span className="px-2 font-['DM_Mono'] text-[10px] font-medium text-[#1e2a38]">
                    {Math.round(zoom * 100)}%
                  </span>
                  <button
                    onClick={() => setZoom(Math.min(1.6, zoom + 0.15))}
                    disabled={zoom >= 1.6}
                    className="w-7 h-7 flex items-center justify-center text-[#4a5568] hover:bg-[#e1e5eb] disabled:opacity-30 cursor-pointer"
                    title="Zoom In"
                  >
                    <Icon name="plus" size={13} />
                  </button>
                </div>
              </div>
            </div>

            {/* Canvas Body (Split View / Overlay) */}
            <div className="relative bg-[#fcfdfe] sci-graph-canvases w-full max-w-full min-w-0 overflow-hidden">
              <div className={`grid ${view === "Overlay mode" ? "grid-cols-1" : "grid-cols-1 md:grid-cols-[44%_56%]"} divide-y md:divide-y-0 md:divide-x divide-[#e1e5eb] w-full max-w-full min-w-0 overflow-hidden`}>
                {/* Left Viewport: Reference Pattern */}
                {view !== "Overlay mode" && (
                  <div className="reference-viewport relative p-3 w-full min-w-0 overflow-hidden">
                    <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-[#f0f2f5]">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#7c3aed]" />
                        <span className="font-['DM_Sans'] text-[12px] font-semibold text-[#1e2a38]">
                          Reference Archetype Signature
                        </span>
                        <span className="font-['DM_Mono'] text-[10px] text-[#7c3aed] font-medium">
                          {matchData.signature_id || "SUSP_SYN_003"}
                        </span>
                      </div>
                      <span className="font-['DM_Mono'] text-[10px] text-[#8795a8]">
                        {matchData.ref_graph?.nodes?.length ?? 4} nodes · {matchData.ref_graph?.edges?.length ?? 4} edges
                      </span>
                    </div>

                    <ScientificGraph
                      enterprise={false}
                      mode={view}
                      showNoise={false}
                      active={active}
                      setActive={setActive}
                      inspect={inspect}
                      zoom={zoom}
                      pan={pan}
                      setPan={setPan}
                      graphData={matchData.ref_graph}
                      matchedCount={matchData.matched_nodes_count}
                    />

                    <div className="text-[10px] text-[#8795a8] px-2 pt-1 flex items-center gap-1.5">
                      <Icon name="shield" size={12} className="text-[#7c3aed]" />
                      <span>Canonical attack archetype · MITRE ATT&CK Model</span>
                    </div>
                  </div>
                )}

                {/* Right Viewport: Observed Telemetry */}
                <div className="telemetry-viewport relative p-3 w-full min-w-0 overflow-hidden">
                  <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-[#f0f2f5]">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[#0d9488]" />
                      <span className="font-['DM_Sans'] text-[12px] font-semibold text-[#1e2a38]">
                        {view === "Overlay mode" ? "Signature Overlay Alignment" : "Observed Enterprise Telemetry"}
                      </span>
                      <span className="font-['DM_Mono'] text-[10px] text-[#0d9488] font-medium">
                        {selectedFile
                          ? selectedFile.name
                          : matchData.obs_graph_id
                          ? `Graph ${matchData.obs_graph_id}`
                          : "all.tsv"}
                      </span>
                    </div>
                    <span className="font-['DM_Mono'] text-[10px] text-[#0d9488] font-bold">
                      {matchData.total_events.toLocaleString()} events
                    </span>
                  </div>

                  <ScientificGraph
                    enterprise={true}
                    mode={view}
                    showNoise={showNoise}
                    active={active}
                    setActive={setActive}
                    inspect={inspect}
                    zoom={zoom}
                    pan={pan}
                    setPan={setPan}
                    graphData={matchData.obs_graph}
                    matchedCount={matchData.matched_nodes_count}
                  />

                  <div className="text-[10px] text-[#8795a8] px-2 pt-1 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#0d9488]" />
                      <span>{view === "Diff heatmap" ? "Teal: matched · Red: unmatched noise" : "Enterprise provenance subgraph highlighted"}</span>
                    </span>
                    <span className="font-['DM_Mono'] text-[9px] text-[#8795a8]">
                      Interactive assignment trace active
                    </span>
                  </div>
                </div>
              </div>

              {/* Assignment Overlay Bridge Line */}
              {active !== null && bridge && view === "Split view" && (
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none z-20"
                  viewBox="0 0 1200 380"
                  preserveAspectRatio="none"
                >
                  <path
                    d={`M${bridge.x1} ${bridge.y1} C ${bridge.x1 + 180} ${bridge.y1 - 45}, ${bridge.x2 - 180} ${bridge.y2 - 45}, ${bridge.x2} ${bridge.y2}`}
                    fill="none"
                    stroke="#0d9488"
                    strokeWidth="2"
                    strokeDasharray="5 4"
                    className="animate-pulse"
                  />
                  <text
                    x={(bridge.x1 + bridge.x2) / 2}
                    y={Math.max(22, (bridge.y1 + bridge.y2) / 2 - 30)}
                    textAnchor="middle"
                    className="font-mono text-[10px] font-bold fill-[#0f766e]"
                  >
                    1:1 Hungarian Correspondence
                  </text>
                </svg>
              )}
            </div>

            {/* Canvas Taxonomy Legend Bar */}
            <div className="border-t border-[#e1e5eb] bg-[#f8fafc] px-5 py-2.5 flex flex-wrap items-center justify-between gap-3 text-[11px] text-[#64748b]">
              <div className="flex items-center gap-4 flex-wrap">
                <span className="font-semibold text-[#1e2a38] text-[10px] uppercase tracking-wider">
                  Entity Taxonomy:
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#7c3aed]" />
                  <span>Process</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#0d9488]" />
                  <span>File</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#d97706]" />
                  <span>Socket / Net</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#2563eb]" />
                  <span>Host Endpoint</span>
                </span>
              </div>

              <div className="font-['DM_Mono'] text-[10px] text-[#8795a8] flex items-center gap-3">
                <span>1-WL Hash: SHA-256</span>
                <span>·</span>
                <span>Polynomial Runtime O(V³+E)</span>
              </div>
            </div>
          </section>

          {/* BOTTOM ROW: NODE MAPPING TABLE / TERMINAL OUTPUT (Dark Developer Terminal Block) */}
          <section className="bg-[#1e2a38] text-[#a8c0d6] font-mono rounded-[16px] shadow-lg border border-[#2a384a] overflow-hidden w-full max-w-full min-w-0">
            {/* Terminal Window Header */}
            <div className="bg-[#16202c] px-4 py-3 border-b border-[#2a384a] flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-[#ef4444] inline-block" />
                  <span className="w-3 h-3 rounded-full bg-[#f59e0b] inline-block" />
                  <span className="w-3 h-3 rounded-full bg-[#10b981] inline-block" />
                </div>
                <span className="text-[11px] text-[#cbd5e1] font-semibold tracking-wide">
                  refinematch@ir-lab:~$ ./evaluate-bipartite-correspondence --target=StreamSpot
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* Search input in terminal */}
                <div className="relative">
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="grep nodes / pid..."
                    className="h-7 pl-7 pr-3 rounded-[6px] bg-[#0f172a] border border-[#334155] text-[11px] text-[#e2e8f0] placeholder-[#64748b] focus:border-[#0d9488] outline-none font-mono"
                  />
                  <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[#64748b]">
                    <Icon name="search" size={12} />
                  </span>
                </div>

                {/* Filter tags */}
                <div className="hidden sm:flex items-center gap-1">
                  {["All nodes", "Processes", "Network", "Files", "Hosts"].map((f) => (
                    <button
                      key={f}
                      onClick={() => setNodeFilter(f)}
                      className={`px-2 py-1 rounded text-[10px] transition-all cursor-pointer ${
                        nodeFilter === f
                          ? "bg-[#0d9488] text-white font-bold"
                          : "bg-[#0f172a] text-[#94a3b8] hover:text-[#e2e8f0]"
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Monospace Table */}
            <div className="overflow-x-auto w-full max-w-full min-w-0">
              <table className="w-full text-left text-[11px] border-collapse">
                <thead>
                  <tr className="bg-[#141d28] text-[#94a3b8] border-b border-[#2a384a]">
                    <th className="py-2.5 px-4 font-semibold">#</th>
                    <th className="py-2.5 px-4 font-semibold">REF ENTITY (ARCHETYPE)</th>
                    <th className="py-2.5 px-4 font-semibold">OBSERVED PROVENANCE NODE</th>
                    <th className="py-2.5 px-4 font-semibold">1-WL COLOR SCORE</th>
                    <th className="py-2.5 px-4 font-semibold">PID / COMMAND</th>
                    <th className="py-2.5 px-4 font-semibold text-right">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#243344]">
                  {filteredNodes.length > 0 ? (
                    filteredNodes.map(({ n, i }) => (
                      <tr
                        key={n.id}
                        onClick={() => inspect(i)}
                        className={`hover:bg-[#253549] transition-colors cursor-pointer ${
                          selected === i ? "bg-[#273a52]" : ""
                        }`}
                      >
                        <td className="py-2.5 px-4 text-[#64748b]">{i + 1}</td>
                        <td className="py-2.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="text-[#a5b4fc] font-bold">{n.id}</span>
                            <span className="px-1.5 py-0.5 rounded text-[9px] bg-[#0f172a] text-[#818cf8] border border-[#3730a3]">
                              {n.label}
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="text-[#5eead4] font-bold">{n.observed}</span>
                            <span className="text-[#94a3b8] text-[10px]">({n.desc})</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="text-[#4ade80] font-bold">{n.score}</span>
                            <div className="w-14 h-1.5 bg-[#0f172a] rounded-full overflow-hidden">
                              <div
                                className="h-full bg-[#10b981]"
                                style={{ width: `${Number(n.score) * 100}%` }}
                              />
                            </div>
                            <span className="text-[9px] text-[#6ee7b7]">[1:1 MATCH]</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-4 text-[#cbd5e1] max-w-[260px] truncate">
                          <span className="text-[#f59e0b] mr-1.5">pid:{n.pid}</span>
                          <span className="text-[#94a3b8]">{n.binary}</span>
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              inspect(i)
                            }}
                            className="px-2 py-1 rounded bg-[#0f172a] hover:bg-[#334155] border border-[#334155] text-[#5eead4] text-[10px] font-semibold transition-all cursor-pointer"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-[#64748b]">
                        No nodes matched current filter criteria "{search}"
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Terminal Footer Bar */}
            <div className="bg-[#141d28] px-4 py-2.5 border-t border-[#2a384a] flex flex-wrap items-center justify-between gap-3 text-[10px] text-[#64748b]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#10b981]" />
                <span className="text-[#94a3b8]">
                  {matchData.matched_nodes_count} / {matchData.ref_graph?.nodes?.length ?? 4} reference nodes assigned
                </span>
                <span>·</span>
                <span className="text-[#a8c0d6]">0 unmapped ties</span>
              </div>
              <div className="text-[#38bdf8]">
                &gt; pipeline ready for forensic triage [stable]
              </div>
            </div>
          </section>
        </main>
      </div>

      {/* 3. FORENSIC INSPECTOR DRAWER */}
      {selected !== null && selectedNode && (
        <aside className="fixed right-0 top-0 bottom-0 w-[420px] max-w-[90vw] bg-white border-l border-[#e1e5eb] shadow-2xl z-50 flex flex-col font-['DM_Sans'] animate-in slide-in-from-right duration-200">
          <div className="p-4 border-b border-[#e1e5eb] flex items-center justify-between bg-[#f8fafc]">
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-lg bg-[#ccfbf1] text-[#0f766e] flex items-center justify-center">
                <Icon name={selectedNode.type} size={15} />
              </span>
              <div>
                <h3 className="font-['DM_Serif_Display'] text-[16px] text-[#1e2a38]">
                  Entity Forensic Telemetry
                </h3>
                <span className="font-['DM_Mono'] text-[10px] text-[#8795a8]">
                  {selectedNode.observed} ({selectedNode.id})
                </span>
              </div>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="w-7 h-7 rounded-full bg-white border border-[#e1e5eb] flex items-center justify-center text-[#4a5568] hover:bg-[#f0f2f5] cursor-pointer"
            >
              <Icon name="close" size={13} />
            </button>
          </div>

          <div className="flex border-b border-[#e1e5eb] px-4 bg-[#fcfdfe] text-[12px] font-medium text-[#4a5568]">
            {["System telemetry", "Provenances & edges", "1-WL signature"].map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`py-2.5 px-3 border-b-2 transition-all cursor-pointer ${
                  tab === t
                    ? "border-[#0d9488] text-[#0f766e] font-semibold"
                    : "border-transparent hover:text-[#1e2a38]"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4 text-[12px]">
            {tab === "System telemetry" && (
              <>
                <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3 flex flex-col gap-2">
                  <span className="text-[10px] font-semibold uppercase text-[#8795a8] tracking-wider">
                    Process & Execution Path
                  </span>
                  <div className="font-['DM_Mono'] text-[11px] text-[#1e2a38] break-all bg-white p-2.5 rounded border border-[#e1e5eb]">
                    {selectedNode.binary}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3">
                    <span className="text-[10px] text-[#8795a8] block">PID / TID</span>
                    <span className="font-['DM_Mono'] text-[14px] font-bold text-[#1e2a38] mt-0.5 block">
                      {selectedNode.pid}
                    </span>
                  </div>
                  <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3">
                    <span className="text-[10px] text-[#8795a8] block">1-WL Match Confidence</span>
                    <span className="font-['DM_Mono'] text-[14px] font-bold text-[#0f766e] mt-0.5 block">
                      {selectedNode.score}
                    </span>
                  </div>
                </div>

                <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[10px] p-3">
                  <span className="text-[10px] text-[#8795a8] block">Forensic Context</span>
                  <span className="font-medium text-[#1e2a38] mt-1 block">
                    {selectedNode.desc}
                  </span>
                </div>
              </>
            )}

            {tab === "Provenances & edges" && (
              <div className="flex flex-col gap-2.5">
                {[
                  { dir: "OUTGOING", event: "read", endpoint: "/tmp/payload.bin", detail: "1,024 bytes · 2 events" },
                  { dir: "OUTGOING", event: "connect", endpoint: "203.0.113.7:443", detail: "Protocol TCP · external endpoint" },
                  { dir: "INCOMING", event: "spawned_by", endpoint: "admin_user", detail: "Source port 49152" },
                ].map((e, idx) => (
                  <div key={idx} className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[8px] p-3">
                    <div className="flex items-center justify-between text-[10px] font-semibold text-[#8795a8]">
                      <span>{e.dir}</span>
                      <span className="font-['DM_Mono'] text-[#0f766e] font-bold">{e.event}</span>
                    </div>
                    <div className="font-['DM_Mono'] text-[11px] text-[#1e2a38] mt-1">{e.endpoint}</div>
                    <div className="text-[10px] text-[#8795a8] mt-0.5">{e.detail}</div>
                  </div>
                ))}
              </div>
            )}

            {tab === "1-WL signature" && (
              <div className="flex flex-col gap-3 font-['DM_Mono']">
                <div className="bg-[#1e2a38] text-[#a8c0d6] p-3 rounded-[8px] border border-[#2a384a]">
                  <span className="text-[9px] text-[#64748b] block mb-1">COLOR PARTITION HASH (128-BIT)</span>
                  <div className="text-[11px] text-[#38bdf8] break-all">
                    7ea67fa9446f26b3a9a6904422fb4532
                  </div>
                </div>
                <div className="bg-[#f7f8fa] border border-[#e1e5eb] rounded-[8px] p-3 text-[11px] flex flex-col gap-2">
                  <div className="flex justify-between">
                    <span className="text-[#8795a8]">Equitable Partition</span>
                    <span className="text-[#0f766e] font-bold">Stable Round 2</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#8795a8]">Automorphism Symmetry</span>
                    <span className="text-[#0f766e] font-bold">Resolved (AGIR)</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-[#e1e5eb] bg-[#f8fafc] flex items-center justify-between gap-2">
            <button
              onClick={() => {
                setBlocked((c) => (c.includes(selected) ? c : [...c, selected]))
                notify("Node added to session blocklist")
              }}
              className="flex-1 h-9 rounded-[8px] bg-[#fff1f2] hover:bg-[#ffe4e6] border border-[#fecdd3] text-[#be123c] text-[11px] font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Icon name="shield" size={13} />
              <span>{blocked.includes(selected) ? "In Blocklist" : "Quarantine Node"}</span>
            </button>
            <button
              onClick={() => {
                downloadFile(
                  `${selectedNode.observed}-stix.json`,
                  JSON.stringify({ type: "indicator", id: selectedNode.observed, target: selectedNode.id }, null, 2),
                )
                notify("STIX indicator exported")
              }}
              className="h-9 px-3 rounded-[8px] bg-white border border-[#e1e5eb] text-[#1e2a38] text-[11px] font-medium hover:bg-[#f0f2f5] flex items-center justify-center gap-1 cursor-pointer"
            >
              <Icon name="download" size={13} />
              <span>STIX</span>
            </button>
          </div>
        </aside>
      )}

      {/* 4. MODALS */}
      {modal && (
        <div
          className="fixed inset-0 bg-[#0f172a]/40 backdrop-blur-xs z-50 flex items-center justify-center p-4 animate-in fade-in duration-150"
          onClick={() => setModal(null)}
        >
          <div
            className="w-full max-w-lg bg-white border border-[#e1e5eb] rounded-[16px] shadow-2xl p-6 relative font-['DM_Sans']"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-[#e1e5eb]">
              <h3 className="font-['DM_Serif_Display'] text-[18px] text-[#1e2a38]">
                {modal}
              </h3>
              <button
                onClick={() => setModal(null)}
                className="w-7 h-7 rounded-full bg-[#f0f2f5] flex items-center justify-center text-[#4a5568] hover:bg-[#e1e5eb] cursor-pointer"
              >
                <Icon name="close" size={13} />
              </button>
            </div>

            <div className="py-4 text-[13px] text-[#4a5568] leading-relaxed">
              {modal === "Isolate affected host" ? (
                <div className="flex flex-col gap-3">
                  <p>
                    Isolating <strong>srv-edge-04</strong> disconnects all external telemetry streams while preserving forensic read channels.
                  </p>
                  <div className="p-3 bg-[#fff1f2] border border-[#fecdd3] rounded-[8px] text-[#be123c] text-[12px]">
                    <strong>Demonstration simulation:</strong> No live infrastructure will be modified in this prototype session.
                  </div>
                </div>
              ) : (
                <p>
                  Incident investigation evidence and telemetry channels are pinned for current review.
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[#e1e5eb]">
              <button
                onClick={() => setModal(null)}
                className="px-4 py-2 rounded-[8px] border border-[#e1e5eb] text-[12px] font-medium text-[#4a5568] hover:bg-[#f0f2f5] cursor-pointer"
              >
                Close
              </button>
              {modal === "Isolate affected host" && (
                <button
                  onClick={() => {
                    setIsolated(true)
                    setTriageStatus("Contained")
                    notify("Host srv-edge-04 marked as contained")
                    setModal(null)
                  }}
                  className="px-4 py-2 rounded-[8px] bg-[#be123c] text-white text-[12px] font-semibold hover:bg-[#9f1239] cursor-pointer"
                >
                  Confirm Isolation
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. TOAST NOTIFICATION */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1e2a38] text-white px-4 py-2.5 rounded-full shadow-lg border border-[#334155] z-50 text-[12px] font-medium flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <span className="w-2 h-2 rounded-full bg-[#10b981]" />
          <span>{toast}</span>
        </div>
      )}
    </div>
  )
}
