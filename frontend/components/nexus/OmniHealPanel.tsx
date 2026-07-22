"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { DiffEditor } from "@monaco-editor/react";

/* -------------------------------------------------------------------------- */
/*  OmniHealPanel — "AI Auto-Fixer" visual module                             */
/*                                                                            */
/*  Reuses the same Monaco DiffEditor pattern as app/result/page.tsx (dark    */
/*  theme, readOnly, side-by-side, no minimap) so the diff here reads exactly */
/*  like the one judges already saw on the Result Dashboard — same visual     */
/*  grammar, new context. Everything else (trace graph, terminal, Slack       */
/*  card) is new chrome built to match that page's glassmorphic language.     */
/* -------------------------------------------------------------------------- */

export interface TraceSpanNode {
  name: string;
  durationMs: number;
  status: "ok" | "error";
}

export interface OmniHealData {
  cweId: string;
  errorSpanName: string;
  traceSpans: TraceSpanNode[];
  thinkingLines: string[];
  originalCode: string;
  fixedCode: string;
  language: string;
  slackChannel: string;
  slackMessage: string;
  prUrl: string;
  prLabel: string;
}

const DEFAULT_DATA: OmniHealData = {
  cweId: "CWE-89",
  errorSpanName: "fixer_agent",
  traceSpans: [
    { name: "scanner_agent", durationMs: 420, status: "ok" },
    { name: "fixer_agent", durationMs: 180, status: "error" },
    { name: "validator_agent", durationMs: 310, status: "ok" },
  ],
  thinkingLines: [
    "> analyzing scanner findings for CWE-89 (SQL Injection)…",
    "> tracing tainted input: request.args['id'] -> raw query string",
    "> drafting parameterized-query patch…",
    "> cross-checking patch against validator's adversarial rubric…",
    "> patch clears eval_score threshold (92/100) — converged.",
  ],
  originalCode:
    'def get_user(user_id):\n    query = "SELECT * FROM users WHERE id = " + user_id\n    return db.execute(query)\n',
  fixedCode:
    'def get_user(user_id):\n    query = "SELECT * FROM users WHERE id = %s"\n    return db.execute(query, (user_id,))\n',
  language: "python",
  slackChannel: "#devguard-alerts",
  slackMessage:
    "Omni-Heal patched a critical SQLi (CWE-89) in `get_user()` — validator score 92/100, converged in 1 attempt.",
  prUrl: "#",
  prLabel: "View GitHub PR #142",
};

/* ---- Typewriter — reveals console lines one character at a time --------- */

function useTypewriter(lines: string[], speedMs = 18, lineGapMs = 260) {
  const [renderedLines, setRenderedLines] = useState<string[]>([]);
  const [cursorOn, setCursorOn] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let li = 0;
    let ci = 0;
    const acc: string[] = [];

    function tick() {
      if (cancelled || li >= lines.length) return;
      const line = lines[li];
      ci += 1;
      const next = [...acc];
      next[li] = line.slice(0, ci);
      setRenderedLines(next);
      if (ci >= line.length) {
        acc[li] = line;
        li += 1;
        ci = 0;
        setTimeout(tick, lineGapMs);
      } else {
        setTimeout(tick, speedMs);
      }
    }
    tick();

    const blink = setInterval(() => setCursorOn((c) => !c), 500);
    return () => {
      cancelled = true;
      clearInterval(blink);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lines.join("|")]);

  return { renderedLines, cursorOn };
}

/* ---- Trace graph — mini waterfall with a pulsing red error span --------- */

