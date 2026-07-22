"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import CountUp from "react-countup";
import { DiffEditor } from "@monaco-editor/react";

/* -------------------------------------------------------------------------- */
/*  LLMJudgePanel — "Truth Serum Agent" (Hallucination Judge) visual module   */
/*                                                                            */
/*  The prompt diff reuses the exact Monaco DiffEditor pattern from           */
/*  app/result/page.tsx (readOnly, side-by-side, no minimap, vs-dark theme)   */
/*  so the "before/after prompt" moment carries the same visual authority as  */
/*  the code diff judges already saw on the Result Dashboard. The courtroom   */
/*  chat and trust meter are new chrome, built on the same glass + glow       */
/*  language as MetricCard.tsx.                                              */
/* -------------------------------------------------------------------------- */

export interface CourtroomMessage {
  speaker: "main_ai" | "judge_ai";
  text: string;
  verdict?: "rejected" | "flagged";
}

export interface LLMJudgeData {
  confidenceSeries: number[]; // 0-100, spikes then drops after judge intervenes
  spikeConfidence: number;
  floorConfidence: number;
  courtroom: CourtroomMessage[];
  promptBefore: string;
  promptAfter: string;
  trustScoreBefore: number; // 0-100
  trustScoreAfter: number;
  cweId: string;
}

const DEFAULT_DATA: LLMJudgeData = {
  confidenceSeries: [92, 88, 90, 61, 31, 28, 74, 89, 93, 94],
  spikeConfidence: 31,
  floorConfidence: 50,
  courtroom: [
    {
      speaker: "main_ai",
      text: "Finding: CWE-89 SQL Injection at line 42 — unsanitized input reaches a raw query string.",
    },
    {
      speaker: "judge_ai",
      text: "Objection. Line 42 contains no query construction of any kind in the supplied snippet. Confidence 0.31 — below the 0.50 floor.",
      verdict: "rejected",
    },
    {
      speaker: "main_ai",
      text: "Re-scanning with elevated RAG context (k=8)…",
    },
    {
      speaker: "judge_ai",
      text: "Revised finding accepted — CWE-89 at line 17, confidence 0.94. Proceeding to Fixer Agent.",
    },
  ],
  promptBefore:
    "You are a security scanner. Find vulnerabilities in the code below and report them.\n\n{code}",
  promptAfter:
    "You are DevGuard's Scanner Agent. Report ONLY genuine vulnerabilities you can point to a\nspecific line for. Do NOT infer patterns that aren't present in the actual code.\nIf uncertain, set confidence_score below 0.5 rather than guessing.\nCite the exact line number and reasoning chain for every finding.\n\n{code}",
  trustScoreBefore: 31,
  trustScoreAfter: 94,
  cweId: "CWE-89",
};

/* ---- Hallucination / confidence observability graph ---------------------- */

function ConfidenceGraph({ series, floor }: { series: number[]; floor: number }) {
  const width = 560;
  const height = 150;
  const stepX = width / (series.length - 1);
  const toY = (v: number) => height - (v / 100) * (height - 16) - 8;

  const points = series.map((v, i) => [i * stepX, toY(v)] as const);
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const floorY = toY(floor);

  const dipIndex = series.indexOf(Math.min(...series));
  const dipPoint = points[dipIndex];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full overflow-visible">
      <defs>
        <linearGradient id="judge-danger" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(244,63,94,0.22)" />
          <stop offset="100%" stopColor="rgba(244,63,94,0)" />
        </linearGradient>
      </defs>

      <rect x={0} y={floorY} width={width} height={height - floorY} fill="url(#judge-danger)" />
      <line x1={0} x2={width} y1={floorY} y2={floorY} stroke="rgba(251,191,36,0.5)" strokeDasharray="4 4" strokeWidth={1} />
      <text x={2} y={floorY - 6} fontSize="9" fill="rgba(251,191,36,0.8)">
        confidence floor {floor}%
      </text>

      <motion.path
        d={path}
        fill="none"
        stroke="#fbbf24"
        strokeWidth={2}
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1] }}
      />

      {dipPoint && (
        <motion.g initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1.2, duration: 0.4 }}>
          <circle cx={dipPoint[0]} cy={dipPoint[1]} r={5} fill="#fb7185" />
          <circle cx={dipPoint[0]} cy={dipPoint[1]} r={10} fill="none" stroke="#fb7185" strokeWidth={1.5} opacity={0.5} />
          <text x={dipPoint[0]} y={dipPoint[1] - 14} textAnchor="middle" fontSize="9" fontWeight={700} fill="#fda4af">
            hallucination spike
          </text>
        </motion.g>
      )}
    </svg>
  );
}

/* ---- AI courtroom live chat ------------------------------------------------ */

