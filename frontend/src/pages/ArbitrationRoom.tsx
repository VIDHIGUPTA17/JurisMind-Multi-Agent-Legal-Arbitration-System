import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'

// ── Types ────────────────────────────────────────────────────────────────────

interface StageInfo {
  number: number
  name: string
  label: string
  agents: string
  icon: string
  description: string
}

interface StageState {
  status: 'pending' | 'running' | 'completed' | 'failed'
  summary?: string
  duration_ms?: number
  error?: string
}

interface CaseData {
  id: string
  title: string
  status: string
  party_a_id: string
  party_b_id: string | null
}

// ── Stage metadata ────────────────────────────────────────────────────────────

const STAGES: StageInfo[] = [
  {
    number: 1,
    name: 'party_analysis',
    label: 'Party Analysis',
    agents: 'Party Agent × 2',
    icon: '👥',
    description: 'Analyzing both parties\' submissions and assessing claim strength',
  },
  {
    number: 2,
    name: 'evidence_comparison',
    label: 'Evidence Comparison',
    agents: 'Evidence Comparison Agent',
    icon: '🔍',
    description: 'Cross-examining evidence — SUPPORTED / NOT FOUND / CONTRADICTED',
  },
  {
    number: 3,
    name: 'contradiction_check',
    label: 'Contradiction & Consistency',
    agents: 'Contradiction Detection + Witness Consistency Agent',
    icon: '⚡',
    description: 'Detecting contradictions, agreed facts, and consistency scores',
  },
  {
    number: 4,
    name: 'legal_reasoning',
    label: 'Legal Reasoning',
    agents: 'Legal Argument + Liability Reasoning Agent',
    icon: '⚖️',
    description: 'Applying Indian statutes, determining liability split %',
  },
  {
    number: 5,
    name: 'resolution',
    label: 'Resolution & Compensation',
    agents: 'Compensation Calculation + Settlement Recommendation Agent',
    icon: '💰',
    description: 'Calculating award in INR and recommending settlement range',
  },
  {
    number: 6,
    name: 'quality_assurance',
    label: 'Bias & Neutrality Check',
    agents: 'Bias Conflict Agent',
    icon: '🛡️',
    description: 'Verifying neutrality score 0–1, ensuring no party favoritism',
  },
  {
    number: 7,
    name: 'final_verdict',
    label: 'Final Verdict',
    agents: 'Chief Judge Agent',
    icon: '🔨',
    description: 'Synthesizing all findings into the binding arbitral award',
  },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: StageState['status'] }) {
  if (status === 'pending') return <span className="w-3 h-3 rounded-full bg-gray-300 inline-block" />
  if (status === 'running')
    return <span className="w-3 h-3 rounded-full bg-blue-500 inline-block animate-pulse" />
  if (status === 'completed') return <span className="w-3 h-3 rounded-full bg-green-500 inline-block" />
  return <span className="w-3 h-3 rounded-full bg-red-500 inline-block" />
}

