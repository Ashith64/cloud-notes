import { create } from 'zustand'

export interface User {
  id: number
  email: string
  name: string
}

interface AuthState {
  user: User | null
  checked: boolean   // true once GET /api/auth/me has resolved (either way)
  setUser: (u: User | null) => void
  setChecked: (v: boolean) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  checked: false,
  setUser: (user) => set({ user }),
  setChecked: (checked) => set({ checked }),
}))
