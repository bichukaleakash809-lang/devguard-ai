// frontend/app/page.tsx
"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
} from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Bug,
  CheckCircle2,
  Cpu,
  Eye,
  GitBranch,
  Lock,
  Radar as RadarIcon,
  ShieldCheck,
  Sparkles,
  Terminal as TerminalIcon,
  Wifi,
  Zap,
} from "lucide-react";

// ═════════════════════════════════════════════════════════════════════════
// DevGuard AI — Landing Page
// -----------------------------------------------------------------------
// Design direction: "black-glass command deck". Every surface is treated
// as a pane of glass floating over a live, breathing system rather than a
// static marketing page — because the product's whole pitch is that it's
// ALWAYS running, ALWAYS watching. The boot sequence exists to earn that
// claim in the first 2.5 seconds: you don't read that DevGuard is always
// on, you watch it come online.
//
// Palette (intentional, not default-dark-mode):
//   --void:        #000000 → #05050a   (background wash)
//   --cyan-core:   #06b6d4             (telemetry / observability signal)
//   --emerald-ok:  #10b981             (safe / patched / blocked)
//   --indigo-deep: #4f46e5             (structural / agent-layer accent)
//   --threat-red:  #f43f5e             (active vulnerability, pre-fix)
// Type: Geist/Inter for UI copy, JetBrains Mono/Fira Code for every
// artifact that represents *machine output* (logs, code, trace ids) —
// the mono/sans split is the visual grammar that separates "DevGuard
// talking to you" from "DevGuard talking to itself".
// ═════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────────────────────────
// Static content (no lorem ipsum — real domain content, reused verbatim
// from the DevGuard architecture: Scanner → Fixer → Validator, the 5 Nexus
// agents, real CWE classes) so every section is grounded in the actual
// product rather than generic placeholder copy.
// ─────────────────────────────────────────────────────────────────────────

const BOOT_LINES: { text: string; tone: "system" | "network" | "ai" | "auth" }[] = [
  { text: "[SYSTEM] Initializing DevGuard AI kernel v2.4.1...", tone: "system" },
  { text: "[SYSTEM] Loading Pydantic schema contracts... OK", tone: "system" },
  { text: "[NETWORK] Connecting to SigNoz Mesh (self-hosted, OTLP/gRPC)...", tone: "network" },
  { text: "[NETWORK] Trace exporter attached — span_batch=512", tone: "network" },
  { text: "[AI] Booting Scanner \u2192 Fixer \u2192 Validator reflection loop...", tone: "ai" },
  { text: "[AI] 5 Nexus agents online: Omni-Heal, Pre-Cog, FinOps, Truth Serum, Exec Commander", tone: "ai" },
  { text: "[AI] Circuit breaker armed — state=CLOSED", tone: "ai" },
  { text: "[AUTH] Verifying hash-chained audit trail integrity...", tone: "auth" },
  { text: "[AUTH] Access Granted — welcome back, operator.", tone: "auth" },
];

const VULNERABLE_CODE = [
  "def get_user(user_id):",
  '    query = "SELECT * FROM users WHERE id = \'" + user_id + "\'"',
  "    cursor.execute(query)",
  "    return cursor.fetchone()",
];

const FIXED_CODE = [
  "def get_user(user_id: str) -> User | None:",
  '    query = "SELECT * FROM users WHERE id = %s"',
  "    cursor.execute(query, (user_id,))",
  "    return cursor.fetchone()",
];

type AgentAccent = "cyan" | "violet" | "emerald" | "amber" | "rose";

interface NexusAgent {
  code: string;
  name: string;
  role: string;
  accent: AgentAccent;
}

const NEXUS_AGENTS: NexusAgent[] = [
  { code: "MOD-01", name: "Omni-Heal", role: "Autonomous code remediation", accent: "cyan" },
  { code: "MOD-02", name: "FinOps Agent", role: "Autonomous cost controller", accent: "emerald" },
  { code: "MOD-03", name: "Pre-Cog Ops", role: "Future-state predictor", accent: "violet" },
  { code: "MOD-04", name: "Truth Serum", role: "LLM hallucination judge", accent: "amber" },
  { code: "MOD-05", name: "Exec Commander", role: "Incident digest & mobile sync", accent: "rose" },
];

const AGENT_ACCENTS: Record<AgentAccent, { text: string; dot: string; border: string }> = {
  cyan: { text: "text-cyan-300", dot: "bg-cyan-400", border: "border-cyan-400/25" },
  violet: { text: "text-violet-300", dot: "bg-violet-400", border: "border-violet-400/25" },
  emerald: { text: "text-emerald-300", dot: "bg-emerald-400", border: "border-emerald-400/25" },
  amber: { text: "text-amber-300", dot: "bg-amber-400", border: "border-amber-400/25" },
  rose: { text: "text-rose-300", dot: "bg-rose-400", border: "border-rose-400/25" },
};

