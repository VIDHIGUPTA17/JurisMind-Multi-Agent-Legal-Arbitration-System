import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import StatusBadge from '../components/StatusBadge'

interface Case {
  id: string
  title: string
  case_type: string
  status: string
  party_a_id: string
  party_b_id: string | null
  invite_token?: string
  created_at: string
}

export default function Cases() {
  const { role, logout } = useAuth()
  const navigate = useNavigate()
  const [cases, setCases] = useState<Case[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [showJoin, setShowJoin] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', case_type: 'CONTRACT', party_b_email: '' })
  const [joinForm, setJoinForm] = useState({ case_id: '', invite_token: '' })
  const [newCaseToken, setNewCaseToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchCases = async () => {
    const { data } = await api.get('/cases')
    setCases(data.cases)
  }

  useEffect(() => { fetchCases() }, [])

  const createCase = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post('/cases', form)
      setNewCaseToken(data.invite_token || '')
      await fetchCases()
      setForm({ title: '', description: '', case_type: 'CONTRACT', party_b_email: '' })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create case')
    } finally {
      setLoading(false)
    }
  }

  const joinCase = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await api.post(`/cases/${joinForm.case_id}/join`, { invite_token: joinForm.invite_token })
      await fetchCases()
      setShowJoin(false)
      setJoinForm({ case_id: '', invite_token: '' })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to join case')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm">
        <h1 className="text-xl font-bold text-gray-800">AI Legal Arbitration</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">{role}</span>
          <button onClick={logout} className="text-sm text-gray-500 hover:text-red-500">Sign out</button>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto py-8 px-4">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-semibold text-gray-800">My Cases</h2>
          <div className="flex gap-2">
            {role === 'PARTY_A' && (
              <button
                onClick={() => setShowCreate(true)}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                + New Case
              </button>
            )}
            {role === 'PARTY_B' && (
              <button
                onClick={() => setShowJoin(true)}
                className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
              >
                Join Case
              </button>
            )}
          </div>
        </div>

        {cases.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No cases yet.</p>
            {role === 'PARTY_A' && <p className="text-sm mt-1">Create a new case to get started.</p>}
            {role === 'PARTY_B' && <p className="text-sm mt-1">Use your invite token to join a case.</p>}
          </div>
        ) : (
          <div className="space-y-3">
            {cases.map((c) => (
              <div
                key={c.id}
                onClick={() => navigate(`/cases/${c.id}`)}
                className="bg-white rounded-xl border border-gray-200 p-5 cursor-pointer hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-800">{c.title}</h3>
                    <p className="text-sm text-gray-400 mt-0.5">
                      {c.case_type} · {new Date(c.created_at).toLocaleDateString('en-IN')}
                    </p>
                  </div>
                  <StatusBadge status={c.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Case Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">Create New Case</h3>
            {newCaseToken ? (
              <div>
                <p className="text-green-600 font-medium mb-2">Case created successfully!</p>
                <p className="text-sm text-gray-600 mb-3">Share this invite token with Party B:</p>
                <div className="bg-gray-100 rounded-lg p-3 font-mono text-sm break-all select-all">{newCaseToken}</div>
                <button
                  onClick={() => { setShowCreate(false); setNewCaseToken('') }}
                  className="mt-4 w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={createCase} className="space-y-3">
                <input className="input-field" placeholder="Case Title" value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })} required />
                <textarea className="input-field resize-none" rows={2} placeholder="Description (optional)"
                  value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                <select className="input-field" value={form.case_type}
                  onChange={(e) => setForm({ ...form, case_type: e.target.value })}>
                  <option value="CONTRACT">Contract Dispute</option>
                  <option value="CONSUMER">Consumer Dispute</option>
                  <option value="PROPERTY">Property Dispute</option>
                  <option value="COMPANY">Company / Corporate</option>
                </select>
                <input type="email" className="input-field" placeholder="Party B's email address"
                  value={form.party_b_email} onChange={(e) => setForm({ ...form, party_b_email: e.target.value })} required />
                {error && <p className="text-red-500 text-sm">{error}</p>}
                <div className="flex gap-2 pt-2">
                  <button type="button" onClick={() => setShowCreate(false)}
                    className="flex-1 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">Cancel</button>
                  <button type="submit" disabled={loading}
                    className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-60">
                    {loading ? 'Creating…' : 'Create Case'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Join Case Modal */}
      {showJoin && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">Join a Case</h3>
            <form onSubmit={joinCase} className="space-y-3">
              <input className="input-field" placeholder="Case ID" value={joinForm.case_id}
                onChange={(e) => setJoinForm({ ...joinForm, case_id: e.target.value })} required />
              <input className="input-field" placeholder="Invite Token" value={joinForm.invite_token}
                onChange={(e) => setJoinForm({ ...joinForm, invite_token: e.target.value })} required />
              {error && <p className="text-red-500 text-sm">{error}</p>}
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setShowJoin(false)}
                  className="flex-1 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={loading}
                  className="flex-1 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-60">
                  {loading ? 'Joining…' : 'Join'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <style>{`
        .input-field { @apply w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500; }
      `}</style>
    </div>
  )
}
