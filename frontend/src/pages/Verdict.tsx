import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'
import VerdictCard from '../components/VerdictCard'

interface VerdictData {
  id: string
  case_id: string
  agent_a_summary: string
  agent_b_summary: string
  judge_reasoning: string
  verdict_text: string
  applicable_laws: string[]
  relief_awarded: string
  created_at: string
}

export default function Verdict() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [verdict, setVerdict] = useState<VerdictData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      try {
        const { data } = await api.get(`/cases/${caseId}/verdict`)
        if (!cancelled) {
          setVerdict(data)
          setLoading(false)
        }
      } catch (err: any) {
        if (cancelled) return
        // 404 = pipeline still running, keep polling
        if (err.response?.status === 404) {
          setTimeout(poll, 4000)
        } else {
          setError(err.response?.data?.detail || 'Failed to load verdict')
          setLoading(false)
        }
      }
    }

    poll()
    return () => { cancelled = true }
  }, [caseId])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-500">AI judges deliberating… this may take up to 2 minutes.</p>
      </div>
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-red-500">{error}</p>
    </div>
  )

  if (!verdict) return null

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4 flex items-center gap-4 shadow-sm">
        <button onClick={() => navigate(`/cases/${caseId}`)} className="text-gray-500 hover:text-gray-800">← Back</button>
        <h1 className="text-xl font-bold text-gray-800">Arbitration Verdict</h1>
        <span className="ml-auto text-sm text-gray-400">{new Date(verdict.created_at).toLocaleString('en-IN')}</span>
      </nav>

      <div className="max-w-4xl mx-auto py-8 px-4">
        <VerdictCard verdict={verdict} />
      </div>
    </div>
  )
}
