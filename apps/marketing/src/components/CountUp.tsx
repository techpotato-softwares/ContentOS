"use client";

import { useEffect, useRef, useState } from "react";

export function CountUp({
  value,
  label,
}: {
  value: string;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`metric-card text-center md:text-left transition-all duration-700 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"
      }`}
    >
      <p className="display text-2xl tracking-tight text-accent md:text-[1.85rem]">{value}</p>
      <p className="mt-1.5 text-xs leading-snug text-steel md:text-sm">{label}</p>
    </div>
  );
}
