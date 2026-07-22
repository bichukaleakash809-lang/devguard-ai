"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";

/* -------------------------------------------------------------------------- */
/*  PreCogPanel — "Future Predictor" visual module                            */
/*                                                                            */
/*  Two custom SVG/CSS visualizations (no charting lib, so every beat can be   */
/*  choreographed): a radar graph whose projected line bends away from a red   */
/*  "crash zone" right before intercept, and a blast-radius map built from     */
/*  concentric pulse rings + trig-positioned nodes around a center service.    */
/*  Both intentionally skip Monaco/DiffEditor — this module's "proof" is the   */
/*  forecast graphics, with the fix indicators as compact after-the-fact       */
/*  confirmation strips rather than another full diff viewer.                 */
/* -------------------------------------------------------------------------- */

export interface BlastNode {
  name: string;
  distance: 1 | 2 | 3; // hops from the origin service — drives radius + color
}

export interface PreCogData {
  radarSeries: number[]; // projected metric trend approaching, then averting, the crash threshold
  crashThreshold: number;
  interceptIndex: number; // index in radarSeries where the agent intervenes
  originService: string;
  blastNodes: BlastNode[];
  replicasBefore: number;
  replicasAfter: number;
  scalingReason: string;
  memoryLeakBefore: string;
  memoryLeakAfter: string;
  etaMinutes: number;
}

const DEFAULT_DATA: PreCogData = {
  radarSeries: [12, 15, 19, 26, 35, 47, 58, 44, 33, 26, 22],
  crashThreshold: 65,
  interceptIndex: 6,
  originService: "fixer_agent",
  blastNodes: [
    { name: "fixer_agent", distance: 1 },
    { name: "validator_agent", distance: 1 },
    { name: "redis_cache", distance: 2 },
    { name: "api_gateway", distance: 2 },
    { name: "signoz_collector", distance: 3 },
    { name: "frontend_ws", distance: 3 },
  ],
  replicasBefore: 2,
  replicasAfter: 5,
  scalingReason: "projected breaker trip in ~9 min at current error-rate drift",
  memoryLeakBefore: "ws_subscribers[scan_id].append(event)  # unbounded growth",
  memoryLeakAfter: "ws_subscribers[scan_id].append(event)  # capped + TTL-evicted",
  etaMinutes: 9,
};

/* ---- Predictive radar graph ------------------------------------------------ */

function RadarGraph({ series, crashThreshold, interceptIndex }: { series: number[]; crashThreshold: number; interceptIndex: number }) {
  const width = 560;
  const height = 170;
  const max = crashThreshold * 1.15;
  const stepX = width / (series.length - 1);
  const toY = (v: number) => height - (v / max) * (height - 16) - 8;

  const points = series.map((v, i) => [i * stepX, toY(v)] as const);
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const crashY = toY(crashThreshold);
  const interceptPoint = points[interceptIndex];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full overflow-visible">
      <defs>
        <linearGradient id="precog-crash" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(244,63,94,0.28)" />
          <stop offset="100%" stopColor="rgba(244,63,94,0)" />
        </linearGradient>
      </defs>

      {/* Crash zone */}
      <rect x={0} y={0} width={width} height={crashY} fill="url(#precog-crash)" />
      <line x1={0} x2={width} y1={crashY} y2={crashY} stroke="rgba(244,63,94,0.55)" strokeDasharray="5 4" strokeWidth={1} />
      <text x={width - 2} y={crashY - 6} textAnchor="end" fontSize="9" fontWeight={700} fill="rgba(251,113,133,0.9)">
        CRASH ZONE
      </text>

      {/* Projected line — dotted up to intercept, solid (averted) after */}
      <motion.path
        d={path}
        fill="none"
        stroke="#a78bfa"
        strokeWidth={2}
        strokeDasharray="5 4"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.8, ease: [0.22, 1, 0.36, 1] }}
      />

      {interceptPoint && (
        <motion.g initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1.6, duration: 0.4 }}>
          <circle cx={interceptPoint[0]} cy={interceptPoint[1]} r={5} fill="#a78bfa" />
          <circle cx={interceptPoint[0]} cy={interceptPoint[1]} r={9} fill="none" stroke="#a78bfa" strokeWidth={1.5} opacity={0.5} />
          <text x={interceptPoint[0]} y={interceptPoint[1] - 14} textAnchor="middle" fontSize="9" fontWeight={700} fill="#c4b5fd">
            intercepted &middot; averted
          </text>
        </motion.g>
      )}
    </svg>
  );
}

