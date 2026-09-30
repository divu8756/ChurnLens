// A random key per browser that scopes experiments on a shared server (the server stores
// only its hash). Kept in localStorage so the same browser sees its experiments again;
// when storage is blocked it lives for this page load only.
const KEY = "churnlens.workspace";
let memory: string | null = null;

function randomKey(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function workspaceKey(): string {
  if (memory) return memory;
  try {
    const stored = window.localStorage.getItem(KEY);
    if (stored && /^[A-Za-z0-9_-]{16,128}$/.test(stored)) return (memory = stored);
    memory = randomKey();
    window.localStorage.setItem(KEY, memory);
  } catch {
    memory ??= randomKey();
  }
  return memory;
}

export const WORKSPACE_HEADER = "X-Workspace-Key";
