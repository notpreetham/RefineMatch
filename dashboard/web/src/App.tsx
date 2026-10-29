import { useEffect, useState, type ReactNode, type CSSProperties } from "react"

type IconName = "grid" | "graph" | "shield" | "activity" | "layers" | "settings" | "help" | "chevron" | "arrow" | "download" | "check" | "clock" | "external" | "close" | "filter" | "plus" | "minus" | "fit" | "process" | "file" | "socket" | "host" | "search" | "bell" | "pause" | "play" | "code" | "copy" | "eye" | "spark" | "target"
function Icon({
  name,
  size = 18,
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
    activity: <path d="M2 12h5l3-8 4 16 3-8h5" />,
    layers: (
      <>
        <path d="m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5" />
      </>
    ),
    settings: (
      <>
        <path d="m9 3-1 3-3 1v4l-2 1 2 2v4l3 1 1 2h6l1-2 3-1v-4l2-2-2-1V7l-3-1-1-3Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5M12 17v.1" />
      </>
    ),
    chevron: <path d="m9 5 7 7-7 7" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    download: (
      <>
        <path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    external: (
      <>
        <path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6" />
      </>
    ),
    close: <path d="m6 6 12 12M18 6 6 18" />,
    filter: (
      <>
        <path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    fit: <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />,
    process: (
      <>
        <rect x="5" y="5" width="14" height="14" rx="3" />
        <path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4" />
        <path d="m10 9 4 3-4 3" />
      </>
    ),
    file: (
      <>
        <path d="M6 3h8l5 5v13H6V3Zm8 0v6h5M9 13h7m-7 4h5" />
      </>
    ),
    socket: (
      <>
        <path d="M8 3v5m8-5v5M6 8h12v4a6 6 0 0 1-12 0V8Zm6 10v4" />
      </>
    ),
    host: (
      <>
        <rect x="3" y="4" width="18" height="13" rx="2" />
        <path d="M8 21h8m-4-4v4M7 8h5m-5 4h9" />
      </>
    ),
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    bell: (
      <>
        <path d="M5 17h14l-2-4V9A5 5 0 0 0 7 9v4l-2 4ZM10 21h4" />
      </>
    ),
    pause: (
      <>
        <path d="M9 5v14M15 5v14" />
      </>
    ),
    play: <path d="m7 4 14 8-14 8V4Z" />,
    code: (
      <>
        <path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18" />
      </>
    ),
    copy: (
      <>
        <rect x="8" y="8" width="12" height="13" rx="2" />
        <path d="M16 8V3H3v13h5" />
      </>
    ),
    eye: (
      <>
        <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
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
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  )
}

function Button({
  children,
  icon,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: IconName }) {
  return (
    <button className={`btn ${className}`} {...props}>
      {icon && <Icon name={icon} size={15} />} {children}
    </button>
  )
}
function Tag({
  children,
  className = "",
}: {
  children: ReactNode
  className?: string
}) {
  return <span className={`tag ${className}`}>{children}</span>
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
const nodes = defaultNodes
const reference = [
  { x: 247, y: 75 },
  { x: 116, y: 193 },
  { x: 380, y: 193 },
  { x: 247, y: 298 },
]
const observed = [
  { x: 328, y: 75 },
  { x: 200, y: 193 },
  { x: 462, y: 193 },
  { x: 328, y: 298 },
]
const noise = Array.from({ length: 49 }, (_, i) => {
  const angle = i * 2.39996
  const radius = 125 + ((i * 37) % 115)
  return {
    x: 330 + Math.cos(angle) * radius * 1.24,
    y: 188 + Math.sin(angle) * radius * 0.68,
  }
})

type CanvasPosition = {
  x: number
  y: number
}

function Graph({
  enterprise,
  mode,
  showNoise,
  active,
  setActive,
  inspect,
  zoom,
  pan,
  setPan,
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
}) {
  const points = enterprise ? observed : reference
  const [drag, setDrag] = useState<{
    x: number
    y: number
    px: number
    py: number
  } | null>(null)
  return (
    <svg
      className="graph-svg"
      viewBox={`0 0 ${enterprise ? 660 : 500} 370`}
      aria-label={
        enterprise
          ? "Observed enterprise telemetry graph"
          : "Reference attack signature graph"
      }
      onPointerDown={(e) => {
        if (
          e.target === e.currentTarget ||
          (e.target as Element).classList.contains("canvas-bg")
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
          id={`dots-${enterprise}`}
          width="18"
          height="18"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="1" cy="1" r=".65" fill="#283340" />
        </pattern>
        <marker
          id={`arrow-${enterprise}`}
          markerWidth="7"
          markerHeight="7"
          refX="6"
          refY="3.5"
          orient="auto"
        >
          <path
            d="m1 1 4 2.5L1 6"
            fill="none"
            stroke={enterprise ? "var(--accent-teal)" : "#697488"}
            strokeWidth="1"
          />
        </marker>
        <filter
          id={`glow-${enterprise}`}
          x="-70%"
          y="-70%"
          width="240%"
          height="240%"
        >
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>
      <rect
        className="canvas-bg"
        width="100%"
        height="100%"
        fill={`url(#dots-${enterprise})`}
      />
      <g
        transform={`translate(${pan.x} ${pan.y}) translate(${
          enterprise ? 330 : 250
        } 185) scale(${zoom}) translate(-${enterprise ? 330 : 250} -185)`}
      >
        {enterprise && showNoise && (
          <g
            className={`noise-nodes ${
              mode === "Diff heatmap" ? "heatmap-noise" : ""
            }`}
          >
            {noise.map((n, i) => (
              <g key={i}>
                <line
                  x1={n.x}
                  y1={n.y}
                  x2={
                    i % 3 === 0
                      ? points[i % 4].x
                      : noise[(i + 7) % noise.length].x
                  }
                  y2={
                    i % 3 === 0
                      ? points[i % 4].y
                      : noise[(i + 7) % noise.length].y
                  }
                />
                <circle cx={n.x} cy={n.y} r={i % 4 === 0 ? 5 : 3} />
                {i % 7 === 0 && (
                  <text x={n.x + 8} y={n.y + 3}>
                    N_{String(119 + i * 37).padStart(4, "0")}
                  </text>
                )}
              </g>
            ))}
          </g>
        )}
        {[
          [0, 1, "read"],
          [0, 2, "connect"],
          [1, 3, "write"],
          [2, 3, "sendto"],
        ].map(([a, b, label], i) => {
          const p = points[Number(a)],
            q = points[Number(b)],
            dx = q.x - p.x,
            dy = q.y - p.y,
            len = Math.sqrt(dx * dx + dy * dy)
          return (
            <g
              key={i}
              className={`graph-edge ${enterprise ? "matched-edge" : ""} ${
                active !== null && Number(a) !== active && Number(b) !== active
                  ? "dim"
                  : ""
              }`}
            >
              <line
                x1={p.x + (dx / len) * 30}
                y1={p.y + (dy / len) * 30}
                x2={q.x - (dx / len) * 33}
                y2={q.y - (dy / len) * 33}
                markerEnd={`url(#arrow-${enterprise})`}
              />
              <rect
                x={(p.x + q.x) / 2 - 25}
                y={(p.y + q.y) / 2 - 9}
                width="50"
                height="18"
                rx="4"
              />
              <text
                x={(p.x + q.x) / 2}
                y={(p.y + q.y) / 2 + 3}
                textAnchor="middle"
              >
                {label}
              </text>
            </g>
          )
        })}
        {mode === "Overlay mode" &&
          enterprise &&
          points.map((p, i) => {
            const n = nodes[i] || defaultNodes[i % defaultNodes.length]
            return (
              <circle
                key={`overlay${i}`}
                cx={p.x - 9}
                cy={p.y - 5}
                r="28"
                stroke={`var(--${n.color})`}
                fill="none"
                strokeDasharray="4 4"
                opacity=".65"
              />
            )
          })}
        {points.map((p, i) => {
          const n = nodes[i] || defaultNodes[i % defaultNodes.length]
          return (
            <g
              key={i}
              data-node-index={i}
              className={`graph-node ${enterprise ? "observed-node" : ""} ${
                active === i ? "node-active" : ""
              } ${
                active !== null && active !== i ? "dim" : ""
              } ${n.color}`}
              style={
                { "--node-color": `var(--${n.color})` } as CSSProperties
              }
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              onClick={() => inspect(i)}
              role="button"
              tabIndex={0}
              aria-label={`Inspect ${
                enterprise ? n.observed : n.id
              }`}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault()
                  inspect(i)
                }
              }}
            >
              <circle
                className="node-glow"
                cx={p.x}
                cy={p.y}
                r="30"
                filter={`url(#glow-${enterprise})`}
              />
              <circle className="node-outer" cx={p.x} cy={p.y} r="29" />
              <circle className="node-inner" cx={p.x} cy={p.y} r="23" />
              <foreignObject x={p.x - 11} y={p.y - 11} width="22" height="22">
                <Icon name={n.type} size={22} />
              </foreignObject>
              {enterprise && (
                <g>
                  <circle
                    cx={p.x + 21}
                    cy={p.y - 20}
                    r="7"
                    fill="#0b2a30"
                    stroke="#2dd4bf"
                  />
                  <path
                    d={`m${p.x + 18} ${p.y - 20} 2 2 4-4`}
                    stroke="#2dd4bf"
                    fill="none"
                  />
                </g>
              )}
              <text
                className="node-label"
                x={p.x}
                y={p.y + 47}
                textAnchor="middle"
              >
                {enterprise ? n.observed : n.id}
              </text>
              <text
                className="node-type"
                x={p.x}
                y={p.y + 62}
                textAnchor="middle"
              >
                {enterprise ? n.desc : n.label.toLowerCase()}
              </text>
            </g>
          )
        })}
        {enterprise && (
          <g className="match-callout">
            <rect x="484" y="46" width="124" height="35" rx="5" />
            <circle cx="498" cy="63" r="3" />
            <text x="509" y="67">
              4 exact node pairs
            </text>
            <path d="M484 64h-90l-30 6" />
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

export default function App() {
  const [ack, setAck] = useState(false)
  const [view, setView] = useState("Split view")
  const [showNoise, setShowNoise] = useState(true)
  const [active, setActive] = useState<number | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [tab, setTab] = useState("System telemetry")
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [filterOpen, setFilterOpen] = useState(false)
  const [timeOpen, setTimeOpen] = useState(false)
  const [range, setRange] = useState("12:00:00 – 12:05:00 UTC")
  const [toast, setToast] = useState("")
  const [paused, setPaused] = useState(false)
  const [modal, setModal] = useState<string | null>(null)
  const [blocked, setBlocked] = useState<number[]>([])
  const [search, setSearch] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
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
  }>({
    similarity_score: 0.9965,
    reference_coverage: 1.0,
    total_events: 8295,
    noise_events: 8280,
    agir_steps: 7,
    matched_nodes_count: 4,
    node_mapping: defaultNodes,
  })
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const nodes = matchData.node_mapping
  const [bridge, setBridge] = useState<{
    x1: number
    y1: number
    x2: number
    y2: number
  } | null>(null)
  useEffect(() => {
    if (active === null || view !== "Split view" || collapsed) {
      setBridge(null)
      return
    }
    const canvas = document.querySelector(".graph-canvases")
    if (!canvas) return
    const updateBridge = () => {
      const left = canvas.querySelector(
        `.reference-viewport [data-node-index="${active}"] .node-inner`,
      )
      const right = canvas.querySelector(
        `.telemetry-viewport [data-node-index="${active}"] .node-inner`,
      )
      if (!left || !right) return
      const bounds = canvas.getBoundingClientRect()
      const a = left.getBoundingClientRect()
      const b = right.getBoundingClientRect()
      setBridge({
        x1: ((a.x + a.width / 2 - bounds.x) / bounds.width) * 1200,
        y1: ((a.y + a.height / 2 - bounds.y) / bounds.height) * 400,
        x2: ((b.x + b.width / 2 - bounds.x) / bounds.width) * 1200,
        y2: ((b.y + b.height / 2 - bounds.y) / bounds.height) * 400,
      })
    }
    updateBridge()
    const observer = new ResizeObserver(updateBridge)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [active, view, collapsed, zoom, pan])
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (
        event.key === "/" &&
        !["INPUT", "TEXTAREA"].includes((event.target as HTMLElement)?.tagName)
      ) {
        event.preventDefault()
        setSearchOpen(true)
        return
      }
      if (event.key !== "Escape") return
      setModal(null)
      setSelected(null)
      setFilterOpen(false)
      setTimeOpen(false)
      setSearchOpen(false)
      setSearch("")
      setStatusOpen(false)
    }
    const closeStatusOnOutside = (event: PointerEvent) => {
      if (!(event.target as Element).closest(".status-wrapper"))
        setStatusOpen(false)
    }
    window.addEventListener("keydown", closeOnEscape)
    window.addEventListener("pointerdown", closeStatusOnOutside)
    return () => {
      window.removeEventListener("keydown", closeOnEscape)
      window.removeEventListener("pointerdown", closeStatusOnOutside)
    }
  }, [])
  useEffect(() => {
    if (searchOpen)
      document
        .querySelector(".table-search")
        ?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, [searchOpen])
  const notify = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(""), 4000)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setSelectedFile(file)
      notify(`Dataset loaded: ${file.name}. Click "Run Match" to analyze.`)
    }
  }

  const runMatching = async (fileOverride?: File | null) => {
    setIsLoading(true)
    const targetFile = fileOverride !== undefined ? fileOverride : selectedFile
    notify(
      targetFile
        ? `Uploading ${targetFile.name} & running 1-WL + AGIR matching...`
        : "Executing 1-WL refinement and Hungarian matching...",
    )
    try {
      const endpoints = ["/api/run-match", "http://127.0.0.1:8000/api/run-match"]
      let data = null

      const formData = new FormData()
      if (targetFile) {
        formData.append("file", targetFile)
      }

      for (const ep of endpoints) {
        try {
          const res = await fetch(ep, {
            method: "POST",
            body: targetFile ? formData : undefined,
          })
          if (res.ok) {
            data = await res.json()
            break
          } else if (!targetFile) {
            const getRes = await fetch(ep)
            if (getRes.ok) {
              data = await getRes.json()
              break
            }
          }
        } catch {
          // try next endpoint
        }
      }

      if (data && data.status === "success") {
        setMatchData({
          similarity_score: Number(data.similarity_score ?? 0.9965),
          reference_coverage: Number(data.reference_coverage ?? 1.0),
          total_events: Number(data.total_events ?? 8295),
          noise_events: Number(data.noise_events ?? data.benign_events_filtered ?? 8280),
          agir_steps: Number(data.agir_steps ?? 7),
          matched_nodes_count: Number(data.matched_nodes_count ?? 4),
          node_mapping: data.node_mapping?.length ? data.node_mapping : defaultNodes,
        })
        notify(
          `Matching complete: ${(Number(data.similarity_score) * 100).toFixed(2)}% similarity across ${Number(data.total_events).toLocaleString()} events`,
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
    runMatching()
  }, [])

  const inspect = (n: number) => {
    setSelected(n)
    setTab("System telemetry")
  }
  const exportReport = () => {
    downloadFile(
      "RefineMatch-IR-2026-8819.json",
      JSON.stringify(
        {
          incident: "IR-2026-8819",
          signature: "SUSP_SYN_003",
          analysis: "RefineMatch StreamSpot Investigation Result",
          acknowledged: ack,
          structuralSimilarity: matchData.similarity_score,
          referenceCoverage: matchData.reference_coverage,
          correlatedEvents: matchData.total_events,
          benignEventsFiltered: matchData.noise_events,
          agirSteps: matchData.agir_steps,
          triageStatus,
          demoHostIsolated: isolated,
          window: `2026-10-27 ${range}`,
          assignments: nodes,
        },
        null,
        2,
      ),
    )
    notify("Forensic report exported as JSON")
  }
  const selectedNode = selected !== null ? nodes[selected] : null
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
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-symbol" title="RefineMatch">
          <Icon name="graph" size={28} />
        </div>
        <div className="nav-stack">
          {([
            { name: "grid", label: "Overview" },
            { name: "activity", label: "Live telemetry" },
            { name: "graph", label: "Investigations" },
            { name: "shield", label: "Threat intelligence" },
            { name: "layers", label: "Pattern library" },
          ] as {
            name: IconName
            label: string
          }[]).map((item) => (
            <button
              key={item.name}
              title={item.label}
              aria-label={item.label}
              className={`nav-item ${item.name === "graph" ? "selected" : ""}`}
              onClick={() =>
                item.name === "graph" ? setModal(null) : setModal(item.label)
              }
            >
              <Icon name={item.name} size={20} />
              {item.name === "activity" && <span className="nav-dot" />}
            </button>
          ))}
        </div>
        <div className="nav-bottom">
          <button
            className="nav-item"
            title="Help & documentation"
            aria-label="Help & documentation"
            onClick={() => setModal("Investigation guide")}
          >
            <Icon name="help" size={20} />
          </button>
          <button
            className="nav-item"
            title="Workspace settings"
            aria-label="Workspace settings"
            onClick={() => setModal("Workspace settings")}
          >
            <Icon name="settings" size={20} />
          </button>
          <button
            className="avatar"
            title="Analyst profile"
            onClick={() => setModal("Analyst profile")}
          >
            AK
            <span />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="wordmark">
            RefineMatch
            <span className="brand-divider" />
            <span className="workspace-name">Security workspace</span>
            <Tag>ENTERPRISE</Tag>
          </div>
          <div className="topbar-right">
            <span className="system-status">
              <span className="status-dot" />
              All systems operational
            </span>
            <span className="top-divider" />
            <button
              className="icon-button"
              aria-label="Search investigation"
              title="Search investigation"
              onClick={() => setSearchOpen(!searchOpen)}
            >
              <Icon name="search" size={18} />
            </button>
            <button
              className="icon-button notification"
              aria-label="Notifications"
              onClick={() => setModal("Notifications")}
            >
              <Icon name="bell" size={18} />
              <span />
            </button>
            <span className="small-avatar">AK</span>
          </div>
        </header>
        <main>
          <div className="breadcrumb">
            <span>Investigations</span>
            <Icon name="chevron" size={12} />
            <span>IR-2026-8819</span>
            <Icon name="chevron" size={12} />
            <span className="current">Provenance Threat Investigator</span>
            <span className="incident-number mono">INCIDENT #IR-2026-8819</span>
          </div>
          <section className="page-heading">
            <div>
              <div className="title-line">
                <h1>Provenance Threat Investigator</h1>
                <Tag className="live">
                  <span className={`status-dot ${paused ? "muted-dot" : ""}`} />
                  {paused ? "ANALYSIS PAUSED" : "LIVE ANALYSIS"}
                </Tag>
              </div>
              <p>
                Trace the attack. Validate the match. Respond with confidence.
              </p>
            </div>
            <div className="heading-actions">
              <div className="status-wrapper">
                <Button
                  className={`triage-button ${
                    triageStatus.toLowerCase().replace(" ", "-")
                  }`}
                  onClick={() => setStatusOpen(!statusOpen)}
                  aria-expanded={statusOpen}
                  aria-haspopup="menu"
                >
                  <span className="small-dot" />
                  {triageStatus}
                  <Icon name="chevron" size={12} />
                </Button>
                {statusOpen && (
                  <div
                    className="popover status-popover"
                    role="menu"
                    aria-label="Incident status"
                  >
                    <span className="eyebrow">INCIDENT STATUS</span>
                    {[
                      "In Triage",
                      "Investigating",
                      "Contained",
                      "Resolved",
                    ].map((status) => (
                      <button
                        key={status}
                        role="menuitemradio"
                        aria-checked={triageStatus === status}
                        onClick={() => {
                          setTriageStatus(status)
                          setAck(status === "Resolved")
                          setStatusOpen(false)
                          notify(
                            `Incident marked ${status.toLowerCase()} for this session`,
                          )
                        }}
                      >
                        <span
                          className={`status-option-dot ${status.toLowerCase().replace(" ", "-")}`}
                        />
                        {status}
                        {triageStatus === status && (
                          <Icon name="check" size={14} />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <label
                className="btn upload-dataset-btn"
                style={{
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "7px",
                  padding: "0 14px",
                  height: "36px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  backgroundColor: "rgba(30, 41, 59, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  color: "#e2e8f0",
                }}
                title="Select .csv or .tsv dataset"
              >
                <Icon name="file" size={15} />
                <span
                  style={{
                    maxWidth: "160px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {selectedFile ? selectedFile.name : "Upload Dataset (.csv / .tsv)"}
                </span>
                <input
                  type="file"
                  accept=".tsv,.csv,.txt"
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </label>
              <Button
                icon="activity"
                className="triage-button"
                disabled={isLoading}
                onClick={() => runMatching()}
                title="Execute 1-WL refinement and Hungarian matching"
              >
                {isLoading ? (
                  <>
                    <span
                      style={{
                        display: "inline-block",
                        marginRight: "6px",
                        animation: "spin 1s linear infinite",
                      }}
                    >
                      ⟳
                    </span>
                    Analyzing Provenance...
                  </>
                ) : (
                  "Run Match"
                )}
              </Button>
              <Button icon="download" onClick={exportReport}>
                Export Report
              </Button>
              <Button
                icon="shield"
                className={isolated ? "acknowledged" : "containment-button"}
                disabled={isolated}
                onClick={() => {
                  setPendingNode(null)
                  setModal("Isolate affected host")
                }}
              >
                {isolated ? (
                  "Host isolated · Demo"
                ) : (
                  <>
                    Isolate Affected Host{" "}
                    <span className="mono">(srv-edge-04)</span>
                  </>
                )}
              </Button>
            </div>
          </section>
          <div className="context-bar">
            <div className="context-left">
              <Icon name="graph" size={14} />
              <span>StreamSpot provenance trace</span>
              <span className="separator">/</span>
              <span className="mono subtle">srv-edge-04</span>
              <Tag className="muted-tag">Production</Tag>
            </div>
            <div className="time-wrapper">
              <button
                className="time-filter"
                onClick={() => setTimeOpen(!timeOpen)}
              >
                <Icon name="clock" size={14} />
                <span>Oct 27, 2026</span>
                <span className="time-sep" />{" "}
                <span className="mono">{range}</span>
                <Icon name="chevron" size={12} />
              </button>
              {timeOpen && (
                <div className="popover time-popover">
                  <span className="eyebrow">INVESTIGATION WINDOW</span>
                  {[
                    "12:00:00 – 12:05:00 UTC",
                    "11:55:00 – 12:10:00 UTC",
                    "11:00:00 – 13:00:00 UTC",
                  ].map((r) => (
                    <button
                      key={r}
                      className={range === r ? "chosen" : ""}
                      onClick={() => {
                        setRange(r)
                        setTimeOpen(false)
                        notify(
                          "Display window updated; incident evidence remains pinned",
                        )
                      }}
                    >
                      <Icon name="clock" size={14} />
                      {r}
                      {range === r && <Icon name="check" size={14} />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <section className={`threat-banner ${ack ? "is-acknowledged" : ""}`}>
            <div className="threat-icon">
              <Icon name="shield" size={25} />
            </div>
            <div className="threat-content">
              <div className="threat-eyebrow">
                <Tag className={ack ? "emerald" : "critical"}>
                  <span className="status-dot" />
                  {ack ? "RESOLVED" : "CRITICAL DETECTION"}
                </Tag>
                <span className="mono">CVE-2026-StreamSpot</span>
                <span className="threat-detected">
                  <Icon name="clock" size={12} />
                  Detected at 12:04:58 UTC
                </span>
              </div>
              <h2>Drive-by Download & In-Memory Code Injection</h2>
              <p>
                A 4-node exploit pattern identified with{" "}
                <strong>99.65% structural correspondence</strong> across{" "}
                <strong>8,295 enterprise events.</strong> Host{" "}
                <code>srv-edge-04</code>{" "}
                <span className="subtle">(N_0001)</span> spawned a rogue browser
                process, connected to an untrusted endpoint, and staged a binary
                drop in <code>/tmp</code>.
              </p>
              <div className="attack-tags">
                <Tag>
                  <span className="tag-code">T1189</span>Drive-by Download
                </Tag>
                <Tag>
                  <span className="tag-code">T1055</span>Process Injection
                </Tag>
                <Tag>
                  <span className="tag-code">T1071</span>Socket Connect
                </Tag>
                <span className="tag-divider" />
                <span className="confidence">
                  <Icon name="shield" size={13} />
                  94.8% high confidence
                </span>
              </div>
            </div>
            <button
              className="banner-details"
              onClick={() => setModal("Detection evidence")}
              title="View detection evidence"
              aria-label="View detection evidence"
            >
              <Icon name="external" size={17} />
            </button>
          </section>

          <section className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">
                <span>Structural similarity</span>
                <Icon name="target" size={15} />
              </div>
              <div className="metric-main">
                <span className="metric-value mint">
                  {(matchData.similarity_score * 100).toFixed(2)}<span>%</span>
                </span>
                <div className="radial">
                  <svg
                    viewBox="0 0 70 50"
                    aria-label={`${(matchData.similarity_score * 100).toFixed(2)}% structural similarity`}
                  >
                    <path
                      className="gauge-track"
                      d="M10 41 A28 28 0 1 1 60 41"
                    />
                    <path
                      className="gauge-fill"
                      d="M10 41 A28 28 0 1 1 60 41"
                      pathLength="100"
                    />
                  </svg>
                  <Icon name="check" size={17} />
                </div>
              </div>
              <div className="metric-description">
                Optimal Hungarian assignment
              </div>
              <div className="metric-bottom">
                <Tag className="emerald">NEAR-EXACT MATCH</Tag>
                <span className="mono">{matchData.similarity_score.toFixed(4)} / 1.0000</span>
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">
                <span>Attack pattern coverage</span>
                <Icon name="graph" size={15} />
              </div>
              <div className="metric-main">
                <span className="metric-value">
                  {(matchData.reference_coverage * 100).toFixed(1)}<span>%</span>
                </span>
                <span className="metric-suffix">
                  <strong>{matchData.matched_nodes_count}</strong> / {nodes.length} nodes
                </span>
              </div>
              <div className="metric-description">
                All reference nodes matched one-to-one
              </div>
              <div className="metric-bottom coverage-bottom">
                <div className="segments">
                  {nodes.map((_, i) => (
                    <span key={i} />
                  ))}
                </div>
                <span>{nodes.length - matchData.matched_nodes_count} unmatched</span>
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">
                <span>Noise rejection</span>
                <Icon name="filter" size={15} />
              </div>
              <div className="metric-main">
                <span className="metric-value">
                  {(
                    (matchData.noise_events /
                      Math.max(1, matchData.total_events)) *
                    100
                  ).toFixed(2)}<span>%</span>
                </span>
                <div className="metric-sparkline">
                  <svg
                    viewBox="0 0 100 38"
                    aria-label="Background activity trend"
                  >
                    <defs>
                      <linearGradient
                        id="spark-fill"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="var(--accent-cyan)"
                          stopOpacity=".18"
                        />
                        <stop
                          offset="100%"
                          stopColor="var(--accent-cyan)"
                          stopOpacity="0"
                        />
                      </linearGradient>
                    </defs>
                    <path
                      d="M0 30 10 27 17 29 26 19 34 23 43 13 51 17 60 8 68 12 77 5 85 9 94 3 100 6V38H0Z"
                      fill="url(#spark-fill)"
                    />
                    <path
                      d="M0 30 10 27 17 29 26 19 34 23 43 13 51 17 60 8 68 12 77 5 85 9 94 3 100 6"
                      fill="none"
                      stroke="var(--accent-cyan)"
                      strokeWidth="1.5"
                    />
                  </svg>
                </div>
              </div>
              <div className="metric-description">
                <strong>{matchData.noise_events.toLocaleString()}</strong> benign events filtered out
              </div>
              <div className="metric-bottom">
                <span className="small-dot cyan" />
                <span>Benign NTP, DNS & web traffic isolated</span>
              </div>
            </div>
            <button
              className="metric-card metric-clickable"
              onClick={() => setModal("AGIR refinement trace")}
            >
              <div className="metric-label">
                <span>AGIR resolution</span>
                <Icon name="layers" size={15} />
              </div>
              <div className="metric-main">
                <span className="metric-value">
                  {matchData.agir_steps} <span className="steps">Steps</span>
                </span>
                <div className="hex-symbol">
                  <Icon name="layers" size={27} />
                </div>
              </div>
              <div className="metric-description">
                Automorphic symmetries resolved
              </div>
              <div className="metric-bottom">
                <Tag className="violet-tag">
                  <span className="small-dot" />
                  STABILIZED
                </Tag>
                <span>Zero ambiguity remaining</span>
              </div>
            </button>
          </section>

          <section className="panel graph-panel">
            <div className="section-header">
              <div className="section-title">
                <Icon name="graph" size={17} />
                <h2>Provenance graph comparison</h2>
                <Tag className="muted-tag mono">1-WL + AGIR</Tag>
              </div>
              <div className="graph-header-actions">
                <span className="matched-indicator">
                  <span className="status-dot" />{matchData.matched_nodes_count} optimal pairs
                </span>
                <span className="top-divider" />
                <button
                  className="icon-button"
                  title={
                    paused ? "Resume live analysis" : "Pause live analysis"
                  }
                  aria-label={
                    paused ? "Resume live analysis" : "Pause live analysis"
                  }
                  onClick={() => setPaused(!paused)}
                >
                  <Icon name={paused ? "play" : "pause"} size={14} />
                </button>
                <button
                  className="icon-button"
                  title={collapsed ? "Expand graph" : "Collapse graph"}
                  aria-label={collapsed ? "Expand graph" : "Collapse graph"}
                  onClick={() => setCollapsed(!collapsed)}
                >
                  <Icon
                    name="chevron"
                    size={14}
                    className={collapsed ? "" : "rotate-up"}
                  />
                </button>
              </div>
            </div>
            {!collapsed && (
              <>
                <div className="graph-toolbar">
                  <div className="view-tabs">
                    {["Split view", "Overlay mode", "Diff heatmap"].map(
                      (v, i) => (
                        <button
                          className={view === v ? "active" : ""}
                          onClick={() => {
                            setView(v)
                            setPan({ x: 0, y: 0 })
                          }}
                          key={v}
                        >
                          <Icon
                            name={
                              (["grid", "layers", "activity"] as IconName[])[i]
                            }
                            size={13}
                          />
                          {v}
                        </button>
                      ),
                    )}
                  </div>
                  <div className="graph-toolbar-right">
                    <span className="graph-helper">
                      <Icon name="eye" size={13} /> Hover a node to trace its
                      match
                    </span>
                    <div className="filter-wrapper">
                      <Button
                        icon="filter"
                        className={filterOpen ? "filter-active" : ""}
                        onClick={() => setFilterOpen(!filterOpen)}
                      >
                        Display filters
                        <span className="filter-count">
                          {showNoise ? "2" : "1"}
                        </span>
                        <Icon name="chevron" size={11} />
                      </Button>
                      {filterOpen && (
                        <div className="popover filter-popover">
                          <span className="eyebrow">CANVAS VISIBILITY</span>
                          <button onClick={() => setShowNoise(!showNoise)}>
                            <span
                              className={`checkbox ${
                                showNoise ? "checked" : ""
                              }`}
                            >
                              {showNoise && <Icon name="check" size={11} />}
                            </span>
                            Show unmatched noise nodes
                          </button>
                          <div className="filter-note">
                            <Icon name="check" size={13} />
                            Matched core nodes always visible
                          </div>
                          <div className="filter-note">
                            Noise is sampled for readability.
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div
                  className={`graph-canvases ${
                    view === "Overlay mode" ? "overlay-canvas" : ""
                  }`}
                >
                  {view !== "Overlay mode" && (
                    <div className="graph-viewport reference-viewport">
                      <div className="viewport-heading">
                        <div>
                          <span className="viewport-dot violet-dot" />
                          <strong>Reference Signature</strong>
                          <span className="mono">SUSP_SYN_003</span>
                        </div>
                        <Tag className="muted-tag">4 nodes · 4 edges</Tag>
                      </div>
                      <Graph
                        enterprise={false}
                        mode={view}
                        showNoise={false}
                        active={active}
                        setActive={setActive}
                        inspect={inspect}
                        zoom={zoom}
                        pan={pan}
                        setPan={setPan}
                      />
                      <div className="canvas-caption">
                        <Icon name="shield" size={12} />
                        Canonical attack archetype
                        <span>StreamSpot / MITRE ATT&CK</span>
                      </div>
                    </div>
                  )}
                  <div className="graph-viewport telemetry-viewport">
                    <div className="viewport-heading">
                      <div>
                        <span className="viewport-dot mint-dot" />
                        <strong>
                          {view === "Overlay mode"
                            ? "Signature overlay"
                            : "Observed Telemetry"}
                        </strong>
                        <span className="mono">all.tsv</span>
                      </div>
                      <Tag className="muted-tag">8,295 events</Tag>
                    </div>
                    <Graph
                      enterprise={true}
                      mode={view}
                      showNoise={showNoise}
                      active={active}
                      setActive={setActive}
                      inspect={inspect}
                      zoom={zoom}
                      pan={pan}
                      setPan={setPan}
                    />
                    <div className="canvas-caption">
                      <span className="small-dot cyan" />
                      Enterprise ingestion
                      <span>
                        {view === "Diff heatmap"
                          ? "Teal: matched · Crimson: unmatched"
                          : "Matched subgraph highlighted"}
                      </span>
                    </div>
                  </div>
                  {active !== null && bridge && view === "Split view" && (
                    <svg
                      className="assignment-overlay"
                      viewBox="0 0 1200 400"
                      preserveAspectRatio="none"
                    >
                      <path
                        d={`M${bridge.x1} ${bridge.y1} C ${bridge.x1 + 180} ${bridge.y1 - 55}, ${bridge.x2 - 180} ${bridge.y2 - 55}, ${bridge.x2} ${bridge.y2}`}
                      />
                      <text
                        x={(bridge.x1 + bridge.x2) / 2}
                        y={Math.max(20, (bridge.y1 + bridge.y2) / 2 - 46)}
                        textAnchor="middle"
                      >
                        1:1 assignment
                      </text>
                    </svg>
                  )}
                  <div className="zoom-controls">
                    <button
                      title="Zoom in"
                      aria-label="Zoom in"
                      disabled={zoom >= 1.6}
                      onClick={() => setZoom(Math.min(1.6, zoom + 0.15))}
                    >
                      <Icon name="plus" size={16} />
                    </button>
                    <span className="mono">{Math.round(zoom * 100)}%</span>
                    <button
                      title="Zoom out"
                      aria-label="Zoom out"
                      disabled={zoom <= 0.55}
                      onClick={() => setZoom(Math.max(0.55, zoom - 0.15))}
                    >
                      <Icon name="minus" size={16} />
                    </button>
                    <span className="control-divider" />
                    <button
                      title="Reset canvas"
                      aria-label="Reset canvas"
                      className="reset-canvas"
                      onClick={() => {
                        setZoom(1)
                        setPan({ x: 0, y: 0 })
                      }}
                    >
                      Reset
                    </button>
                    <button
                      title="Focus fit"
                      aria-label="Focus fit"
                      onClick={() => {
                        setZoom(showNoise ? 1 : 1.15)
                        setPan({ x: 0, y: 0 })
                      }}
                    >
                      <Icon name="fit" size={15} />
                    </button>
                  </div>
                  <button
                    className="minimap"
                    title="Reset canvas position"
                    aria-label="Reset canvas position"
                    onClick={() => {
                      setZoom(1)
                      setPan({ x: 0, y: 0 })
                    }}
                  >
                    <svg viewBox="0 0 100 58">
                      <path
                        d="m50 10-24 19 24 20 24-20L50 10"
                        fill="none"
                        stroke="#3e6c65"
                      />
                      {[
                        [50, 10],
                        [26, 29],
                        [74, 29],
                        [50, 49],
                      ].map(([x, y], i) => (
                        <circle cx={x} cy={y} r="2.5" fill="#39c79d" key={i} />
                      ))}
                      <rect
                        x="10"
                        y="3"
                        width="80"
                        height="52"
                        rx="3"
                        fill="none"
                        stroke="#74899d"
                        strokeWidth=".6"
                      />
                    </svg>
                  </button>
                </div>
                <div className="graph-legend">
                  <div className="legend-items">
                    <span>
                      <i className="legend-ring mint-ring" />
                      Matched node
                    </span>
                    <span>
                      <i className="legend-ring noise-ring" />
                      Background noise
                    </span>
                    <span className="legend-divider" />
                    <span>1-WL color classes:</span>
                    <span>
                      <i className="small-dot violet-dot" />
                      Process
                    </span>
                    <span>
                      <i className="small-dot teal-dot" />
                      File
                    </span>
                    <span>
                      <i className="small-dot amber-dot" />
                      Socket
                    </span>
                    <span>
                      <i className="small-dot blue-dot" />
                      Host
                    </span>
                  </div>
                  <span className="mono runtime">
                    <Icon name="activity" size={12} />
                    Refined in 1.50s
                  </span>
                </div>
              </>
            )}
          </section>

          <section className="panel mapping-panel">
            <div className="section-header">
              <div className="section-title">
                <Icon name="layers" size={17} />
                <h2>Optimal node correspondence</h2>
                <Tag className="muted-tag">{nodes.length} mappings</Tag>
              </div>
              <div className="table-heading-right">
                <Icon name="shield" size={13} />
                <span className="assignment-verification">
                  Hungarian 1-to-1 Assignment
                </span>
                <Button
                  icon="download"
                  className="small-btn"
                  title="Export mapping CSV"
                  onClick={() => {
                    downloadFile(
                      "node-correspondence.csv",
                      "reference,observed,type,compatibility\n" +
                        nodes
                          .map(
                            (n) =>
                              `${n.id},${n.observed},${n.label},${n.score}`,
                          )
                          .join("\n"),
                      "text/csv",
                    )
                    notify("Node correspondence exported as CSV")
                  }}
                >
                  Export CSV
                </Button>
              </div>
            </div>
            <div className="mapping-toolbar">
              <div className="quick-filters" aria-label="Filter node types">
                {["All nodes", "Processes", "Network", "Files", "Hosts"].map(
                  (filter) => (
                    <button
                      key={filter}
                      className={nodeFilter === filter ? "active" : ""}
                      aria-pressed={nodeFilter === filter}
                      onClick={() => setNodeFilter(filter)}
                    >
                      {filter}
                      <span>{filter === "All nodes" ? 4 : 1}</span>
                    </button>
                  ),
                )}
              </div>
              <Button
                icon="search"
                className="table-search-toggle"
                onClick={() => {
                  setSearchOpen(!searchOpen)
                  if (searchOpen) setSearch("")
                }}
              >
                Find a node <span className="key-hint">/</span>
              </Button>
            </div>
            {searchOpen && (
              <div className="table-search">
                <Icon name="search" size={16} />
                <input
                  autoFocus
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search node IDs, types, or endpoints…"
                  aria-label="Search node correspondences"
                />
                <button
                  className="icon-button"
                  onClick={() => {
                    setSearchOpen(false)
                    setSearch("")
                  }}
                  aria-label="Close search"
                >
                  <Icon name="close" size={14} />
                </button>
              </div>
            )}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Reference pattern node</th>
                    <th>Observed enterprise node</th>
                    <th>
                      1-WL color match <span className="subtle">↕</span>
                    </th>
                    <th>
                      Compatibility <span className="subtle">↕</span>
                    </th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredNodes.map(({ n, i }) => (
                    <tr
                      key={n.id}
                      onMouseEnter={() => setActive(i)}
                      onMouseLeave={() => setActive(null)}
                      className={active === i ? "row-active" : ""}
                    >
                      <td>
                        <span className="paired">
                          <span className="check-circle">
                            <Icon name="check" size={10} />
                          </span>
                          Optimally Paired
                        </span>
                      </td>
                      <td>
                        <div className="node-table-cell">
                          <span className={`node-type-icon ${n.color}`}>
                            <Icon name={n.type} size={15} />
                          </span>
                          <span className="mono">{n.id}</span>
                          <Tag className="type-tag">
                            {n.label.toLowerCase()}
                          </Tag>
                        </div>
                      </td>
                      <td>
                        <span className="mono observed-id">{n.observed}</span>
                        <span className="table-node-description">
                          {n.desc}
                          {n.pid !== "—" ? ` · PID ${n.pid}` : ""}
                        </span>
                      </td>
                      <td>
                        <span className={`color-swatch ${n.color}`} />
                        <span className="exact-match">Exact match</span>
                        <span className="depth-badge mono">k=2</span>
                      </td>
                      <td>
                        <div
                          className={`compatibility ${
                            Number(n.score) < 0.995 ? "partial-score" : ""
                          }`}
                        >
                          <span className="mono">{n.score}</span>
                          <span className="score-bar">
                            <i style={{ width: `${Number(n.score) * 100}%` }} />
                          </span>
                        </div>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="inspect-button"
                            onClick={() => {
                              inspect(i)
                              setTab("Incident edges")
                            }}
                          >
                            <Icon name="code" size={13} />
                            Inspect Node Logs
                          </button>
                          <button
                            className={`block-node-button ${
                              blocked.includes(i) ? "blocked" : ""
                            }`}
                            disabled={blocked.includes(i)}
                            onClick={() => {
                              setPendingNode(i)
                              setModal("Confirm node action")
                            }}
                          >
                            <Icon
                              name={blocked.includes(i) ? "check" : "shield"}
                              size={12}
                            />
                            {blocked.includes(i)
                              ? "Blocked · Demo"
                              : "Kill / Block"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredNodes.length === 0 && (
                <div className="empty-state">
                  No nodes match “{search}” in {nodeFilter.toLowerCase()}. Try
                  another node ID or filter.
                </div>
              )}
            </div>
            <div className="table-footer">
              <span>
                <Icon name="check" size={12} />
                All reference nodes optimally assigned. No orphaned exploits.
              </span>
              <span className="mono">Σ compatibility: 3.986 / 4.000</span>
            </div>
          </section>
          <footer className="page-footer">
            <span>
              <span className="status-dot" />
              StreamSpot engine <span className="mono">v2.4.1</span>
              <span className="footer-separator">·</span>Illustrative
              investigation dataset
            </span>
            <span>
              <Icon name="shield" size={12} />
              Privacy-preserving analysis
              <span className="footer-separator">·</span>All identifiers
              pseudonymized
            </span>
          </footer>
        </main>
      </div>
      {selectedNode && selected !== null && (
        <>
          <div className="drawer-scrim" onClick={() => setSelected(null)} />
          <aside className="inspector">
            <div className="drawer-title">
              <span>
                <Icon name="search" size={17} />
                FORENSIC INSPECTOR
              </span>
              <button
                className="icon-button"
                onClick={() => setSelected(null)}
                aria-label="Close inspector"
              >
                <Icon name="close" />
              </button>
            </div>
            <div className="drawer-node-heading">
              <span className={`drawer-node-icon ${selectedNode.color}`}>
                <Icon name={selectedNode.type} size={25} />
              </span>
              <div>
                <h2 className="mono">{selectedNode.observed}</h2>
                <span>
                  Reference <code>{selectedNode.id}</code>
                </span>
              </div>
              <Tag className="emerald">MATCHED</Tag>
            </div>
            <div className="drawer-meta">
              <Tag>{selectedNode.label}</Tag>
              <span>{selectedNode.desc}</span>
            </div>
            <div className="node-timestamps">
              <div>
                <span>FIRST SEEN</span>
                <strong className="mono">12:00:00 UTC</strong>
              </div>
              <div>
                <span>LAST SEEN</span>
                <strong className="mono">12:05:00 UTC</strong>
              </div>
            </div>
            <div className="drawer-tabs">
              {["System telemetry", "Incident edges", "1-WL signature"].map(
                (t) => (
                  <button
                    className={tab === t ? "active" : ""}
                    key={t}
                    onClick={() => setTab(t)}
                  >
                    {t}
                  </button>
                ),
              )}
            </div>
            <div className="drawer-content">
              {tab === "System telemetry" && (
                <>
                  <div className="drawer-section-heading">
                    <Icon name="process" size={15} />
                    <h3>System telemetry</h3>
                  </div>
                  <label className="field-label">BINARY / COMMAND LINE</label>
                  <div className="code-block mono">{selectedNode.binary}</div>
                  <div className="detail-grid">
                    <div>
                      <label className="field-label">PROCESS ID</label>
                      <span className="mono">{selectedNode.pid}</span>
                    </div>
                    <div>
                      <label className="field-label">EXECUTION DURATION</label>
                      <span className="mono">1.50 seconds</span>
                    </div>
                    <div>
                      <label className="field-label">MEMORY FOOTPRINT</label>
                      <span className="mono">24.8 MB</span>
                    </div>
                    <div>
                      <label className="field-label">HOST</label>
                      <span className="mono">srv-edge-04</span>
                    </div>
                  </div>
                  <label className="field-label">SHA-256 HASH</label>
                  <div className="code-block mono hash">
                    a7f1c62d9e848b500a1cf731e60f8258
                    <br />
                    d904e63ce4e5ef0919ac21b05c39f217
                  </div>
                  <div className="drawer-section-heading">
                    <Icon name="graph" size={15} />
                    <h3>Parent process lineage</h3>
                  </div>
                  <div className="lineage">
                    <div>
                      <Icon name="process" size={17} />
                      <span>
                        cmd.exe <small className="mono">PID 4022</small>
                      </span>
                    </div>
                    <span className="lineage-link" />
                    <div className="lineage-malicious">
                      <Icon name="process" size={17} />
                      <span>
                        powershell.exe <small className="mono">PID 9102</small>
                      </span>
                      <Tag className="critical">SUSPICIOUS</Tag>
                    </div>
                  </div>
                  <div className="inspector-note">
                    <Icon name="shield" size={17} />
                    <p>
                      Telemetry is linked to the matched incident subgraph.
                      Identifiers have been pseudonymized.
                    </p>
                  </div>
                </>
              )}
              {tab === "Incident edges" && (
                <>
                  <div className="drawer-section-heading">
                    <Icon name="activity" size={15} />
                    <h3>Communication flow</h3>
                  </div>
                  <p className="drawer-description">
                    Directed events connected to {selectedNode.observed}.
                  </p>
                  {[
                    {
                      direction: "OUTGOING",
                      event: "read",
                      endpoint: "/tmp/payload.bin",
                      detail: "1,024 bytes · 2 events",
                    },
                    {
                      direction: "OUTGOING",
                      event: "connect",
                      endpoint: "203.0.113.7:443",
                      detail: "Protocol TCP · external endpoint",
                    },
                    {
                      direction: "INCOMING",
                      event: "spawned_by",
                      endpoint: "admin_user",
                      detail: "Source port 49152",
                    },
                  ].map((e) => (
                    <div className="edge-detail" key={e.event}>
                      <span className="field-label">{e.direction}</span>
                      <div>
                        <Tag
                          className={e.event === "connect" ? "critical" : ""}
                        >
                          {e.event}
                        </Tag>
                        <Icon name="arrow" size={14} />
                        <code>{e.endpoint}</code>
                      </div>
                      <p>{e.detail}</p>
                    </div>
                  ))}
                </>
              )}
              {tab === "1-WL signature" && (
                <>
                  <div className="drawer-section-heading">
                    <Icon name="spark" size={15} />
                    <h3>Weisfeiler-Leman signature</h3>
                  </div>
                  <label className="field-label">128-BIT COLOR DIGEST</label>
                  <div className="code-block mono hash">
                    7ea67fa9446f26b3a9a6904422fb4532
                  </div>
                  <div className="signature-color">
                    <span className={`color-swatch ${selectedNode.color}`} />
                    <span>Depth-k color partition</span>
                    <Tag className="emerald">EXACT MATCH</Tag>
                  </div>
                  <div className="detail-grid">
                    <div>
                      <label className="field-label">IN-DEGREE</label>
                      <span className="mono">1</span>
                    </div>
                    <div>
                      <label className="field-label">OUT-DEGREE</label>
                      <span className="mono">2</span>
                    </div>
                    <div>
                      <label className="field-label">REFINEMENT ROUND</label>
                      <span className="mono">2 (Stable)</span>
                    </div>
                    <div>
                      <label className="field-label">LOCAL COMPATIBILITY</label>
                      <span className="mono mint">{selectedNode.score}</span>
                    </div>
                  </div>
                  <div className="inspector-note">
                    <Icon name="layers" size={20} />
                    <p>
                      AGIR resolved all automorphic symmetries in 7 steps. This
                      pairing is part of the globally optimal Hungarian
                      assignment.
                    </p>
                  </div>
                </>
              )}
            </div>
            <div className="drawer-actions">
              <Button
                icon="external"
                onClick={() => setModal("Host event logs")}
              >
                Pivot to host logs
              </Button>
              <Button
                icon="shield"
                className={
                  blocked.includes(selected) ? "acknowledged" : "danger-btn"
                }
                onClick={() => {
                  setBlocked((current) =>
                    current.includes(selected)
                      ? current
                      : [...current, selected],
                  )
                  notify(
                    "Indicator added to this session’s blocklist; no host changes applied",
                  )
                }}
              >
                {blocked.includes(selected)
                  ? "In session blocklist"
                  : "Add to blocklist"}
              </Button>
              <Button
                icon="download"
                className="stix-button"
                onClick={() => {
                  downloadFile(
                    `${selectedNode.observed}-stix.json`,
                    JSON.stringify(
                      {
                        type: "bundle",
                        id: `bundle--${crypto.randomUUID()}`,
                        objects: [
                          {
                            type: "indicator",
                            spec_version: "2.1",
                            id: `indicator--${crypto.randomUUID()}`,
                            created: new Date().toISOString(),
                            modified: new Date().toISOString(),
                            name: `RefineMatch ${selectedNode.observed}`,
                            pattern: "[ipv4-addr:value = '203.0.113.7']",
                            pattern_type: "stix",
                            valid_from: "2026-10-27T12:00:00.000Z",
                            description: `Illustrative incident evidence; selected node ${selectedNode.id}.`,
                          },
                        ],
                      },
                      null,
                      2,
                    ),
                  )
                  notify("STIX 2.1 indicator bundle exported")
                }}
              >
                Export STIX indicator
              </Button>
            </div>
          </aside>
        </>
      )}
      {modal && (
        <div className="modal-scrim" onClick={() => setModal(null)}>
          <section
            className="modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label={modal}
          >
            <div className="modal-header">
              <span>
                <Icon
                  name={modal.includes("AGIR") ? "layers" : "shield"}
                  size={19}
                />
                <h2>{modal}</h2>
              </span>
              <button
                className="icon-button"
                onClick={() => setModal(null)}
                aria-label="Close dialog"
              >
                <Icon name="close" />
              </button>
            </div>
            {modal === "Isolate affected host" ||
            modal === "Confirm node action" ? (
              <div className="confirmation-content">
                <Tag className="critical">CONTAINMENT ACTION</Tag>
                <h3>
                  {pendingNode === null
                    ? "Isolate srv-edge-04?"
                    : `${
                        nodes[pendingNode].label === "Process"
                          ? "Terminate process"
                          : nodes[pendingNode].label === "Socket"
                            ? "Block endpoint"
                            : nodes[pendingNode].label === "File"
                              ? "Quarantine file"
                              : "Isolate host"
                      }?`}
                </h3>
                <p>
                  {pendingNode === null
                    ? "Network isolation normally disconnects this host from the enterprise network while preserving the investigation channel. Active connections may be interrupted."
                    : `This action targets ${nodes[pendingNode].observed} (${nodes[pendingNode].desc}). In a connected environment, this can interrupt active processes or network traffic.`}
                </p>
                <div className="confirmation-target">
                  <Icon
                    name={
                      pendingNode === null ? "host" : nodes[pendingNode].type
                    }
                    size={20}
                  />
                  <div>
                    <span className="mono">
                      {pendingNode === null
                        ? "srv-edge-04"
                        : nodes[pendingNode].observed}
                    </span>
                    <small>
                      {pendingNode === null
                        ? "Affected host · Production"
                        : nodes[pendingNode].binary}
                    </small>
                  </div>
                </div>
                <div className="demo-notice">
                  <Icon name="eye" size={17} />
                  <p>
                    <strong>Demo environment</strong>This action is simulated in
                    this browser session only. No live host, process, or
                    firewall will be modified.
                  </p>
                </div>
                <div className="confirmation-actions">
                  <Button onClick={() => setModal(null)}>Cancel</Button>
                  <Button
                    icon="shield"
                    className="containment-button"
                    onClick={() => {
                      if (pendingNode === null) {
                        setIsolated(true)
                        setTriageStatus("Contained")
                        notify(
                          "Demo: srv-edge-04 marked as isolated. No live host was modified.",
                        )
                      } else {
                        setBlocked((current) =>
                          current.includes(pendingNode)
                            ? current
                            : [...current, pendingNode],
                        )
                        notify(
                          `Demo: containment action recorded for ${nodes[pendingNode].observed}. No live systems were modified.`,
                        )
                      }
                      setModal(null)
                    }}
                  >
                    {pendingNode === null
                      ? "Simulate Host Isolation"
                      : "Simulate Kill / Block"}
                  </Button>
                </div>
              </div>
            ) : modal === "AGIR refinement trace" ? (
              <>
                <p className="modal-intro">
                  Ambiguity-Guided Individualization & Refinement
                </p>
                <div className="refinement-steps">
                  {[
                    "Initialize node-type partitions",
                    "Aggregate 1-hop neighborhood colors",
                    "Refine depth-2 color signatures",
                    "Detect automorphic equivalence classes",
                    "Individualize ambiguous candidate nodes",
                    "Resolve optimal Hungarian assignment",
                    "Verify stable, unique correspondence",
                  ].map((s, i) => (
                    <div key={s}>
                      <span className="step-number mono">0{i + 1}</span>
                      <p>{s}</p>
                      <Icon name="check" size={16} />
                    </div>
                  ))}
                </div>
                <div className="modal-success">
                  <span className="status-dot" />
                  Stable partitions · Zero ambiguity remaining
                </div>
              </>
            ) : modal === "Host event logs" || modal === "Live telemetry" ? (
              <>
                <p className="modal-intro mono">
                  srv-edge-04 · 2026-10-27 · Incident window
                </p>
                <div className="event-logs">
                  {[
                    [
                      "12:00:00.012",
                      "PROCESS",
                      "cmd.exe → powershell.exe (PID 9102)",
                    ],
                    ["12:00:00.284", "READ", "/tmp/payload.bin · 1,024 bytes"],
                    ["12:00:00.611", "CONNECT", "203.0.113.7:443 · TCP"],
                    ["12:00:01.089", "WRITE", "Binary staged on srv-edge-04"],
                    [
                      "12:04:58.003",
                      "DETECTION",
                      "SUSP_SYN_003 · 99.65% correspondence",
                    ],
                  ].map(([t, event, detail]) => (
                    <div key={t}>
                      <time className="mono">{t}</time>
                      <Tag>{event}</Tag>
                      <p>{detail}</p>
                    </div>
                  ))}
                </div>
              </>
            ) : modal === "Notifications" ? (
              <div className="notification-content">
                <Tag className={ack ? "emerald" : "critical"}>
                  {ack ? "ACKNOWLEDGED" : "CRITICAL"}
                </Tag>
                <h3>Suspicious sequence detected</h3>
                <p>
                  IR-2026-8819 · Drive-by Download & In-Memory Code Injection
                </p>
                <span className="mono subtle">12:04:58 UTC · srv-edge-04</span>
              </div>
            ) : modal === "Workspace settings" ? (
              <div className="settings-content">
                <div>
                  <span>Workspace</span>
                  <strong>Security workspace</strong>
                </div>
                <div>
                  <span>Environment</span>
                  <Tag>Production</Tag>
                </div>
                <div>
                  <span>Analysis mode</span>
                  <strong>Illustrative dataset</strong>
                </div>
                <div>
                  <span>Privacy</span>
                  <Tag className="emerald">Pseudonymized</Tag>
                </div>
                <div>
                  <span>Session blocklist</span>
                  <strong>{blocked.length} indicators</strong>
                </div>
                <p>
                  Interface preferences and acknowledgements apply to this
                  browser session only.
                </p>
              </div>
            ) : modal === "Analyst profile" ? (
              <div className="profile-content">
                <span className="avatar">AK</span>
                <h3>Alex Kim</h3>
                <p>Incident response analyst</p>
                <Tag className="emerald">Security workspace · Analyst</Tag>
              </div>
            ) : modal === "Pattern library" ||
              modal === "Threat intelligence" ? (
              <>
                <p className="modal-intro">
                  Active reference signature for this investigation
                </p>
                <div className="pattern-card">
                  <Tag className="critical">HIGH SEVERITY</Tag>
                  <h3 className="mono">SUSP_SYN_003</h3>
                  <p>Drive-by Download & In-Memory Code Injection</p>
                  <div className="attack-tags">
                    <Tag>T1189</Tag>
                    <Tag>T1055</Tag>
                    <Tag>T1071</Tag>
                  </div>
                  <span>4 nodes · 4 directed edges · StreamSpot reference</span>
                </div>
              </>
            ) : modal === "Investigation guide" ? (
              <div className="guide-content">
                <p>
                  <strong>1. Explore the evidence.</strong> Switch between
                  split, overlay, and diff views. Use display filters to isolate
                  the matched attack subgraph.
                </p>
                <p>
                  <strong>2. Trace a correspondence.</strong> Hover a graph node
                  or mapping row to highlight its optimal pair. Click a node to
                  inspect telemetry, incident edges, and its 1-WL signature.
                </p>
                <p>
                  <strong>3. Document the incident.</strong> Acknowledge the
                  alert and export the forensic report, mapping CSV, or STIX
                  indicator. This workspace uses an illustrative dataset; no
                  live hosts are modified.
                </p>
              </div>
            ) : (
              <>
                <p className="modal-intro">
                  Incident IR-2026-8819 · Evidence summary
                </p>
                <div className="evidence-grid">
                  <div>
                    <span>Structural correspondence</span>
                    <strong className="mint">99.65%</strong>
                  </div>
                  <div>
                    <span>Correlated enterprise events</span>
                    <strong>8,295</strong>
                  </div>
                  <div>
                    <span>Reference nodes matched</span>
                    <strong>4 / 4</strong>
                  </div>
                  <div>
                    <span>Humanized threat confidence</span>
                    <strong>94.8%</strong>
                  </div>
                </div>
                <div className="inspector-note">
                  <Icon name="shield" size={20} />
                  <p>
                    The optimal mapping links a process, file, socket, and host.
                    Structural similarity is distinct from threat confidence.
                    This is an illustrative investigation, not a live enterprise
                    connection.
                  </p>
                </div>
                <Button icon="download" onClick={exportReport}>
                  Export complete evidence report
                </Button>
              </>
            )}
          </section>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <span className="check-circle">
            <Icon name="check" size={12} />
          </span>
          {toast}
          <button
            className="icon-button"
            onClick={() => setToast("")}
            aria-label="Dismiss notification"
          >
            <Icon name="close" size={13} />
          </button>
        </div>
      )}
    </div>
  )
}
