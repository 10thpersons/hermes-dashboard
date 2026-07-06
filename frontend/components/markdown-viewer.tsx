function renderMarkdown(md: string): string {
  // Escape HTML first
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Fenced code blocks (must run before inline code)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="bg-[var(--bg-primary)] rounded-lg p-4 my-3 overflow-x-auto text-xs font-mono"><code>${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded text-sm font-mono text-[var(--accent)]">$1</code>');

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-5 mb-2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-6 mb-3">$1</h1>');

  // Bold, italic
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Lists
  html = html.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');

  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote class="border-l-2 border-[var(--accent)] pl-3 my-2 text-[var(--text-secondary)]">$1</blockquote>');

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr class="border-[var(--border)] my-4" />');

  // Wrap remaining text in paragraphs
  const lines = html.split("\n");
  const result: string[] = [];
  const blockTags = /^<(h[1-3]|pre|li|blockquote|hr|table|thead|tbody|tr|th|td|ul|ol)/;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) {
      result.push("");
      continue;
    }
    if (blockTags.test(line) || line.startsWith("</")) {
      result.push(line);
    } else {
      result.push(`<p class="mb-3">${line}</p>`);
    }
  }
  return result.join("\n");
}

export function MarkdownViewer({ content }: { content: string }) {
  return (
    <div
      className="prose prose-invert max-w-none text-sm leading-relaxed"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}
