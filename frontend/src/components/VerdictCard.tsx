interface VerdictData {
  verdict_text: string
  judge_reasoning: string
  applicable_laws: string[]
  agent_a_summary: string
  agent_b_summary: string
  relief_awarded: string
}

const VERDICT_COLOR: Record<string, string> = {
  'IN FAVOUR OF CLAIMANT': 'bg-green-50 border-green-400 text-green-800',
  'IN FAVOUR OF RESPONDENT': 'bg-red-50 border-red-400 text-red-800',
  'PARTIAL AWARD': 'bg-amber-50 border-amber-400 text-amber-800',
  DISMISSED: 'bg-gray-50 border-gray-400 text-gray-800',
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border p-5 mb-4">
      <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
        {title}
      </h3>
      <div className="text-sm text-gray-600 leading-relaxed">{children}</div>
    </div>
  )
}

export default function VerdictCard({ verdict }: { verdict: VerdictData }) {
  const verdictColor = VERDICT_COLOR[verdict.verdict_text] || 'bg-blue-50 border-blue-400 text-blue-800'

  let agentASummary: any = null
  let agentBSummary: any = null
  try { agentASummary = JSON.parse(verdict.agent_a_summary) } catch { agentASummary = {} }
  try { agentBSummary = JSON.parse(verdict.agent_b_summary) } catch { agentBSummary = {} }

  let reliefAwarded: any = verdict.relief_awarded
  try { reliefAwarded = JSON.parse(verdict.relief_awarded) } catch { /* plain string, use as-is */ }

  return (
    <div>
      {/* Main Verdict Banner */}
      <div className={`border-2 rounded-2xl p-6 mb-6 text-center ${verdictColor}`}>
        <p className="text-xs uppercase tracking-widest font-semibold mb-1">AI Arbitral Award</p>
        <p className="text-2xl font-bold">{verdict.verdict_text}</p>
        {reliefAwarded && typeof reliefAwarded === 'object' ? (
          <div className="mt-2 text-sm font-medium space-y-0.5">
            {reliefAwarded.amount_inr && <p>Award: ₹{reliefAwarded.amount_inr}</p>}
            {reliefAwarded.description && <p className="font-normal text-xs opacity-80">{reliefAwarded.description}</p>}
            {reliefAwarded.interest && <p className="font-normal text-xs opacity-80">Interest: {reliefAwarded.interest}</p>}
            {reliefAwarded.costs && <p className="font-normal text-xs opacity-80">{reliefAwarded.costs}</p>}
          </div>
        ) : reliefAwarded ? (
          <p className="mt-2 text-sm font-medium">{reliefAwarded}</p>
        ) : null}
      </div>

      {/* Applicable Laws */}
      {verdict.applicable_laws?.length > 0 && (
        <Section title="⚖️ Applicable Laws">
          <ul className="space-y-1">
            {verdict.applicable_laws.map((law, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-gray-400">▸</span>
                <span>{law}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* Judge's Reasoning */}
      <Section title="📋 Judge's Reasoning">
        <p className="whitespace-pre-wrap">{verdict.judge_reasoning}</p>
      </Section>

      {/* Claimant Position */}
      <Section title="🔵 Claimant's Position (Agent A)">
        {agentASummary.claims && (
          <div className="mb-2">
            <p className="font-medium text-gray-700 mb-1">Claims:</p>
            <ul className="list-disc list-inside space-y-0.5">
              {agentASummary.claims.map((c: any, i: number) => (
                <li key={i}>
                  {typeof c === 'string' ? c : c.claim}
                  {c.strength && <span className="ml-2 text-xs text-gray-400">({c.strength})</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        {agentASummary.relief_sought && (
          <p><span className="font-medium">Relief Sought:</span> {agentASummary.relief_sought}</p>
        )}
        {agentASummary.strength_assessment && (
          <p className="mt-1"><span className="font-medium">Strength:</span> {agentASummary.strength_assessment}</p>
        )}
      </Section>

      {/* Respondent Position */}
      <Section title="🔴 Respondent's Position (Agent B)">
        {agentBSummary.defences && (
          <div className="mb-2">
            <p className="font-medium text-gray-700 mb-1">Defences:</p>
            <ul className="list-disc list-inside space-y-0.5">
              {agentBSummary.defences.map((d: any, i: number) => (
                <li key={i}>
                  {typeof d === 'string' ? d : d.defence}
                  {d.strength && <span className="ml-2 text-xs text-gray-400">({d.strength})</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        {agentBSummary.strength_assessment && (
          <p><span className="font-medium">Strength:</span> {agentBSummary.strength_assessment}</p>
        )}
      </Section>
    </div>
  )
}
