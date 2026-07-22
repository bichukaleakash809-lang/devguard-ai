"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import CountUp from "react-countup";
import { DiffEditor } from "@monaco-editor/react";

/* -------------------------------------------------------------------------- */
/*  FinOpsPanel — "Cost Controller" visual module                             */
/*                                                                            */
/*  The cost/ingestion graph is a hand-drawn SVG path (not a charting lib) so  */
/*  it can be choreographed exactly: spike -> detection marker -> drop -> flat */
/*  line, animated with a single pathLength tween. The YAML diff reuses the    */
/*  Monaco DiffEditor pattern from app/result/page.tsx so the "before/after    */
/*  config" moment reads with the same visual authority as the code diff on   */
/*  the Result Dashboard.                                                     */
/* -------------------------------------------------------------------------- */

export interface FinOpsData {
  costSeries: number[]; // relative units, spike then settle — used to draw the line
  spikeUsd: number;
  normalUsd: number;
  budgetUsd: number;
  yamlBefore: string;
  yamlAfter: string;
  moneySavedUsd: number;
  costReductionPct: number;
}

const DEFAULT_DATA: FinOpsData = {
  costSeries: [12, 14, 13, 18, 46, 88, 96, 62, 30, 18, 15, 14, 13],
  spikeUsd: 4.8,
  normalUsd: 0.42,
  budgetUsd: 1.0,
  yamlBefore:
    "processors:\n  probabilistic_sampler:\n    sampling_percentage: 100\n    # full-fidelity tracing — fine at baseline spend\n",
  yamlAfter:
    "processors:\n  probabilistic_sampler:\n    sampling_percentage: 5\n    # cost-guardian override: 30-min spend exceeded budget.\n    # error + critical-severity spans are exempted below.\n  always_sample:\n    - status: error\n    - severity: critical\n",
  moneySavedUsd: 1250,
  costReductionPct: 74,
};

/* ---- Cost / ingestion graph ------------------------------------------------ */

function CostGraph({ series, budgetUsd, spikeUsd }: { series: number[]; budgetUsd: number; spikeUsd: number }) {
  const width = 560;
  const height = 160;
  const max = Math.max(...series);
  const stepX = width / (series.length - 1);

  const points = series.map((v, i) => {
    const x = i * stepX;
    const y = height - (v / max) * (height - 20) - 10;
    return [x, y] as const;
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;

  const spikeIndex = series.indexOf(max);
  const spikePoint = points[spikeIndex];
  const budgetY = height - (budgetUsd / (spikeUsd * 1.05)) * (height - 20) - 10;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full overflow-visible">
      <defs>
        <linearGradient id="finops-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(52,211,153,0.35)" />
          <stop offset="100%" stopColor="rgba(52,211,153,0)" />
        </linearGradient>
      </defs>

      {/* Budget threshold line */}
      <line
        x1={0}
        x2={width}
        y1={budgetY}
        y2={budgetY}
        stroke="rgba(251,191,36,0.5)"
        strokeDasharray="4 4"
        strokeWidth={1}
      />
      <text x={width - 2} y={budgetY - 6} textAnchor="end" fontSize="9" fill="rgba(251,191,36,0.75)">
        budget ${budgetUsd.toFixed(2)}
      </text>

      <motion.path
        d={areaPath}
        fill="url(#finops-area)"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.4 }}
      />
      <motion.path
        d={linePath}
        fill="none"
        stroke="#34d399"
        strokeWidth={2}
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1] }}
      />

      {/* Spike marker */}
      {spikePoint && (
        <motion.circle
          cx={spikePoint[0]}
          cy={spikePoint[1]}
          r={4}
          fill="#fb7185"
          initial={{ scale: 0 }}
          animate={{ scale: [0, 1.4, 1] }}
          transition={{ delay: 1.1, duration: 0.5 }}
        />
      )}
      {spikePoint && (
        <text
          x={spikePoint[0]}
          y={spikePoint[1] - 10}
          textAnchor="middle"
          fontSize="9"
          fill="#fb7185"
          fontWeight={600}
        >
          spike detected
        </text>
      )}
    </svg>
  );
}