function TraceGraph({ spans, errorSpanName }: { spans: TraceSpanNode[]; errorSpanName: string }) {
  const maxDuration = Math.max(...spans.map((s) => s.durationMs), 1);
  return (
    <div className="space-y-2">
      {spans.map((span, i) => {
        const widthPct = Math.max(8, (span.durationMs / maxDuration) * 100);
        const isError = span.name === errorSpanName || span.status === "error";
        return (
          <div key={span.name} className="flex items-center gap-3">
            <span className="w-28 flex-none truncate text-[11px] text-white/50">{span.name}</span>
            <div className="relative h-4 flex-1 overflow-visible rounded-full bg-white/5">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${widthPct}%` }}
                transition={{ duration: 0.7, delay: 0.1 * i, ease: [0.22, 1, 0.36, 1] }}
                className={`h-full rounded-full ${
                  isError ? "bg-rose-500/60" : "bg-cyan-400/50"
                }`}
              />
              {isError && (
                <motion.span
                  className="absolute -right-1 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-rose-400"
                  animate={{ scale: [1, 1.6, 1], opacity: [1, 0.4, 1] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                  style={{ left: `calc(${widthPct}% - 4px)` }}
                />
              )}
            </div>
            <span className="w-14 flex-none text-right text-[11px] tabular-nums text-white/40">
              {span.durationMs}ms
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ---- Slack message simulation ------------------------------------------- */

function SlackCard({
  channel,
  message,
  prUrl,
  prLabel,
}: {
  channel: string;
  message: string;
  prUrl: string;
  prLabel: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#1a1d29]/70 p-4">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-cyan-400 to-indigo-500 text-xs font-bold text-white">
          &#9889;
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-white/85">
            DevGuard Bot
            <span className="rounded bg-white/10 px-1 py-0.5 text-[9px] font-medium text-white/40">APP</span>
          </div>
          <div className="text-[10px] text-white/35">posted to {channel}</div>
        </div>
      </div>
      <p className="mt-3 text-[13px] leading-relaxed text-white/75">{message}</p>
      <a
        href={prUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/80 transition hover:bg-white/10"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.09 3.29 9.4 7.86 10.93.57.1.78-.25.78-.55v-2c-3.2.7-3.87-1.37-3.87-1.37-.53-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.2 1.18a11.1 11.1 0 0 1 5.82 0c2.22-1.49 3.19-1.18 3.19-1.18.63 1.59.24 2.76.12 3.05.74.8 1.19 1.83 1.19 3.09 0 4.43-2.7 5.4-5.27 5.69.42.36.78 1.08.78 2.18v3.23c0 .3.21.66.79.55A10.52 10.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z" />
        </svg>
        {prLabel}
      </a>
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

/* ---- Main panel ----------------------------------------------------------- */

export default function OmniHealPanel({ data }: { data?: Partial<OmniHealData> }) {
  const d = useMemo(() => ({ ...DEFAULT_DATA, ...data }), [data]);
  const { renderedLines, cursorOn } = useTypewriter(d.thinkingLines);
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    consoleRef.current?.scrollTo({ top: consoleRef.current.scrollHeight, behavior: "smooth" });
  }, [renderedLines]);

  return (
    <div
      className="nx-panel relative overflow-hidden rounded-2xl border border-cyan-400/25 bg-white/[0.03] p-6 backdrop-blur-xl ring-1 ring-cyan-400/20 sm:p-8"
      style={{ ["--panel-glow" as string]: "34, 211, 238" }}
    >
      <NexusPanelStyles />
      <span className="nx-corner nx-corner-tl" />
      <span className="nx-corner nx-corner-tr" />
      <span className="nx-corner nx-corner-bl" />
      <span className="nx-corner nx-corner-br" />

      <div className="flex items-center justify-between">
        <div>
          <span className="rounded-md border border-cyan-400/25 px-2 py-0.5 text-[10px] font-semibold tracking-widest text-cyan-300">
            MOD-01
          </span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Omni-Heal</h2>
          <p className="mt-1 text-xs font-medium uppercase tracking-wider text-cyan-300">
            AI Auto-Fixer &middot; live remediation
          </p>
        </div>
        <span className="rounded-full border border-rose-400/30 bg-rose-500/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-rose-300">
          {d.cweId} detected
        </span>
      </div>

      {/* Trace graph */}
      <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4">
        <div className="mb-3 text-[10px] font-medium uppercase tracking-wider text-white/40">
          Distributed trace &middot; error span highlighted
        </div>
        <TraceGraph spans={d.traceSpans} errorSpanName={d.errorSpanName} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* AI Thinking Console */}
        <div className="flex flex-col rounded-xl border border-white/10 bg-black/60 p-4">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
            <span className="ml-2 text-[10px] font-medium text-white/40">fixer_agent.log</span>
          </div>
          <div
            ref={consoleRef}
            className="h-40 overflow-y-auto font-mono text-[12px] leading-relaxed text-emerald-400"
          >
            {renderedLines.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-all">
                {line}
                {i === renderedLines.length - 1 && (
                  <span className={cursorOn ? "opacity-100" : "opacity-0"}>&#9608;</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Slack simulation */}
        <SlackCard
          channel={d.slackChannel}
          message={d.slackMessage}
          prUrl={d.prUrl}
          prLabel={d.prLabel}
        />
      </div>

      {/* Code diff */}
      <div className="mt-6 overflow-hidden rounded-xl border border-white/10">
        <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-4 py-2.5">
          <span className="text-xs font-medium text-white/70">Live patch &middot; original vs. AI-fixed</span>
          <div className="flex items-center gap-3 text-[10px] font-medium">
            <span className="flex items-center gap-1 text-rose-300">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" /> vulnerable
            </span>
            <span className="flex items-center gap-1 text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> patched
            </span>
          </div>
        </div>
        <div className="h-64">
          <DiffEditor
            original={d.originalCode}
            modified={d.fixedCode}
            language={d.language}
            theme="vs-dark"
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 13,
              scrollBeyondLastLine: false,
              glyphMargin: true,
            }}
          />
        </div>
      </div>
    </div>
  );
}
