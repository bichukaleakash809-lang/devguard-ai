"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import CountUp from "react-countup";

/* -------------------------------------------------------------------------- */
/*  ExecutiveCommanderPanel — "Mobile SRE & Auto-Reporter" visual module      */
/*                                                                            */
/*  No Monaco here — this module's job is the executive-facing artifacts     */
/*  (a phone notification and a PDF), not a code diff, so the visual grammar  */
/*  leans on the phone-bezel mockup and a light "paper" card deliberately     */
/*  inverted against the dark theme — the one place a bright surface is       */
/*  correct, because a PDF preview that's dark-on-dark reads as broken, not   */
/*  stylish. Everything else (gauge, glass, glow) matches the other 4 panels. */
/* -------------------------------------------------------------------------- */

export interface ExecutiveCommanderData {
  healthScore: number; // 0-100
  slackChannel: string;
  slackAlertTitle: string;
  slackAlertBody: string;
  deployButtonLabel: string;
  reportTitle: string;
  reportGeneratedAt: string;
  reportSummaryLines: string[];
  reportStats: { label: string; value: string }[];
}

const DEFAULT_DATA: ExecutiveCommanderData = {
  healthScore: 97,
  slackChannel: "#sre-oncall",
  slackAlertTitle: "DevGuard God Mode — Incident Digest",
  slackAlertBody:
    "4 modules ran concurrently. 1 critical SQLi patched (converged, eval 92/100). Cost spike contained. Breaker-trip forecast averted. All fixes ready for sign-off.",
  deployButtonLabel: "Approve & Deploy All",
  reportTitle: "Executive SRE Summary",
  reportGeneratedAt: "Generated moments ago",
  reportSummaryLines: [
    "Omni-Heal patched CWE-89 (SQLi) in fixer_agent — converged in 1 reflection attempt, eval_score 92/100.",
    "FinOps Agent detected a 30-min spend spike ($4.80 vs $1.00 budget) and reduced OTel sampling to 5% while keeping error/critical spans at full fidelity.",
    "Pre-Cog Ops forecast a circuit-breaker trip in ~9 minutes and recommended scaling replicas 2 → 5 ahead of time.",
    "Truth Serum Agent rejected one low-confidence finding (0.31) before it reached the Fixer, then accepted the corrected re-scan (0.94).",
  ],
  reportStats: [
    { label: "Modules run", value: "4/4" },
    { label: "Critical fixes", value: "1" },
    { label: "Cost avoided", value: "$1,250" },
    { label: "Health score", value: "97%" },
  ],
};

/* ---- Global health gauge — semicircle speedometer -------------------------- */

function HealthGauge({ score }: { score: number }) {
  const color = score >= 80 ? "#34d399" : score >= 50 ? "#fbbf24" : "#f43f5e";
  const angleDeg = 180 - (score / 100) * 180;
  const rad = (angleDeg * Math.PI) / 180;
  const cx = 100;
  const cy = 100;
  const needleR = 66;
  const needleX = cx + needleR * Math.cos(rad);
  const needleY = cy - needleR * Math.sin(rad);

  return (
    <div className="relative mx-auto" style={{ width: 200, height: 118 }}>
      <svg width="200" height="118" viewBox="0 0 200 110">
        {/* Background track */}
        <path
          d="M20,100 A80,80 0 0,1 180,100"
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        {/* Progress arc */}
        <motion.path
          d="M20,100 A80,80 0 0,1 180,100"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: score / 100 }}
          transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
        />
        {/* Needle */}
        <motion.line
          x1={cx}
          y1={cy}
          stroke="white"
          strokeWidth={2.5}
          strokeLinecap="round"
          initial={{ x2: cx - 66, y2: cy }}
          animate={{ x2: needleX, y2: needleY }}
          transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
        />
        <circle cx={cx} cy={cy} r={5} fill="white" />
      </svg>
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="text-2xl font-bold tabular-nums text-white">
          <CountUp end={score} duration={1.4} suffix="%" />
        </span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-white/40">
          Global health
        </span>
      </div>
    </div>
  );
}

/* ---- iPhone simulator ------------------------------------------------------- */