/* ---- ROI meter -------------------------------------------------------------- */

function RoiMeter({ moneySavedUsd, costReductionPct }: { moneySavedUsd: number; costReductionPct: number }) {
  const circumference = 2 * Math.PI * 42;
  const dash = (costReductionPct / 100) * circumference;

  return (
    <div className="nx-roi-glow flex items-center gap-5 rounded-xl border border-emerald-400/25 bg-emerald-500/[0.04] p-5">
      <div className="relative h-24 w-24 flex-none">
        <svg width="96" height="96" viewBox="0 0 96 96" className="-rotate-90">
          <circle cx="48" cy="48" r="42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
          <motion.circle
            cx="48"
            cy="48"
            r="42"
            fill="none"
            stroke="#34d399"
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - dash }}
            transition={{ duration: 1.3, ease: "easeOut" }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-emerald-300">
          <CountUp end={costReductionPct} duration={1.4} suffix="%" />
        </span>
      </div>
      <div>
        <div className="text-[10px] font-medium uppercase tracking-wider text-white/40">Money saved</div>
        <div className="text-3xl font-semibold tabular-nums tracking-tight text-white">
          <CountUp end={moneySavedUsd} duration={1.6} prefix="$" separator="," useEasing />
        </div>
        <p className="mt-1 text-xs font-medium text-emerald-300">
          via adaptive sampling &amp; cost-aware routing
        </p>
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
      .nx-roi-glow {
        box-shadow: 0 0 0 1px rgba(52, 211, 153, 0.1), 0 0 40px -12px rgba(52, 211, 153, 0.45);
      }
    `}</style>
  );
}

/* ---- Main panel -------------------------------------------------------------- */

export default function FinOpsPanel({ data }: { data?: Partial<FinOpsData> }) {
  const d = useMemo(() => ({ ...DEFAULT_DATA, ...data }), [data]);

  return (
    <div
      className="nx-panel relative overflow-hidden rounded-2xl border border-emerald-400/25 bg-white/[0.03] p-6 backdrop-blur-xl ring-1 ring-emerald-400/20 sm:p-8"
      style={{ ["--panel-glow" as string]: "52, 211, 153" }}
    >
      <NexusPanelStyles />
      <span className="nx-corner nx-corner-tl" />
      <span className="nx-corner nx-corner-tr" />
      <span className="nx-corner nx-corner-bl" />
      <span className="nx-corner nx-corner-br" />

      <div className="flex items-center justify-between">
        <div>
          <span className="rounded-md border border-emerald-400/25 px-2 py-0.5 text-[10px] font-semibold tracking-widest text-emerald-300">
            MOD-02
          </span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">FinOps Agent</h2>
          <p className="mt-1 text-xs font-medium uppercase tracking-wider text-emerald-300">
            Autonomous cost controller
          </p>
        </div>
        <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-amber-300">
          ${d.spikeUsd.toFixed(2)}/30min spike
        </span>
      </div>

      {/* Cost / ingestion graph */}
      <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4">
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-white/40">
          LLM spend &middot; last 30 minutes
        </div>
        <CostGraph series={d.costSeries} budgetUsd={d.budgetUsd} spikeUsd={d.spikeUsd} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr]">
        {/* YAML config diff */}
        <div className="overflow-hidden rounded-xl border border-white/10">
          <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-4 py-2.5">
            <span className="text-xs font-medium text-white/70">
              otel-collector-config.yaml &middot; sampling_percentage 100 &rarr; 5
            </span>
          </div>
          <div className="h-56">
            <DiffEditor
              original={d.yamlBefore}
              modified={d.yamlAfter}
              language="yaml"
              theme="vs-dark"
              options={{
                readOnly: true,
                renderSideBySide: true,
                minimap: { enabled: false },
                fontSize: 12,
                scrollBeyondLastLine: false,
                glyphMargin: true,
              }}
            />
          </div>
        </div>

        {/* ROI meter */}
        <RoiMeter moneySavedUsd={d.moneySavedUsd} costReductionPct={d.costReductionPct} />
      </div>
    </div>
  );
}
