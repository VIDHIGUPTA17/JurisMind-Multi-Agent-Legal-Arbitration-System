import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import StatusBadge from '../components/StatusBadge'
import UploadDropzone from '../components/UploadDropzone'

interface Document {
  id: string
  filename: string
  processing_status: string
  uploader_id: string
  uploaded_at: string
}

interface Case {
  id: string
  title: string
  case_type: string
  status: string
  party_a_id: string
  party_b_id: string | null
}

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>()
  const { userId } = useAuth()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState<Case | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [triggeringVerdict, setTriggeringVerdict] = useState(false)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    const [{ data: c }, { data: d }] = await Promise.all([
      api.get(`/cases/${caseId}`),
      api.get(`/cases/${caseId}/documents`),
    ])
    setCaseData(c)
    setDocuments(d.documents)
  }, [caseId])

  useEffect(() => { fetchData() }, [fetchData])

  // Poll for processing status every 5s if any docs are still processing
  useEffect(() => {
    const pending = documents.some((d) => d.processing_status === 'PENDING' || d.processing_status === 'PROCESSING')
    if (!pending) return
    const t = setInterval(fetchData, 5000)
    return () => clearInterval(t)
  }, [documents, fetchData])

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      await api.post(`/cases/${caseId}/documents`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const triggerVerdict = async () => {
    setTriggeringVerdict(true)
    setError('')
    try {
      await api.post(`/cases/${caseId}/verdict`)
      navigate(`/cases/${caseId}/arbitration`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to trigger verdict')
      setTriggeringVerdict(false)
    }
  }

  if (!caseData) return <div className="min-h-screen flex items-center justify-center">Loading…</div>

  const canTriggerVerdict =
    caseData.status === 'PARTY_B_RESPONDED' || caseData.status === 'IN_ARBITRATION'
  const verdictDelivered = caseData.status === 'VERDICT_DELIVERED'

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4 flex items-center gap-4 shadow-sm">
        <button onClick={() => navigate('/cases')} className="text-gray-500 hover:text-gray-800">← Back</button>
        <h1 className="text-xl font-bold text-gray-800 flex-1">{caseData.title}</h1>
        <StatusBadge status={caseData.status} />
      </nav>

      <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-700 mb-1">Case Information</h2>
          <p className="text-sm text-gray-500">Type: {caseData.case_type} · ID: <span className="font-mono text-xs">{caseData.id}</span></p>
          {!caseData.party_b_id && (
            <p className="mt-2 text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              Waiting for Party B to join using the invite token.
            </p>
          )}
        </div>

        {/* Upload Section */}
        {!verdictDelivered && (
          <div className="bg-white rounded-xl border p-5">
            <h2 className="font-semibold text-gray-700 mb-3">Upload Document</h2>
            <UploadDropzone onDrop={handleUpload} loading={uploading} />
            {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          </div>
        )}

        {/* Documents List */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="font-semibold text-gray-700 mb-3">Documents ({documents.length})</h2>
          {documents.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">No documents uploaded yet.</p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-700">{doc.filename}</p>
                    <p className="text-xs text-gray-400">
                      {doc.uploader_id === userId ? 'Your document' : 'Opposing party'} ·{' '}
                      {new Date(doc.uploaded_at).toLocaleDateString('en-IN')}
                    </p>
                  </div>
                  <StatusBadge status={doc.processing_status} small />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Verdict Actions */}
        {verdictDelivered ? (
          <div className="flex gap-3">
            <button
              onClick={() => navigate(`/cases/${caseId}/verdict`)}
              className="flex-1 py-3 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
            >
              View Verdict
            </button>
            <button
              onClick={() => navigate(`/cases/${caseId}/arbitration`)}
              className="flex-1 py-3 bg-slate-600 text-white font-semibold rounded-xl hover:bg-slate-700 transition-colors"
            >
              View Pipeline
            </button>
          </div>
        ) : caseData.status === 'IN_ARBITRATION' ? (
          <button
            onClick={() => navigate(`/cases/${caseId}/arbitration`)}
            className="w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
          >
            Watch Live Pipeline →
          </button>
        ) : canTriggerVerdict ? (
          <button
            onClick={triggerVerdict}
            disabled={triggeringVerdict}
            className="w-full py-3 bg-red-600 text-white font-semibold rounded-xl hover:bg-red-700 transition-colors disabled:opacity-60"
          >
            {triggeringVerdict ? 'Starting pipeline…' : 'Trigger AI Verdict'}
          </button>
        ) : null}
      </div>
    </div>
  )
}
