import { createContext, useContext, useState, type ReactNode } from "react";

export interface TipRow { value: string; label: string; color?: string }
interface TipState { x: number; y: number; rows: TipRow[] }

const Ctx = createContext<{ show: (x: number, y: number, rows: TipRow[]) => void; hide: () => void }>({ show: () => {}, hide: () => {} });

export function TooltipProvider({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<TipState | null>(null);
  return (
    <Ctx.Provider value={{ show: (x, y, rows) => setTip({ x, y, rows }), hide: () => setTip(null) }}>
      {children}
      {tip && (
        <div className="tooltip" role="status" aria-live="polite"
          style={{ left: Math.min(tip.x + 14, window.innerWidth - 300), top: Math.min(tip.y + 10, window.innerHeight - 160) }}>
          {tip.rows.map((r, i) => (
            <div className="trow" key={i}>
              {r.color && <span className="key" style={{ background: r.color, width: 12, height: 3, display: "inline-block" }} />}
              <span className="val">{r.value}</span>
              <span className="lab">{r.label}</span>
            </div>
          ))}
        </div>
      )}
    </Ctx.Provider>
  );
}

export function useTooltip() {
  return useContext(Ctx);
}