const LOG_TEMPLATES: ((t: string, id: string) => string)[] = [
  (t, id) => `[${t}] INFO  otel-collector      span.export trace_id=${id} status=OK`,
  (t, id) => `[${t}] INFO  scanner-agent        rag.retrieve k=4 cwe_class=CWE-89`,
  (t, id) => `[${t}] WARN  circuit-breaker      half_open probe #1 -> primary model`,
  (t, id) => `[${t}] INFO  fixer-agent          patch.generated attempt=1 trace_id=${id}`,
  (t, id) => `[${t}] INFO  validator-agent      eval_score=0.94 verdict=PASS`,
  (t, id) => `[${t}] SEC   scanner-agent        CWE-89 detected severity=critical conf=0.97`,
  (t, id) => `[${t}] INFO  audit-chain          entry appended prev_hash=${id.slice(0, 8)}`,
  (t, id) => `[${t}] INFO  finops-agent         session_spend=$${(Math.random() * 4 + 1).toFixed(2)}`,
  (t, id) => `[${t}] WARN  precog-agent         oom_risk forecast=12% horizon=15m`,
  (t, id) => `[${t}] INFO  redis-cache          hit_ratio=0.${60 + Math.floor(Math.random() * 30)}`,
  (t, id) => `[${t}] INFO  truth-serum-agent    hallucination_flag=false conf_floor=0.50`,
  (t, id) => `[${t}] SEC   validator-agent      reflection retry=2/3 trace_id=${id}`,
  (t, id) => `[${t}] INFO  websocket            /ws/scan/${id.slice(0, 6)} client attached`,
  (t, id) => `[${t}] INFO  exec-commander       incident_digest.compiled modules=4/4`,
  (t, id) => `[${t}] WARN  cost-guardian        conservation_mode=true budget_pressure=high`,
];

function randHex(len: number) {
  const chars = "0123456789abcdef";
  let out = "";
  for (let i = 0; i < len; i++) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}

function timestamp() {
  const d = new Date();
  return d.toTimeString().slice(0, 8) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

// ─────────────────────────────────────────────────────────────────────────
// Small utility hooks
// ─────────────────────────────────────────────────────────────────────────

function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}

