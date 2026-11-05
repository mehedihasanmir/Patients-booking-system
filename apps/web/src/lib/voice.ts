"use client";

import { create } from "zustand";

type VoiceState = {
  level: number;
  callerLevel: number;
  active: boolean;
  setLevel: (level: number) => void;
  setCallerLevel: (level: number) => void;
  setActive: (active: boolean) => void;
};

export const useVoice = create<VoiceState>((set) => ({
  level: 0,
  callerLevel: 0,
  active: false,
  setLevel: (level) => set({ level }),
  setCallerLevel: (level) => set({ callerLevel: level }),
  setActive: (active) => set({ active }),
}));
