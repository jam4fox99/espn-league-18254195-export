"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

export function ClientOnly({ children }: { readonly children: ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return <>{children}</>;
}