/* ---- Blast radius network map ---------------------------------------------- */

function BlastRadiusMap({ origin, nodes }: { origin: string; nodes: BlastNode[] }) {
  const size = 260;
  const center = size / 2;
  const ringRadii = { 1: 55, 2: 90, 3: 122 } as const;
  const colorByDistance = {
    1: { dot: "bg-rose-400", text: "text-rose-300", stroke: "rgba(251,113,133,0.5)" },
    2: { dot: "bg-amber-400", text: "text-amber-300", stroke: "rgba(251,191,36,0.4)" },
    3: { dot: "bg-cyan-400", text: "text-cyan-300", stroke: "rgba(34,211,238,0.3)" },
  } as const;

  // Group by distance so nodes at the same ring are spread evenly around it.
  const byDistance = useMemo(() => {
    const groups: Record<number, BlastNode[]> = { 1: [], 2: [], 3: [] };
    nodes.forEach((n) => groups[n.distance].push(n));
    return groups;
  }, [nodes]);

  return (
    <div className="relative mx-auto" style={{ width: size, height: size }}>
      {/* Concentric pulse rings */}
      {[1, 2, 3].map((d) => (
        <motion.div
          key={d}
          className="absolute rounded-full border"
          style={{
            width: ringRadii[d as 1 | 2 | 3] * 2,
            height: ringRadii[d as 1 | 2 | 3] * 2,
            left: center - ringRadii[d as 1 | 2 | 3],
            top: center - ringRadii[d as 1 | 2 | 3],
            borderColor: colorByDistance[d as 1 | 2 | 3].stroke,
          }}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: [0.15, 0.4, 0.15], scale: [0.96, 1, 0.96] }}
          transition={{ duration: 2.6, repeat: Infinity, delay: d * 0.2, ease: "easeInOut" }}
        />
      ))}

      {/* Origin node */}
      <div
        className="absolute flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-rose-400/50 bg-rose-500/20 text-center text-[9px] font-semibold text-rose-200"
        style={{ left: center, top: center }}
      >
        {origin.replace("_", "\n")}
      </div>

      {/* Surrounding nodes, positioned trigonometrically around each ring */}
      {([1, 2, 3] as const).map((d) =>
        byDistance[d].map((node, i) => {
          const count = byDistance[d].length;
          const angle = (i / count) * 2 * Math.PI + d * 0.4;
          const r = ringRadii[d];
          const x = center + r * Math.cos(angle);
          const y = center + r * Math.sin(angle);
          const c = colorByDistance[d];
          return (
            <motion.div
              key={node.name}
              className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1"
              style={{ left: x, top: y }}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.15 * d + 0.08 * i, duration: 0.4 }}
            >
              <span className={`h-2.5 w-2.5 rounded-full ${c.dot}`} />
              <span className={`whitespace-nowrap text-[9px] font-medium ${c.text}`}>{node.name}</span>
            </motion.div>
          );
        })
      )}
    </div>
  );
}

/* ---- Dual fix indicator strip ----------------------------------------------- */

function ScalingFixCard({ before, after, reason }: { before: number; after: number; reason: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="text-[10px] font-medium uppercase tracking-wider text-white/40">Infra auto-scale</div>
      <div className="mt-2 flex items-center gap-3">
        <span className="rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-sm font-semibold tabular-nums text-white/60">
          replicas: {before}
        </span>
        <svg width="20" height="14" viewBox="0 0 20 14" fill="none">
          <path d="M1 7h14M11 2l6 5-6 5" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="rounded-md border border-violet-400/30 bg-violet-500/15 px-2.5 py-1 text-sm font-semibold tabular-nums text-violet-200">
          replicas: {after}
        </span>
      </div>
      <p className="mt-2 text-xs text-white/45">{reason}</p>
    </div>
  );
}