/** Typewriter over an array of lines; calls onDone once every line is fully typed. */
function useLineTypewriter(lines: string[], msPerChar = 14, lineGapMs = 90, onDone?: () => void) {
  const [rendered, setRendered] = useState<string[]>([]);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  const key = lines.join("|");

  useEffect(() => {
    let cancelled = false;
    let lineIdx = 0;
    let charIdx = 0;
    setRendered([]);

    function tick() {
      if (cancelled || lineIdx >= lines.length) {
        if (!cancelled) doneRef.current?.();
        return;
      }
      const line = lines[lineIdx];
      charIdx += 1;
      setRendered((prev) => {
        const next = [...prev];
        next[lineIdx] = line.slice(0, charIdx);
        return next;
      });
      if (charIdx >= line.length) {
        lineIdx += 1;
        charIdx = 0;
        setTimeout(tick, lineGapMs);
      } else {
        setTimeout(tick, msPerChar);
      }
    }
    const starter = setTimeout(tick, 120);
    return () => {
      cancelled = true;
      clearTimeout(starter);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return rendered;
}

/** 3D tilt + cursor-relative position, for the bento cards' parallax + conic border reveal. */
function useTilt(strength = 10) {
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const springX = useSpring(px, { stiffness: 220, damping: 22, mass: 0.4 });
  const springY = useSpring(py, { stiffness: 220, damping: 22, mass: 0.4 });

  const rotateX = useTransform(springY, [0, 1], [strength, -strength]);
  const rotateY = useTransform(springX, [0, 1], [-strength, strength]);
  const glowX = useTransform(springX, [0, 1], ["0%", "100%"]);
  const glowY = useTransform(springY, [0, 1], ["0%", "100%"]);

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = ref.current?.getBoundingClientRect();
      if (!rect) return;
      px.set((e.clientX - rect.left) / rect.width);
      py.set((e.clientY - rect.top) / rect.height);
    },
    [px, py]
  );

  const onMouseLeave = useCallback(() => {
    px.set(0.5);
    py.set(0.5);
  }, [px, py]);

  return { ref, rotateX, rotateY, glowX, glowY, onMouseMove, onMouseLeave };
}

// ═════════════════════════════════════════════════════════════════════════
// Boot sequence overlay
// ═════════════════════════════════════════════════════════════════════════

function BootSequence({ onComplete }: { onComplete: () => void }) {
  const [typedDone, setTypedDone] = useState(false);
  const [exiting, setExiting] = useState(false);
  const lineTexts = useMemo(() => BOOT_LINES.map((l) => l.text), []);
  const rendered = useLineTypewriter(lineTexts, 11, 110, () => setTypedDone(true));

  useEffect(() => {
    if (!typedDone) return;
    const t = setTimeout(() => setExiting(true), 650);
    return () => clearTimeout(t);
  }, [typedDone]);

  useEffect(() => {
    if (!exiting) return;
    const t = setTimeout(onComplete, 620);
    return () => clearTimeout(t);
  }, [exiting, onComplete]);

  const toneColor: Record<(typeof BOOT_LINES)[number]["tone"], string> = {
    system: "text-slate-400",
    network: "text-cyan-300",
    ai: "text-indigo-300",
    auth: "text-emerald-300",
  };

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black"
      initial={{ opacity: 1 }}
      animate={exiting ? { opacity: 0, scale: 1.06 } : { opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="pointer-events-none absolute inset-0 dg-scanlines opacity-[0.4]" />
      <div className="pointer-events-none absolute inset-0 dg-boot-vignette" />
      <div className="relative w-full max-w-2xl px-6">
        <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-600">
          <TerminalIcon className="h-3.5 w-3.5" />
          <span>devguard-kernel &mdash; boot console</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-5 font-mono text-[13px] leading-relaxed shadow-[0_0_80px_-20px_rgba(6,182,212,0.35)]">
          {BOOT_LINES.map((l, i) => (
            <div key={i} className={`${toneColor[l.tone]} min-h-[1.4em]`}>
              {rendered[i] ?? ""}
              {rendered[i]?.length === l.text.length ? null : (
                <span className="dg-caret" aria-hidden />
              )}
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Mouse-reactive cursor aura (hero-scoped)
// ═════════════════════════════════════════════════════════════════════════

function CursorAura() {
  const x = useMotionValue(-400);
  const y = useMotionValue(-400);
  const sx = useSpring(x, { stiffness: 140, damping: 20, mass: 0.5 });
  const sy = useSpring(y, { stiffness: 140, damping: 20, mass: 0.5 });

  const onMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      x.set(e.clientX - rect.left);
      y.set(e.clientY - rect.top);
    },
    [x, y]
  );

  return (
    <div className="pointer-events-auto absolute inset-0 overflow-hidden" onMouseMove={onMove}>
      <motion.div
        aria-hidden
        className="pointer-events-none absolute h-[520px] w-[520px] rounded-full dg-cursor-orb"
        style={{ left: sx, top: sy, translateX: "-50%", translateY: "-50%" }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute h-2 w-2 rounded-full bg-cyan-300"
        style={{
          left: sx,
          top: sy,
          translateX: "-50%",
          translateY: "-50%",
          boxShadow: "0 0 24px 6px rgba(34,211,238,0.65)",
        }}
      />
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Live telemetry header bar
// ═════════════════════════════════════════════════════════════════════════

function LiveTelemetryBar() {
  const mounted = useMounted();
  const [latency, setLatency] = useState(12);
  const [threats, setThreats] = useState(24059);
  const [spans, setSpans] = useState(184213);

  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => {
      setLatency((prev) => {
        const next = prev + (Math.random() * 4 - 2);
        return Math.min(28, Math.max(7, Math.round(next * 10) / 10));
      });
      if (Math.random() < 0.35) setThreats((p) => p + Math.floor(Math.random() * 3) + 1);
      setSpans((p) => p + Math.floor(Math.random() * 40) + 10);
    }, 1000);
    return () => clearInterval(id);
  }, [mounted]);

  return (
    <div className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.06] bg-black/50 backdrop-blur-xl">
      <div className="mx-auto flex h-11 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <div className="dg-logo-mini flex h-6 w-6 items-center justify-center rounded-md text-[11px] font-bold text-white">
            D
          </div>
          <span className="text-[13px] font-semibold tracking-tight text-white">
            DevGuard<span className="text-cyan-400">.</span>AI
          </span>
        </div>

        <div className="hidden items-center gap-6 font-mono text-[11px] text-slate-400 sm:flex">
          <span className="flex items-center gap-1.5">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            OTel Mesh Connected
          </span>
          <span>
            Global Latency: <span className="text-cyan-300">~{latency.toFixed(1)}ms</span>
          </span>
          <span>
            Threats Blocked: <span className="text-emerald-300">{threats.toLocaleString("en-US")}</span>
          </span>
          <span>
            Spans Traced: <span className="text-indigo-300">{spans.toLocaleString("en-US")}</span>
          </span>
        </div>

        <a
          href="#nexus"
          className="rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-[11px] font-semibold text-slate-200 transition-colors hover:bg-white/[0.08]"
        >
          Launch Nexus &rarr;
        </a>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Magnetic button + magnetic badge
// ═════════════════════════════════════════════════════════════════════════

function MagneticButton({
  children,
  variant = "primary",
  href = "#",
}: {
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  href?: string;
}) {
  const ref = useRef<HTMLAnchorElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 300, damping: 18 });
  const sy = useSpring(y, { stiffness: 300, damping: 18 });

  const onMove = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const relX = e.clientX - rect.left - rect.width / 2;
    const relY = e.clientY - rect.top - rect.height / 2;
    x.set(relX * 0.35);
    y.set(relY * 0.5);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  const base =
    "relative inline-flex items-center gap-2 rounded-full px-7 py-3.5 text-sm font-semibold transition-colors";
  const styles =
    variant === "primary"
      ? "dg-cta-primary text-black"
      : "border border-white/15 bg-white/[0.02] text-slate-200 hover:bg-white/[0.06]";

  return (
    <motion.a
      ref={ref}
      href={href}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ x: sx, y: sy }}
      className={`${base} ${styles}`}
    >
      {children}
    </motion.a>
  );
}

function MagneticBadge() {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 260, damping: 20 });
  const sy = useSpring(y, { stiffness: 260, damping: 20 });

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    x.set((e.clientX - rect.left - rect.width / 2) * 0.25);
    y.set((e.clientY - rect.top - rect.height / 2) * 0.35);
  };
  const onLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ x: sx, y: sy }}
      className="dg-badge inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/[0.06] px-4 py-1.5 text-[11px] font-medium text-cyan-200"
    >
      <Sparkles className="h-3.5 w-3.5" />
      SigNoz Hackathon 2026 &middot; Grand Finalist
    </motion.div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Hero
