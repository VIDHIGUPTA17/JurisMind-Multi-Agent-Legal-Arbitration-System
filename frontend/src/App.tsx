import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Cases from './pages/Cases'
import CaseDetail from './pages/CaseDetail'
import ArbitrationRoom from './pages/ArbitrationRoom'
import Verdict from './pages/Verdict'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/cases"
            element={
              <ProtectedRoute>
                <Cases />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId"
            element={
              <ProtectedRoute>
                <CaseDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/arbitration"
            element={
              <ProtectedRoute>
                <ArbitrationRoom />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/verdict"
            element={
              <ProtectedRoute>
                <Verdict />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/cases" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