function MemoryLeakFixCard({ before, after }: { before: string; after: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="text-[10px] font-medium uppercase tracking-wider text-white/40">Memory-leak patch</div>
      <div className="mt-2 space-y-1 font-mono text-[11px] leading-relaxed">
        <div className="rounded bg-rose-500/10 px-2 py-1 text-rose-300">
          <span className="select-none text-rose-500/70">- </span>
          {before}
        </div>
        <div className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-300">
          <span className="select-none text-emerald-500/70">+ </span>
          {after}
        </div>
      </div>
    </div>
  );
}

/* ---- Shared HUD panel chrome (self-contained — no dependency on any other
   page/component's global styles, so this component drops in standalone) --- */

function NexusPanelStyles() {
  return (
    <style jsx global>{`
      .nx-panel {
        box-shadow: 0 0 0 1px rgba(var(--panel-glow), 0.06), 0 0 50px -18px rgba(var(--panel-glow), 0.35),
          0 20px 60px -24px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.05);
      }
      .nx-corner {
        position: absolute;
        width: 18px;
        height: 18px;
        border-color: rgba(var(--panel-glow), 0.55);
        pointer-events: none;
      }
      .nx-corner-tl {
        top: 10px;
        left: 10px;
        border-top: 2px solid;
        border-left: 2px solid;
        border-radius: 4px 0 0 0;
      }
      .nx-corner-tr {
        top: 10px;
        right: 10px;
        border-top: 2px solid;
        border-right: 2px solid;
        border-radius: 0 4px 0 0;
      }
      .nx-corner-bl {
        bottom: 10px;
        left: 10px;
        border-bottom: 2px solid;
        border-left: 2px solid;
        border-radius: 0 0 0 4px;
      }
      .nx-corner-br {
        bottom: 10px;
        right: 10px;
        border-bottom: 2px solid;
        border-right: 2px solid;
        border-radius: 0 0 4px 0;
      }
    `}</style>
  );
}

/* ---- Main panel ---------------------------------------------------------------- */

export default function PreCogPanel({ data }: { data?: Partial<PreCogData> }) {
  const d = useMemo(() => ({ ...DEFAULT_DATA, ...data }), [data]);

  return (
    <div
      className="nx-panel relative overflow-hidden rounded-2xl border border-violet-400/25 bg-white/[0.03] p-6 backdrop-blur-xl ring-1 ring-violet-400/20 sm:p-8"
      style={{ ["--panel-glow" as string]: "167, 139, 250" }}
    >
      <NexusPanelStyles />
      <span className="nx-corner nx-corner-tl" />
      <span className="nx-corner nx-corner-tr" />
      <span className="nx-corner nx-corner-bl" />
      <span className="nx-corner nx-corner-br" />

      <div className="flex items-center justify-between">
        <div>
          <span className="rounded-md border border-violet-400/25 px-2 py-0.5 text-[10px] font-semibold tracking-widest text-violet-300">
            MOD-03
          </span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Pre-Cog Ops</h2>
          <p className="mt-1 text-xs font-medium uppercase tracking-wider text-violet-300">
            Future-state predictor
          </p>
        </div>
        <span className="rounded-full border border-violet-400/30 bg-violet-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-violet-300">
          ETA {d.etaMinutes} min &middot; averted
        </span>
      </div>

      {/* Predictive radar graph */}
      <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4">
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-white/40">
          Error-rate forecast &middot; next 15 min
        </div>
        <RadarGraph series={d.radarSeries} crashThreshold={d.crashThreshold} interceptIndex={d.interceptIndex} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.2fr]">
        {/* Blast radius map */}
        <div className="rounded-xl border border-white/10 bg-black/20 p-4">
          <div className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/40">
            Blast radius &middot; origin: {d.originService}
          </div>
          <BlastRadiusMap origin={d.originService} nodes={d.blastNodes} />
        </div>

        {/* Dual fix indicators */}
        <div className="flex flex-col gap-4">
          <ScalingFixCard before={d.replicasBefore} after={d.replicasAfter} reason={d.scalingReason} />
          <MemoryLeakFixCard before={d.memoryLeakBefore} after={d.memoryLeakAfter} />
        </div>
      </div>
    </div>
  );
}
