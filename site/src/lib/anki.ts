// Anki export (secondary to the built-in review): the same format as `make flashcards`.
import { lessons } from "./content";

function csvField(s: string): string {
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function ankiCsv(): string {
  const rows = lessons.flatMap((l) =>
    l.flashcards.map((c) => [c.q, c.a, `tsfm_rc lesson_${l.id} ${l.slug.slice(3)}`].map(csvField).join(",")),
  );
  return rows.join("\n") + "\n";
}

export function download(filename: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