function ProgressBar({ completed, total }: { completed: number; total: number }) {
  const pct = Math.round((completed / total) * 100)
  return (
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div
        className="bg-blue-600 h-2 rounded-full transition-all duration-700"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function ArbitrationRoom() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const { token } = useAuth()

  const [caseData, setCaseData] = useState<CaseData | null>(null)
  const [stages, setStages] = useState<Record<string, StageState>>(() =>
    Object.fromEntries(STAGES.map((s) => [s.name, { status: 'pending' }]))
  )
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [verdictReady, setVerdictReady] = useState(false)
  const [claimantSummary, setClaimantSummary] = useState<any>(null)
  const [respondentSummary, setRespondentSummary] = useState<any>(null)
  const [legalIssues, setLegalIssues] = useState<string[]>([])
  const [award, setAward] = useState<string | null>(null)
  const [log, setLog] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  // Fetch case info
  useEffect(() => {
    api.get(`/cases/${caseId}`).then(({ data }) => setCaseData(data)).catch(() => {})
  }, [caseId])

  // Fetch already-completed stages (in case user refreshes mid-pipeline)
  useEffect(() => {
    api.get(`/cases/${caseId}/arbitration/stages`).then(({ data }) => {
      data.stages?.forEach((s: any) => {
        if (s.status === 'COMPLETED' || s.status === 'FAILED') {
          const meta = STAGES.find((st) => st.name === s.stage_name)
          if (!meta) return
          setStages((prev) => ({
            ...prev,
            [s.stage_name]: {
              status: s.status.toLowerCase() as StageState['status'],
              summary: s.output_summary,
              duration_ms: s.duration_ms,
              error: s.error_message,
            },
          }))
          // Extract summaries from completed stage 1
          if (s.stage_number === 1 && s.output_json) {
            try {
              const ctx = typeof s.output_json === 'string' ? JSON.parse(s.output_json) : s.output_json
              if (ctx.claimant_summary) setClaimantSummary(ctx.claimant_summary)
              if (ctx.respondent_summary) setRespondentSummary(ctx.respondent_summary)
            } catch {}
          }
          if (s.stage_number === 4 && s.output_json) {
            try {
              const ctx = typeof s.output_json === 'string' ? JSON.parse(s.output_json) : s.output_json
              setLegalIssues(ctx.legal_analysis?.legal_issues?.map((i: any) =>
                typeof i === 'string' ? i : i.issue || i.statute || JSON.stringify(i)
              ) || [])
            } catch {}
          }
        }
      })
    }).catch(() => {})
  }, [caseId])

  // SSE connection
  useEffect(() => {
    if (!token || !caseId) return
    const url = `http://localhost:8000/cases/${caseId}/arbitration/stream?token=${encodeURIComponent(token)}`
    const es = new EventSource(url)
    esRef.current = es

    const addLog = (msg: string) => {
      setLog((prev) => [...prev.slice(-49), `${new Date().toLocaleTimeString('en-IN')} — ${msg}`])
    }

    es.addEventListener('stage_started', (e) => {
      const data = JSON.parse(e.data)
      setCurrentStage(data.stage_name)
      setStages((prev) => ({
        ...prev,
        [data.stage_name]: { status: 'running' },
      }))
      addLog(`▶ Stage ${data.stage_number}: ${data.stage_name} started`)
    })

    es.addEventListener('stage_completed', (e) => {
      const data = JSON.parse(e.data)
      setStages((prev) => ({
        ...prev,
        [data.stage_name]: {
          status: 'completed',
          summary: data.summary,
          duration_ms: data.duration_ms,
        },
      }))
      addLog(`✔ Stage ${data.stage_number}: ${data.stage_name} — ${data.summary}`)

      // Fetch stage detail to get rich context
      api.get(`/cases/${caseId}/arbitration/stages/${data.stage_number}`).then(({ data: detail }) => {
        const ctx = detail.output_json
        if (!ctx) return
        if (data.stage_number === 1) {
          if (ctx.claimant_summary) setClaimantSummary(ctx.claimant_summary)
          if (ctx.respondent_summary) setRespondentSummary(ctx.respondent_summary)
        }
        if (data.stage_number === 4) {
          setLegalIssues(ctx.legal_analysis?.legal_issues?.map((i: any) =>
            typeof i === 'string' ? i : i.issue || i.statute || JSON.stringify(i)
          ) || [])
        }
        if (data.stage_number === 5) {
          const comp = ctx.compensation_breakdown
          if (comp?.total_award) setAward(`₹${Number(comp.total_award).toLocaleString('en-IN')}`)
        }
      }).catch(() => {})
    })

    es.addEventListener('stage_failed', (e) => {
      const data = JSON.parse(e.data)
      setStages((prev) => ({
        ...prev,
        [data.stage_name]: { status: 'failed', error: data.error },
      }))
      addLog(`✗ Stage ${data.stage_number} FAILED: ${data.error}`)
    })

    es.addEventListener('verdict_ready', (e) => {
      const data = JSON.parse(e.data)
      setVerdictReady(true)
      setCurrentStage(null)
      addLog(`🔨 VERDICT: ${data.verdict} (confidence: ${data.confidence})`)
      es.close()
      setTimeout(() => navigate(`/cases/${caseId}/verdict`), 2500)
    })

    es.onerror = () => {
      // SSE disconnected (pipeline not started yet or finished)
      es.close()
    }

    return () => { es.close() }
  }, [token, caseId, navigate])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  const completedCount = Object.values(stages).filter((s) => s.status === 'completed').length

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white">
      {/* Header */}
      <div className="border-b border-white/10 bg-white/5 backdrop-blur px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate(`/cases/${caseId}`)}
          className="text-white/60 hover:text-white text-sm"
        >
          ← Back
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-bold">{caseData?.title || 'Arbitration Room'}</h1>
          <p className="text-xs text-white/50">AI Multi-Agent Arbitration Pipeline — Live Session</p>
        </div>
        {verdictReady ? (
          <span className="px-3 py-1 bg-green-500 text-white text-xs font-bold rounded-full animate-pulse">
            VERDICT READY
          </span>
        ) : (
          <span className="px-3 py-1 bg-blue-500/30 border border-blue-400/40 text-blue-200 text-xs font-medium rounded-full">
            DELIBERATING…
          </span>
        )}
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Left: Claimant Panel ─────────────────────────────────────── */}
        <div className="bg-blue-900/30 border border-blue-500/30 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-3 h-3 rounded-full bg-blue-400" />
            <h2 className="font-semibold text-blue-300 text-sm uppercase tracking-wider">Claimant (Party A)</h2>
          </div>

          {claimantSummary ? (
            <div className="space-y-3">
              <div>
                <p className="text-xs text-white/40 mb-1">CLAIMS FILED</p>
                <ul className="space-y-2">
                  {(claimantSummary.claims || []).map((c: any, i: number) => (
                    <li key={i} className="text-sm bg-blue-800/40 rounded-lg px-3 py-2 border border-blue-600/20">
                      <p>{typeof c === 'string' ? c : c.claim}</p>
                      {c.strength && (
                        <span className={`text-xs mt-1 inline-block px-2 py-0.5 rounded-full ${
                          c.strength === 'STRONG' ? 'bg-green-700/40 text-green-300' :
                          c.strength === 'MODERATE' ? 'bg-yellow-700/40 text-yellow-300' :
                          'bg-red-700/40 text-red-300'
                        }`}>{c.strength}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
              {claimantSummary.relief_sought && (
                <div>
                  <p className="text-xs text-white/40 mb-1">RELIEF SOUGHT</p>
                  <p className="text-sm text-blue-200 bg-blue-800/30 rounded-lg px-3 py-2">
                    {claimantSummary.relief_sought}
                  </p>
                </div>
              )}
              {claimantSummary.overall_strength_assessment && (
                <div className="border-t border-blue-600/20 pt-3">
                  <p className="text-xs text-white/40 mb-1">CASE STRENGTH</p>
                  <p className="text-sm font-medium text-blue-300">{claimantSummary.overall_strength_assessment}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-40 gap-3 text-white/30">
              {stages.party_analysis.status === 'running' ? (
                <>
                  <div className="animate-spin w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full" />
                  <p className="text-sm">Analyzing claimant position…</p>
                </>
              ) : (
                <p className="text-sm">Awaiting party analysis…</p>
              )}
            </div>
          )}
        </div>

        {/* ── Center: Pipeline Tracker ─────────────────────────────────── */}
        <div className="space-y-4">
          {/* Progress bar */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
            <div className="flex justify-between text-xs text-white/50 mb-2">
              <span>Pipeline Progress</span>
              <span>{completedCount} / 7 stages</span>
            </div>
            <ProgressBar completed={completedCount} total={7} />
          </div>

          {/* Stage cards */}
          {STAGES.map((stage) => {
            const state = stages[stage.name] || { status: 'pending' }
            const isRunning = state.status === 'running'
            const isDone = state.status === 'completed'
            const isFailed = state.status === 'failed'

            return (
              <div
                key={stage.name}
                className={`rounded-xl border p-4 transition-all duration-500 ${
                  isRunning
                    ? 'bg-blue-600/20 border-blue-400/50 shadow-lg shadow-blue-500/10'
                    : isDone
                    ? 'bg-green-900/20 border-green-500/30'
                    : isFailed
                    ? 'bg-red-900/20 border-red-500/30'
                    : 'bg-white/3 border-white/10 opacity-60'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`text-2xl mt-0.5 ${isRunning ? 'animate-bounce' : ''}`}>
                    {isDone ? '✅' : isFailed ? '❌' : stage.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <StatusDot status={state.status} />
                      <span className="font-semibold text-sm">{stage.label}</span>
                      {state.duration_ms && (
                        <span className="text-xs text-white/30 ml-auto">
                          {(state.duration_ms / 1000).toFixed(1)}s
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-white/40 mb-1">{stage.agents}</p>

                    {isRunning && (
                      <p className="text-xs text-blue-300 italic animate-pulse">
                        {stage.description}
                      </p>
                    )}

                    {isDone && state.summary && (
                      <p className="text-xs text-green-300 mt-1 leading-relaxed">
                        {state.summary}
                      </p>
                    )}

                    {isFailed && state.error && (
                      <p className="text-xs text-red-300 mt-1">{state.error}</p>
                    )}

                    {!isRunning && !isDone && !isFailed && (
                      <p className="text-xs text-white/25">{stage.description}</p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}

          {/* Legal issues (filled after stage 4) */}
          {legalIssues.length > 0 && (
            <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-4">
              <p className="text-xs text-amber-300 font-semibold mb-2">⚖️ LEGAL ISSUES IDENTIFIED</p>
              <ul className="space-y-1">
                {legalIssues.map((issue, i) => (
                  <li key={i} className="text-xs text-amber-200">▸ {issue}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Award preview (stage 5) */}
          {award && (
            <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-xl p-4 text-center">
              <p className="text-xs text-emerald-300 font-semibold mb-1">💰 TENTATIVE AWARD</p>
              <p className="text-2xl font-bold text-emerald-300">{award}</p>
            </div>
          )}

          {/* Verdict ready banner */}
          {verdictReady && (
            <div className="bg-green-600/30 border-2 border-green-400/60 rounded-2xl p-6 text-center animate-pulse">
              <p className="text-2xl font-bold text-green-300 mb-2">🔨 Verdict Delivered!</p>
              <p className="text-sm text-green-200">Redirecting to verdict page…</p>
            </div>
          )}
        </div>

        {/* ── Right: Respondent Panel ──────────────────────────────────── */}
        <div className="bg-red-900/30 border border-red-500/30 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-3 h-3 rounded-full bg-red-400" />
            <h2 className="font-semibold text-red-300 text-sm uppercase tracking-wider">Respondent (Party B)</h2>
          </div>

          {respondentSummary ? (
            <div className="space-y-3">
              <div>
                <p className="text-xs text-white/40 mb-1">DEFENCES RAISED</p>
                <ul className="space-y-2">
                  {(respondentSummary.defences || []).map((d: any, i: number) => (
                    <li key={i} className="text-sm bg-red-800/40 rounded-lg px-3 py-2 border border-red-600/20">
                      <p>{typeof d === 'string' ? d : d.defence}</p>
                      {d.strength && (
                        <span className={`text-xs mt-1 inline-block px-2 py-0.5 rounded-full ${
                          d.strength === 'STRONG' ? 'bg-green-700/40 text-green-300' :
                          d.strength === 'MODERATE' ? 'bg-yellow-700/40 text-yellow-300' :
                          'bg-red-700/40 text-red-300'
                        }`}>{d.strength}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
              {respondentSummary.overall_strength_assessment && (
                <div className="border-t border-red-600/20 pt-3">
                  <p className="text-xs text-white/40 mb-1">CASE STRENGTH</p>
                  <p className="text-sm font-medium text-red-300">{respondentSummary.overall_strength_assessment}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-40 gap-3 text-white/30">
              {stages.party_analysis.status === 'running' ? (
                <>
                  <div className="animate-spin w-6 h-6 border-2 border-red-400 border-t-transparent rounded-full" />
                  <p className="text-sm">Analyzing respondent position…</p>
                </>
              ) : (
                <p className="text-sm">Awaiting party analysis…</p>
              )}
            </div>
          )}

          {/* Live activity log */}
          <div className="mt-6">
            <p className="text-xs text-white/30 mb-2 uppercase tracking-wider">Live Agent Log</p>
            <div
              ref={logRef}
              className="h-48 overflow-y-auto bg-black/30 rounded-lg p-3 space-y-1 font-mono"
            >
              {log.length === 0 ? (
                <p className="text-xs text-white/20">Waiting for pipeline events…</p>
              ) : (
                log.map((line, i) => (
                  <p key={i} className="text-xs text-green-300/80 leading-relaxed">{line}</p>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