// ═════════════════════════════════════════════════════════════════════════

function HeroSection() {
  return (
    <section className="relative flex min-h-[92vh] flex-col items-center justify-center overflow-hidden px-4 pt-24 text-center sm:px-6">
      <div className="pointer-events-none absolute inset-0 dg-grid opacity-[0.3]" />
      <div className="pointer-events-none absolute -top-32 left-1/2 h-[640px] w-[920px] -translate-x-1/2 rounded-full dg-bloom" />
      <CursorAura />

      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <MagneticBadge />
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 mt-8 max-w-4xl text-4xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl"
      >
        <span className="dg-gradient-text">Autonomous AI Security</span>
        <br />
        <span className="dg-gradient-text-2">&amp; Observability Mesh</span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 mt-6 max-w-xl text-base leading-relaxed text-slate-400 sm:text-lg"
      >
        A three-agent pipeline that scans, patches, and adversarially reviews
        its own fixes &mdash; then reads its own SigNoz telemetry back out to
        change how it behaves, in the same request.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 mt-10 flex flex-col items-center gap-4 sm:flex-row"
      >
        <MagneticButton variant="primary" href="#bento">
          <Zap className="h-4 w-4" />
          Run a Live Scan
        </MagneticButton>
        <MagneticButton variant="ghost" href="#nexus">
          <RadarIcon className="h-4 w-4" />
          Enter Nexus Command Center
        </MagneticButton>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.8 }}
        className="relative z-10 mt-16 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-[11px] uppercase tracking-widest text-slate-600"
      >
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5" /> Hash-chained audit trail
        </span>
        <span className="flex items-center gap-1.5">
          <GitBranch className="h-3.5 w-3.5" /> 3-retry reflection loop
        </span>
        <span className="flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5" /> Full OTel tracing
        </span>
      </motion.div>
    </section>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Bento card shell — 3D tilt + conic border reveal
// ═════════════════════════════════════════════════════════════════════════

function TiltCard({
  className = "",
  glowRgb,
  children,
}: {
  className?: string;
  glowRgb: string;
  children: React.ReactNode;
}) {
  const { ref, rotateX, rotateY, glowX, glowY, onMouseMove, onMouseLeave } = useTilt(6);

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      style={{ rotateX, rotateY, transformPerspective: 1000 }}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className={`dg-bento-card group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025] p-5 backdrop-blur-xl sm:p-6 ${className}`}
    >
      <motion.div
        aria-hidden
        className="dg-card-conic pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background: useTransform([glowX, glowY], ([gx, gy]: [string, string]) =>
            `radial-gradient(500px circle at ${gx} ${gy}, rgba(${glowRgb}, 0.12), transparent 60%)`
          ),
        }}
      />
      <div className="relative z-10 flex h-full flex-col">{children}</div>
    </motion.div>
  );
}

