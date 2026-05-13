import { createContext, useContext, useState, ReactNode } from 'react'

interface AuthState {
  token: string | null
  userId: string | null
  role: string | null
}

interface AuthContextType extends AuthState {
  login: (token: string, userId: string, role: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: localStorage.getItem('token'),
    userId: localStorage.getItem('userId'),
    role: localStorage.getItem('role'),
  })

  const login = (token: string, userId: string, role: string) => {
    localStorage.setItem('token', token)
    localStorage.setItem('userId', userId)
    localStorage.setItem('role', role)
    setState({ token, userId, role })
  }

  const logout = () => {
    localStorage.clear()
    setState({ token: null, userId: null, role: null })
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
