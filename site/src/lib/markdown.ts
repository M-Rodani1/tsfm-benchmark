import MarkdownIt from "markdown-it";

// Lesson prose is trusted repository content, but HTML is still disabled: Markdown only.
const md = new MarkdownIt({ html: false, linkify: true, typographer: false });
md.renderer.rules.link_open = (tokens, idx, options, _env, self) => {
  const href = String(tokens[idx].attrGet("href") ?? "");
  if (/^https?:/.test(href)) {
    tokens[idx].attrSet("target", "_blank");
    tokens[idx].attrSet("rel", "noopener noreferrer");
  }
  return self.renderToken(tokens, idx, options);
};

export function renderMarkdown(text: string): string {
  return md.render(text);
}

export function renderInline(text: string): string {
  return md.renderInline(text);
}