function CourtroomChat({ messages }: { messages: CourtroomMessage[] }) {
  return (
    <div className="space-y-2.5">
      {messages.map((m, i) => {
        const isJudge = m.speaker === "judge_ai";
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 * i, duration: 0.35, ease: "easeOut" }}
            className={`flex ${isJudge ? "justify-end" : "justify-start"}`}
          >
            <div className={`max-w-[85%] rounded-xl border px-3.5 py-2.5 ${
              isJudge
                ? "border-amber-400/30 bg-amber-500/[0.08] text-amber-100"
                : "border-white/10 bg-white/5 text-white/80"
            }`}
            >
              <div className={`mb-1 text-[10px] font-semibold uppercase tracking-wider ${isJudge ? "text-amber-300" : "text-cyan-300"}`}>
                {isJudge ? "Judge AI" : "Main AI"}
              </div>
              <p className="text-[12.5px] leading-relaxed">{m.text}</p>
              {m.verdict && (
                <span className="mt-2 inline-flex items-center gap-1 rounded-md border border-rose-400/40 bg-rose-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-300">
                  &#10060; {m.verdict}
                </span>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

/* ---- Trust score meter — sweeps red -> amber -> emerald ------------------- */

function TrustMeter({ before, after }: { before: number; after: number }) {
  const circumference = 2 * Math.PI * 42;
  const dash = (after / 100) * circumference;

  return (
    <div className="flex items-center gap-5 rounded-xl border border-white/10 bg-black/20 p-5">
      <div className="relative h-24 w-24 flex-none">
        <svg width="96" height="96" viewBox="0 0 96 96" className="-rotate-90">
          <circle cx="48" cy="48" r="42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
          <motion.circle
            cx="48"
            cy="48"
            r="42"
            fill="none"
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference, stroke: "#f43f5e" }}
            animate={{ strokeDashoffset: circumference - dash, stroke: ["#f43f5e", "#fbbf24", "#34d399"] }}
            transition={{ duration: 1.6, ease: "easeOut" }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-emerald-300">
          <CountUp end={after} duration={1.6} suffix="%" />
        </span>
      </div>
      <div>
        <div className="text-[10px] font-medium uppercase tracking-wider text-white/40">Trust score</div>
        <div className="mt-0.5 flex items-center gap-2 text-xs">
          <span className="rounded-md border border-rose-400/30 bg-rose-500/10 px-1.5 py-0.5 font-semibold text-rose-300">
            {before}% danger
          </span>
          <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
            <path d="M1 6h10M8 2l4 4-4 4" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="rounded-md border border-emerald-400/30 bg-emerald-500/10 px-1.5 py-0.5 font-semibold text-emerald-300">
            {after}% safe
          </span>
        </div>
        <p className="mt-2 text-xs text-white/45">Restored after prompt auto-correction &amp; re-scan.</p>
      </div>
    </div>
  );
}

/* ---- Shared HUD panel chrome (self-contained) ----------------------------- */

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

/* ---- Main panel ------------------------------------------------------------ */

export default function LLMJudgePanel({ data }: { data?: Partial<LLMJudgeData> }) {
  const d = useMemo(() => ({ ...DEFAULT_DATA, ...data }), [data]);

  return (
    <div
      className="nx-panel relative overflow-hidden rounded-2xl border border-amber-400/25 bg-white/[0.03] p-6 backdrop-blur-xl ring-1 ring-amber-400/20 sm:p-8"
      style={{ ["--panel-glow" as string]: "251, 191, 36" }}
    >
      <NexusPanelStyles />
      <span className="nx-corner nx-corner-tl" />
      <span className="nx-corner nx-corner-tr" />
      <span className="nx-corner nx-corner-bl" />
      <span className="nx-corner nx-corner-br" />

      <div className="flex items-center justify-between">
        <div>
          <span className="rounded-md border border-amber-400/25 px-2 py-0.5 text-[10px] font-semibold tracking-widest text-amber-300">
            MOD-04
          </span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Truth Serum Agent</h2>
          <p className="mt-1 text-xs font-medium uppercase tracking-wider text-amber-300">
            LLM hallucination judge
          </p>
        </div>
        <span className="rounded-full border border-rose-400/30 bg-rose-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-rose-300">
          {d.spikeConfidence}% confidence &middot; {d.cweId}
        </span>
      </div>

      {/* Observability graph */}
      <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4">
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-white/40">
          Scanner confidence &middot; last 10 findings
        </div>
        <ConfidenceGraph series={d.confidenceSeries} floor={d.floorConfidence} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* AI Courtroom */}
        <div className="rounded-xl border border-white/10 bg-black/20 p-4">
          <div className="mb-3 text-[10px] font-medium uppercase tracking-wider text-white/40">
            AI courtroom &middot; live cross-examination
          </div>
          <CourtroomChat messages={d.courtroom} />
        </div>

        {/* Trust meter */}
        <TrustMeter before={d.trustScoreBefore} after={d.trustScoreAfter} />
      </div>

      {/* Prompt diff */}
      <div className="mt-6 overflow-hidden rounded-xl border border-white/10">
        <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-4 py-2.5">
          <span className="text-xs font-medium text-white/70">Scanner system prompt &middot; auto-corrected to strict mode</span>
          <div className="flex items-center gap-3 text-[10px] font-medium">
            <span className="flex items-center gap-1 text-rose-300">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" /> permissive
            </span>
            <span className="flex items-center gap-1 text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> strict
            </span>
          </div>
        </div>
        <div className="h-52">
          <DiffEditor
            original={d.promptBefore}
            modified={d.promptAfter}
            language="plaintext"
            theme="vs-dark"
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 12.5,
              wordWrap: "on",
              scrollBeyondLastLine: false,
              glyphMargin: true,
            }}
          />
        </div>
      </div>
    </div>
  );
}
