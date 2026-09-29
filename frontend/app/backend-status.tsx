"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

type Status = "checking" | "online" | "offline";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let unmounted = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    getHealth(controller.signal)
      .then((health) => {
        if (unmounted) return;
        setStatus(health.status === "ok" ? "online" : "offline");
        setVersion(health.version);
      })
      .catch(() => {
        if (!unmounted) setStatus("offline");
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      unmounted = true;
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  const colour =
    status === "online" ? "bg-green-600" : status === "offline" ? "bg-red-600" : "bg-gray-400";

  return (
    <p className="flex items-center gap-2 text-sm" data-testid="backend-status">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${colour}`} aria-hidden />
      Backend: {status}
      {version ? <span className="text-gray-500">(v{version})</span> : null}
    </p>
  );
}
