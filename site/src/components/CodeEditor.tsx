// A plain textarea code editor: monospace, line numbers, Tab indents 4 spaces,
// Shift+Enter runs. Autosaved by the caller (debounced) so closing the tab loses nothing.
import { useRef, type KeyboardEvent } from "react";

export function CodeEditor({ value, onChange, onRun, label, rows }: {
  value: string; onChange: (v: string) => void; onRun?: () => void; label: string; rows?: number;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const lines = value.split("\n").length;
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const ta = e.currentTarget;
    if (e.key === "Enter" && (e.shiftKey || e.ctrlKey || e.metaKey) && onRun) {
      e.preventDefault();
      onRun();
      return;
    }
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const { selectionStart: s, selectionEnd: t } = ta;
      const next = value.slice(0, s) + "    " + value.slice(t);
      onChange(next);
      requestAnimationFrame(() => ref.current?.setSelectionRange(s + 4, s + 4));
    }
  };
  return (
    <div className="editor">
      <div className="gutter" aria-hidden="true">{Array.from({ length: lines }, (_, i) => i + 1).join("\n")}</div>
      <textarea ref={ref} className="code" value={value} aria-label={label} spellCheck={false} autoCapitalize="off" autoCorrect="off"
        rows={rows ?? Math.min(28, Math.max(3, lines))} onChange={(e) => onChange(e.target.value)} onKeyDown={onKey} />
    </div>
  );
}