function PhoneSimulator({
  channel,
  title,
  body,
  buttonLabel,
}: {
  channel: string;
  title: string;
  body: string;
  buttonLabel: string;
}) {
  return (
    <div className="mx-auto w-[240px]">
      {/* Bezel */}
      <div className="nx-phone-bezel relative rounded-[2.25rem] border-[6px] border-[#0b0c12] bg-[#0b0c12] p-2 shadow-2xl">
        {/* Notch */}
        <div className="absolute left-1/2 top-2 z-10 h-4 w-20 -translate-x-1/2 rounded-full bg-black" />
        {/* Screen */}
        <div className="relative overflow-hidden rounded-[1.6rem] bg-gradient-to-b from-[#1a1d29] to-[#0e0f16]">
          {/* Status bar */}
          <div className="flex items-center justify-between px-4 pb-1 pt-3 text-[9px] font-medium text-white/60">
            <span>9:41</span>
            <span>&#128246; &#128225; &#128267;</span>
          </div>

          {/* Notification card (Slack-style) */}
          <div className="px-3 pb-3 pt-2">
            <motion.div
              initial={{ opacity: 0, y: -12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="rounded-xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur"
            >
              <div className="flex items-center gap-1.5">
                <div className="flex h-5 w-5 items-center justify-center rounded-md bg-gradient-to-br from-cyan-400 to-indigo-500 text-[9px] font-bold text-white">
                  &#9889;
                </div>
                <span className="text-[9px] font-semibold text-white/80">DevGuard Bot</span>
                <span className="ml-auto text-[8px] text-white/35">{channel}</span>
              </div>
              <div className="mt-1.5 text-[10px] font-semibold text-white/90">{title}</div>
              <p className="mt-1 text-[9.5px] leading-relaxed text-white/60">{body}</p>
            </motion.div>

            {/* Deploy button */}
            <motion.button
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              transition={{ duration: 0.15 }}
              className="nx-deploy-btn relative mt-4 flex w-full items-center justify-center gap-1.5 overflow-hidden rounded-xl px-3 py-3 text-[10.5px] font-bold uppercase tracking-wider text-white"
            >
              <span className="nx-deploy-border" aria-hidden />
              <span className="relative z-10">&#9889; {buttonLabel}</span>
            </motion.button>

            <div className="mt-4 flex items-center justify-center gap-1.5 text-[8px] text-white/25">
              <span className="h-1 w-1 rounded-full bg-white/25" />
              swipe up to dismiss
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- PDF report preview ----------------------------------------------------- */

function PdfPreview({
  title,
  generatedAt,
  summaryLines,
  stats,
}: {
  title: string;
  generatedAt: string;
  summaryLines: string[];
  stats: { label: string; value: string }[];
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16, rotateX: -4 }}
      animate={{ opacity: 1, y: 0, rotateX: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="relative mx-auto w-full max-w-sm rounded-lg bg-[#f4f1ea] p-5 text-[#1c1c1c] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)]"
    >
      <span className="absolute -top-2 right-4 rounded-sm bg-rose-600 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white shadow">
        PDF
      </span>
      <div className="flex items-center justify-between border-b border-black/10 pb-2">
        <div>
          <div className="text-[13px] font-bold tracking-tight">{title}</div>
          <div className="text-[9px] text-black/45">{generatedAt}</div>
        </div>
        <div className="flex h-6 w-6 items-center justify-center rounded bg-black/80 text-[10px] font-bold text-white">
          D
        </div>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-2">
        {stats.map((s) => (
          <div key={s.label} className="rounded bg-black/[0.04] px-1.5 py-1.5 text-center">
            <div className="text-[11px] font-bold tabular-nums">{s.value}</div>
            <div className="text-[7px] uppercase tracking-wide text-black/45">{s.label}</div>
          </div>
        ))}
      </div>

      <ul className="mt-3 space-y-1.5">
        {summaryLines.map((line, i) => (
          <li key={i} className="flex gap-1.5 text-[9.5px] leading-snug text-black/70">
            <span className="mt-1 h-1 w-1 flex-none rounded-full bg-black/40" />
            {line}
          </li>
        ))}
      </ul>

      <div className="mt-3 flex items-center justify-between border-t border-black/10 pt-2 text-[8px] text-black/35">
        <span>DevGuard AI &middot; SigNoz Nexus</span>
        <span>Page 1 of 1</span>
      </div>
    </motion.div>
  );
}

/* ---- Shared HUD panel chrome (self-contained) ------------------------------- */

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
      .nx-phone-bezel {
        box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06), 0 20px 50px -12px rgba(0, 0, 0, 0.8);
      }
      .nx-deploy-btn {
        background: linear-gradient(180deg, #201626, #150e1c);
        box-shadow: 0 0 0 1px rgba(244, 63, 94, 0.35), 0 6px 24px -6px rgba(244, 63, 94, 0.5);
        animation: nx-deploy-glow 2.2s ease-in-out infinite;
      }
      @keyframes nx-deploy-glow {
        0%,
        100% {
          box-shadow: 0 0 0 1px rgba(244, 63, 94, 0.35), 0 6px 24px -6px rgba(244, 63, 94, 0.45);
        }
        50% {
          box-shadow: 0 0 0 1px rgba(244, 63, 94, 0.55), 0 8px 28px -4px rgba(244, 63, 94, 0.7);
        }
      }
      .nx-deploy-border {
        position: absolute;
        inset: -1px;
        border-radius: 0.75rem;
        padding: 1px;
        background: conic-gradient(from var(--nx-angle, 0deg), transparent 0%, #f43f5e 25%, #6366f1 50%, transparent 75%);
        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        animation: nx-rotate 3s linear infinite;
      }
      @property --nx-angle {
        syntax: "<angle>";
        initial-value: 0deg;
        inherits: false;
      }
      @keyframes nx-rotate {
        to {
          --nx-angle: 360deg;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .nx-deploy-btn,
        .nx-deploy-border {
          animation: none !important;
        }
      }
    `}</style>
  );
}

/* ---- Main panel --------------------------------------------------------------- */

export default function ExecutiveCommanderPanel({ data }: { data?: Partial<ExecutiveCommanderData> }) {
  const d = useMemo(() => ({ ...DEFAULT_DATA, ...data }), [data]);

  return (
    <div
      className="nx-panel relative overflow-hidden rounded-2xl border border-rose-400/25 bg-white/[0.03] p-6 backdrop-blur-xl ring-1 ring-rose-400/20 sm:p-8"
      style={{ ["--panel-glow" as string]: "251, 113, 133" }}
    >
      <NexusPanelStyles />
      <span className="nx-corner nx-corner-tl" />
      <span className="nx-corner nx-corner-tr" />
      <span className="nx-corner nx-corner-bl" />
      <span className="nx-corner nx-corner-br" />

      <div className="flex items-center justify-between">
        <div>
          <span className="rounded-md border border-rose-400/25 px-2 py-0.5 text-[10px] font-semibold tracking-widest text-rose-300">
            MOD-05
          </span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">
            Executive SRE Commander
          </h2>
          <p className="mt-1 text-xs font-medium uppercase tracking-wider text-rose-300">
            Mobile sync &amp; auto-reporter
          </p>
        </div>
        <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
          {d.healthScore}% healthy
        </span>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Health gauge */}
        <div className="flex flex-col items-center justify-center rounded-xl border border-white/10 bg-black/20 p-5">
          <HealthGauge score={d.healthScore} />
        </div>

        {/* iPhone simulator */}
        <div className="flex items-center justify-center rounded-xl border border-white/10 bg-black/20 p-5">
          <PhoneSimulator
            channel={d.slackChannel}
            title={d.slackAlertTitle}
            body={d.slackAlertBody}
            buttonLabel={d.deployButtonLabel}
          />
        </div>

        {/* PDF preview */}
        <div className="flex items-center justify-center rounded-xl border border-white/10 bg-black/20 p-5">
          <PdfPreview
            title={d.reportTitle}
            generatedAt={d.reportGeneratedAt}
            summaryLines={d.reportSummaryLines}
            stats={d.reportStats}
          />
        </div>
      </div>
    </div>
  );
}
