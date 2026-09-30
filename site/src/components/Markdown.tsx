import { renderInline, renderMarkdown } from "../lib/markdown";

export function Markdown({ text, className }: { text: string; className?: string }) {
  return <div className={className ?? "prose"} dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />;
}

export function InlineMd({ text }: { text: string }) {
  return <span dangerouslySetInnerHTML={{ __html: renderInline(text) }} />;
}
