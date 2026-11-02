import { create } from 'zustand'

interface NetworkState {
  isOffline: boolean
  setIsOffline: (isOffline: boolean) => void
}

export const useNetworkStore = create<NetworkState>((set) => ({
  isOffline: typeof navigator !== 'undefined' ? !navigator.onLine : false,
  setIsOffline: (isOffline) => set({ isOffline }),
}))
