import { create } from "zustand";

interface UserState {
  userId: number | null;
  setUserId: (id: number | null) => void;
}

// Development configuration
export const DEV_USER_ID = 1;

export const useUserStore = create<UserState>((set) => ({
  // Initialize with development user ID for current phase
  userId: DEV_USER_ID,
  setUserId: (id) => set({ userId: id }),
}));
