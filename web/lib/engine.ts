"use client";

import { useEffect, useState } from "react";

export type EngineState = "ready" | "starting" | "offline";

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, { cache: "no-store", ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "The analysis engine could not complete the request.");
  }
  return response.json() as Promise<T>;
}

export function useEngineStatus(): EngineState {
  const [state, setState] = useState<EngineState>("starting");
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function check() {
      const status = await api<{ status: EngineState }>("health", {
        signal: AbortSignal.timeout(2500),
      }).then((health) => health.status, () => "offline" as const);
      if (active) {
        setState(status);
        timer = setTimeout(check, 2500);
      }
    }
    void check();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, []);
  return state;
}