function CardEyebrow({
  code,
  title,
  icon: Icon,
  accent,
}: {
  code: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2.5">
      <div className={`flex h-7 w-7 items-center justify-center rounded-lg border ${accent} bg-white/[0.03]`}>
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="leading-tight">
        <p className="text-[10px] uppercase tracking-widest text-slate-500">{code}</p>
        <p className="text-sm font-semibold text-white">{title}</p>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Card 1 — Mega: Omni-Heal code auto-fixer
// ═════════════════════════════════════════════════════════════════════════

function CodeAutoFixerCard() {
  const [phase, setPhase] = useState<"typing-vuln" | "healing" | "typing-fixed" | "hold">("typing-vuln");
  const vulnLines = useMemo(() => VULNERABLE_CODE, []);
  const fixedLines = useMemo(() => FIXED_CODE, []);

  const vulnRendered = useLineTypewriter(
    phase === "typing-vuln" ? vulnLines : [],
    16,
    140,
    () => setTimeout(() => setPhase("healing"), 500)
  );
  const fixedRendered = useLineTypewriter(
    phase === "typing-fixed" ? fixedLines : [],
    14,
    120,
    () => setTimeout(() => setPhase("hold"), 3200)
  );

  useEffect(() => {
    if (phase !== "healing") return;
    const t = setTimeout(() => setPhase("typing-fixed"), 1900);
    return () => clearTimeout(t);
  }, [phase]);

  useEffect(() => {
    if (phase !== "hold") return;
    const t = setTimeout(() => setPhase("typing-vuln"), 1400);
    return () => clearTimeout(t);
  }, [phase]);

  const showFixed = phase === "typing-fixed" || phase === "hold";
  const displayLines = showFixed ? fixedRendered : vulnRendered;
  const sourceLines = showFixed ? fixedLines : vulnLines;

  return (
    <TiltCard className="sm:col-span-2 lg:col-span-2 lg:row-span-2" glowRgb="34,211,238">
      <CardEyebrow
        code="MOD-01 &middot; MEGA"
        title="Omni-Heal — Autonomous Code Remediation"
        icon={Cpu}
        accent="border-cyan-400/25 text-cyan-300"
      />

      <div className="relative flex-1 overflow-hidden rounded-xl border border-white/10 bg-black/40">
        <div className="flex items-center gap-1.5 border-b border-white/10 bg-white/[0.02] px-3 py-2">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
          <span className="ml-2 font-mono text-[10px] text-slate-500">users_repository.py</span>
          <span
            className={`ml-auto flex items-center gap-1 rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
              showFixed ? "border-emerald-400/30 text-emerald-300" : "border-rose-400/30 text-rose-300"
            }`}
          >
            {showFixed ? <CheckCircle2 className="h-2.5 w-2.5" /> : <Bug className="h-2.5 w-2.5" />}
            {showFixed ? "CWE-89 Patched" : "CWE-89 SQL Injection"}
          </span>
        </div>

        <div className="min-h-[168px] px-4 py-4 font-mono text-[12.5px] leading-[1.9]">
          {sourceLines.map((line, i) => (
            <div key={i} className="flex gap-3">
              <span className="w-5 flex-none select-none text-right text-slate-700">{i + 1}</span>
              <span className={showFixed ? "text-emerald-200" : "text-slate-300"}>
                {displayLines[i] ?? ""}
                {(phase === "typing-vuln" || phase === "typing-fixed") &&
                (displayLines[i]?.length ?? 0) < line.length &&
                (displayLines[i]?.length ?? 0) > 0 ? (
                  <span className="dg-caret" aria-hidden />
                ) : null}
              </span>
            </div>
          ))}
        </div>

        <AnimatePresence>
          {phase === "healing" && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="absolute inset-x-3 bottom-3 flex items-center gap-3 rounded-lg border border-cyan-400/30 bg-black/80 px-3 py-2.5 backdrop-blur-md"
            >
              <span className="dg-spinner h-3.5 w-3.5 flex-none" />
              <div className="leading-tight">
                <p className="text-[11px] font-semibold text-cyan-200">Omni-Heal Agent engaged</p>
                <p className="font-mono text-[10px] text-slate-400">
                  parameterizing query &middot; reflection attempt 1/3
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[10.5px] text-slate-500">
        <span>
          eval_score: <span className="text-emerald-300">{showFixed ? "0.94" : "\u2014"}</span>
        </span>
        <span>
          retries: <span className="text-cyan-300">{showFixed ? "1/3" : "0/3"}</span>
        </span>
        <span>
          verdict:{" "}
          <span className={showFixed ? "text-emerald-300" : "text-slate-600"}>
            {showFixed ? "PASS" : "pending"}
          </span>
        </span>
      </div>
    </TiltCard>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Card 2 — Wide: SigNoz observability live chart
// ═════════════════════════════════════════════════════════════════════════

function ObservabilityChartCard() {
  const mounted = useMounted();
  const [points, setPoints] = useState<number[]>(() => Array.from({ length: 28 }, () => 40));
  const [bars, setBars] = useState<number[]>(() => Array.from({ length: 14 }, () => 30));
  const [p50, setP50] = useState(38);
  const [p95, setP95] = useState(96);
  const [p99, setP99] = useState(142);

  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => {
      setPoints((prev) => {
        const last = prev[prev.length - 1];
        const next = Math.min(95, Math.max(10, last + (Math.random() * 24 - 12)));
        return [...prev.slice(1), next];
      });
      setBars((prev) => {
        const next = Math.min(100, Math.max(15, prev[prev.length - 1] + (Math.random() * 30 - 15)));
        return [...prev.slice(1), next];
      });
      setP50((p) => Math.max(20, Math.round(p + (Math.random() * 6 - 3))));
      setP95((p) => Math.max(60, Math.round(p + (Math.random() * 10 - 5))));
      setP99((p) => Math.max(100, Math.round(p + (Math.random() * 16 - 8))));
    }, 900);
    return () => clearInterval(id);
  }, [mounted]);

  const path = useMemo(() => {
    const w = 100;
    const h = 100;
    const step = w / (points.length - 1);
    return points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${(i * step).toFixed(2)} ${(h - p).toFixed(2)}`)
      .join(" ");
  }, [points]);

  const areaPath = `${path} L 100 100 L 0 100 Z`;

  return (
    <TiltCard className="sm:col-span-2 lg:col-span-2" glowRgb="99,102,241">
      <div className="flex items-start justify-between">
        <CardEyebrow
          code="SIGNOZ"
          title="Distributed Trace Latency"
          icon={Activity}
          accent="border-indigo-400/25 text-indigo-300"
        />
        <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/25 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 dg-ping" />
          live
        </span>
      </div>

      <div className="relative h-32 w-full overflow-hidden rounded-lg border border-white/10 bg-black/30 sm:h-36">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full">
          <defs>
            <linearGradient id="dg-area-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(99,102,241,0.45)" />
              <stop offset="100%" stopColor="rgba(99,102,241,0)" />
            </linearGradient>
          </defs>
          {[20, 40, 60, 80].map((y) => (
            <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
          ))}
          <path d={areaPath} fill="url(#dg-area-fill)" />
          <path d={path} fill="none" stroke="#818cf8" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
          <path d={path} fill="none" stroke="#22d3ee" strokeWidth="0.6" opacity="0.7" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>

      <div className="mt-3 flex h-10 items-end gap-[3px]">
        {bars.map((b, i) => (
          <div
            key={i}
            className="dg-bar-transition flex-1 rounded-t bg-gradient-to-t from-indigo-500/70 to-cyan-400/70"
            style={{ height: `${b}%` }}
          />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 font-mono text-[11px]">
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2 text-center">
          <p className="text-slate-500">p50</p>
          <p className="text-white">{p50}ms</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2 text-center">
          <p className="text-slate-500">p95</p>
          <p className="text-cyan-300">{p95}ms</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2 text-center">
          <p className="text-slate-500">p99</p>
          <p className="text-indigo-300">{p99}ms</p>
        </div>
      </div>
    </TiltCard>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Card 3 — Tall: Nexus Commander agent radar
// ═════════════════════════════════════════════════════════════════════════

function NexusCommanderCard() {
  const mounted = useMounted();
  const [activeMap, setActiveMap] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(NEXUS_AGENTS.map((a) => [a.code, false]))
  );

  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => {
      const target = NEXUS_AGENTS[Math.floor(Math.random() * NEXUS_AGENTS.length)];
      setActiveMap((prev) => ({ ...prev, [target.code]: !prev[target.code] }));
    }, 1400);
    return () => clearInterval(id);
  }, [mounted]);

  return (
    <TiltCard className="sm:col-span-1 lg:row-span-2" glowRgb="167,139,250">
      <CardEyebrow code="NEXUS" title="Command Center" icon={RadarIcon} accent="border-violet-400/25 text-violet-300" />

      <div className="relative mx-auto mb-5 h-28 w-28 flex-none">
        <div className="dg-radar-sweep absolute inset-0 rounded-full" />
        <div className="absolute inset-0 rounded-full border border-violet-400/20" />
        <div className="absolute inset-3 rounded-full border border-violet-400/15" />
        <div className="absolute inset-[26px] rounded-full border border-violet-400/10" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="h-1.5 w-1.5 rounded-full bg-violet-300" />
        </div>
      </div>

      <div className="flex-1 space-y-2.5">
        {NEXUS_AGENTS.map((agent) => {
          const a = AGENT_ACCENTS[agent.accent];
          const active = activeMap[agent.code];
          return (
            <div
              key={agent.code}
              className="flex items-center gap-2.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2"
            >
              <span className={`h-1.5 w-1.5 flex-none rounded-full ${active ? `${a.dot} dg-ping` : "bg-slate-700"}`} />
              <div className="min-w-0 flex-1 leading-tight">
                <p className="truncate text-[11.5px] font-medium text-slate-200">{agent.name}</p>
                <p className="truncate text-[9.5px] text-slate-500">{agent.role}</p>
              </div>
              <span
                className={`flex-none rounded-md border px-1.5 py-0.5 text-[8.5px] font-semibold uppercase tracking-wider ${
                  active ? `${a.border} ${a.text}` : "border-white/10 text-slate-600"
                }`}
              >
                {active ? "active" : "idle"}
              </span>
            </div>
          );
        })}
      </div>
    </TiltCard>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Card 4 — Square: Threat map
// ═════════════════════════════════════════════════════════════════════════

const THREAT_GRID_SIZE = 8;

function ThreatMapCard() {
  const mounted = useMounted();
  const total = THREAT_GRID_SIZE * THREAT_GRID_SIZE;
  const [cells, setCells] = useState<("safe" | "threat" | "blocked")[]>(() => Array(total).fill("safe"));
  const [blockedCount, setBlockedCount] = useState(0);

  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => {
      const idx = Math.floor(Math.random() * total);
      setCells((prev) => {
        const next = [...prev];
        if (next[idx] === "safe") next[idx] = "threat";
        return next;
      });
      setTimeout(() => {
        setCells((prev) => {
          const next = [...prev];
          if (next[idx] === "threat") {
            next[idx] = "blocked";
            setBlockedCount((c) => c + 1);
          }
          return next;
        });
        setTimeout(() => {
          setCells((prev) => {
            const next = [...prev];
            if (next[idx] === "blocked") next[idx] = "safe";
            return next;
          });
        }, 1600);
      }, 550);
    }, 380);
    return () => clearInterval(id);
  }, [mounted, total]);

  return (
    <TiltCard className="sm:col-span-1" glowRgb="244,63,94">
      <div className="flex items-start justify-between">
        <CardEyebrow code="THREAT MAP" title="Live Attack Surface" icon={AlertTriangle} accent="border-rose-400/25 text-rose-300" />
        <span className="font-mono text-[10px] text-emerald-300">{blockedCount} blocked</span>
      </div>

      <div
        className="grid flex-1 gap-1"
        style={{ gridTemplateColumns: `repeat(${THREAT_GRID_SIZE}, minmax(0, 1fr))` }}
      >
        {cells.map((state, i) => (
          <div
            key={i}
            className={`aspect-square rounded-[3px] transition-colors duration-300 ${
              state === "safe" ? "bg-white/[0.04]" : state === "threat" ? "dg-cell-threat bg-rose-500" : "bg-emerald-400/80"
            }`}
          />
        ))}
      </div>

      <p className="mt-3 font-mono text-[10px] text-slate-500">simulating SQLi / DDoS probes across edge nodes</p>
    </TiltCard>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Card 5 — Square: Live CLI logs
// ═════════════════════════════════════════════════════════════════════════

function LiveLogsCard() {
  const mounted = useMounted();
  const [lines, setLines] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => {
      const template = LOG_TEMPLATES[Math.floor(Math.random() * LOG_TEMPLATES.length)];
      const line = template(timestamp(), randHex(16));
      setLines((prev) => [...prev.slice(-38), line]);
    }, 340);
    return () => clearInterval(id);
  }, [mounted]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lines]);

  const tone = (line: string) => {
    if (line.includes("SEC")) return "text-rose-300";
    if (line.includes("WARN")) return "text-amber-300";
    if (line.includes("INFO")) return "text-slate-400";
    return "text-slate-500";
  };

  return (
    <TiltCard className="sm:col-span-1" glowRgb="16,185,129">
      <CardEyebrow code="CLI" title="Live SRE / Security Logs" icon={Eye} accent="border-emerald-400/25 text-emerald-300" />

      <div
        ref={scrollRef}
        className="dg-log-scroll relative flex-1 overflow-y-auto rounded-lg border border-white/10 bg-black/50 p-2.5 font-mono text-[9.5px] leading-[1.6]"
      >
        {lines.length === 0 && <p className="text-slate-600">&gt; connecting to log stream&hellip;</p>}
        {lines.map((l, i) => (
          <div key={i} className={`whitespace-nowrap ${tone(l)}`}>
            {l}
          </div>
        ))}
        <div className="dg-caret inline-block h-3 w-1.5 align-middle" aria-hidden />
      </div>
    </TiltCard>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Bento section
// ═════════════════════════════════════════════════════════════════════════

function BentoSection() {
  return (
    <section id="bento" className="relative mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="mb-12 text-center">
        <p className="text-[11px] uppercase tracking-[0.25em] text-cyan-400">the mesh, live</p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Five systems. One <span className="dg-gradient-text">self-observing</span> pipeline.
        </h2>
      </div>

      <div id="nexus" className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <CodeAutoFixerCard />
        <NexusCommanderCard />
        <ObservabilityChartCard />
        <ThreatMapCard />
        <LiveLogsCard />
      </div>
    </section>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Footer
// ═════════════════════════════════════════════════════════════════════════

function Footer() {
  return (
    <footer className="relative border-t border-white/[0.06] px-4 py-10 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-[11px] text-slate-600 sm:flex-row">
        <span>DevGuard AI &middot; Scanner &rarr; Fixer &rarr; Validator &middot; built on SigNoz</span>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <Lock className="h-3 w-3" /> Hash-chained audit
          </span>
          <span className="flex items-center gap-1.5">
            <Wifi className="h-3 w-3" /> OTel everywhere
          </span>
        </div>
      </div>
    </footer>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Page
// ═════════════════════════════════════════════════════════════════════════

export default function LandingPage() {
  const [booted, setBooted] = useState(false);

  return (
    <>
      <GlobalStyles />
      <AnimatePresence>{!booted && <BootSequence onComplete={() => setBooted(true)} />}</AnimatePresence>

      <main className="relative min-h-screen w-full bg-[#05050a] text-slate-200 antialiased">
        <div className="pointer-events-none fixed inset-0 dg-grid opacity-[0.15]" />
        <div className="pointer-events-none fixed inset-0 dg-scanlines opacity-[0.25]" />

        <LiveTelemetryBar />

        <motion.div
          initial={{ opacity: 0 }}
          animate={booted ? { opacity: 1 } : { opacity: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: booted ? 0.05 : 0 }}
        >
          <HeroSection />
          <BentoSection />
          <Footer />
        </motion.div>
      </main>
    </>
  );
}

// ═════════════════════════════════════════════════════════════════════════
// Global styles — everything Tailwind can't express natively: scanlines,
// mesh gradients, conic reveal borders, radar sweep, custom keyframes.
// ═════════════════════════════════════════════════════════════════════════

function GlobalStyles() {
  return (
    <style jsx global>{`
      :root {
        --dg-cyan: #06b6d4;
        --dg-emerald: #10b981;
        --dg-indigo: #4f46e5;
        --dg-threat: #f43f5e;
      }

      html {
        background: #000;
      }

      .dg-grid {
        background-image: linear-gradient(to right, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
        background-size: 42px 42px;
        mask-image: radial-gradient(ellipse 85% 60% at 50% 0%, #000 40%, transparent 100%);
      }

      .dg-bloom {
        background: radial-gradient(ellipse at center, rgba(79, 70, 229, 0.22), transparent 70%);
        filter: blur(40px);
      }

      .dg-boot-vignette {
        background: radial-gradient(ellipse at center, transparent 40%, rgba(0, 0, 0, 0.9) 100%);
      }

      .dg-scanlines {
        background: repeating-linear-gradient(
          to bottom,
          rgba(255, 255, 255, 0.018) 0px,
          rgba(255, 255, 255, 0.018) 1px,
          transparent 1px,
          transparent 3px
        );
      }

      .dg-logo-mini {
        background: linear-gradient(135deg, var(--dg-indigo), var(--dg-cyan));
        box-shadow: 0 0 16px -2px var(--dg-cyan);
      }

      .dg-gradient-text {
        background: linear-gradient(90deg, #ffffff 0%, #a5f3fc 45%, #22d3ee 100%);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
      }
      .dg-gradient-text-2 {
        background: linear-gradient(90deg, #c7d2fe 0%, #818cf8 50%, #4f46e5 100%);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
      }

      .dg-badge {
        box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.08), 0 0 30px -10px rgba(34, 211, 238, 0.5);
      }

      .dg-cursor-orb {
        background: radial-gradient(circle, rgba(34, 211, 238, 0.16), rgba(79, 70, 229, 0.08) 45%, transparent 72%);
        filter: blur(6px);
      }

      .dg-cta-primary {
        background: linear-gradient(90deg, #22d3ee, #4f46e5);
        box-shadow: 0 8px 30px -8px rgba(34, 211, 238, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.06);
        transition: box-shadow 0.2s ease-out, transform 0.2s ease-out;
      }
      .dg-cta-primary:hover {
        box-shadow: 0 10px 40px -6px rgba(34, 211, 238, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.1);
      }

      .dg-bento-card {
        box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 20px 60px -30px rgba(0, 0, 0, 0.9);
        transition: border-color 0.25s ease-out;
        min-height: 260px;
      }
      .dg-bento-card:hover {
        border-color: rgba(255, 255, 255, 0.18);
      }

      .dg-card-conic {
        border-radius: inherit;
        padding: 1px;
        background: conic-gradient(
          from 0deg,
          transparent 0%,
          rgba(34, 211, 238, 0.55) 18%,
          transparent 36%,
          rgba(79, 70, 229, 0.5) 55%,
          transparent 74%,
          rgba(16, 185, 129, 0.45) 92%,
          transparent 100%
        );
        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        animation: dg-rotate 4s linear infinite;
      }
      @keyframes dg-rotate {
        to {
          transform: rotate(360deg);
        }
      }

      .dg-caret {
        display: inline-block;
        width: 7px;
        height: 1em;
        margin-left: 1px;
        background: currentColor;
        vertical-align: text-bottom;
        animation: dg-blink 0.9s steps(1) infinite;
      }
      @keyframes dg-blink {
        50% {
          opacity: 0;
        }
      }

      .dg-spinner {
        display: inline-block;
        border: 2px solid rgba(34, 211, 238, 0.25);
        border-top-color: #22d3ee;
        border-radius: 9999px;
        animation: dg-spin 0.7s linear infinite;
      }
      @keyframes dg-spin {
        to {
          transform: rotate(360deg);
        }
      }

      .dg-ping {
        animation: dg-ping 1.5s ease-in-out infinite;
      }
      @keyframes dg-ping {
        0%,
        100% {
          opacity: 1;
          transform: scale(1);
        }
        50% {
          opacity: 0.45;
          transform: scale(0.7);
        }
      }

      .dg-radar-sweep {
        background: conic-gradient(from 0deg, rgba(167, 139, 250, 0.35), transparent 28%, transparent 100%);
        animation: dg-rotate 3.2s linear infinite;
      }

      .dg-cell-threat {
        animation: dg-threat-pulse 0.55s ease-in-out infinite;
      }
      @keyframes dg-threat-pulse {
        0%,
        100% {
          box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.6);
        }
        50% {
          box-shadow: 0 0 8px 2px rgba(244, 63, 94, 0.5);
        }
      }

      .dg-bar-transition {
        transition: height 0.5s cubic-bezier(0.22, 1, 0.36, 1);
      }

      .dg-log-scroll {
        max-height: 168px;
        scrollbar-width: thin;
        scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
      }
      .dg-log-scroll::-webkit-scrollbar {
        width: 5px;
      }
      .dg-log-scroll::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
      }

      @media (prefers-reduced-motion: reduce) {
        .dg-card-conic,
        .dg-caret,
        .dg-spinner,
        .dg-ping,
        .dg-radar-sweep,
        .dg-cell-threat {
          animation: none !important;
        }
      }
    `}</style>
  );
}
