import { Fragment, type ReactNode } from "react";

/**
 * Minimal, dependency-free Markdown renderer tuned for assistant chat replies.
 * Supports headings, ordered/unordered lists, blockquotes, fenced + inline code,
 * horizontal rules, and inline bold / italic / code / links. Anything unknown
 * falls through as a plain paragraph, so raw text always renders safely.
 */

const INLINE_PATTERN =
  /(`[^`]+`)|(\*\*[^*\n]+\*\*)|(__[^_\n]+__)|(\*[^*\n]+\*)|(_[^_\n]+_)|(\[[^\]\n]+\]\((?:https?:\/\/|\/)[^)\s]+\))/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let token = 0;
  let match: RegExpExecArray | null;

  INLINE_PATTERN.lastIndex = 0;
  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const raw = match[0];
    const key = `${keyPrefix}-i${token++}`;

    if (raw.startsWith("`")) {
      nodes.push(
        <code key={key} className="chat-inline-code">
          {raw.slice(1, -1)}
        </code>,
      );
    } else if (raw.startsWith("**") || raw.startsWith("__")) {
      nodes.push(<strong key={key}>{raw.slice(2, -2)}</strong>);
    } else if (raw.startsWith("[")) {
      const split = raw.indexOf("](");
      const label = raw.slice(1, split);
      const href = raw.slice(split + 2, -1);
      nodes.push(
        <a
          key={key}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="chat-link"
        >
          {label}
        </a>,
      );
    } else {
      nodes.push(<em key={key}>{raw.slice(1, -1)}</em>);
    }
    lastIndex = INLINE_PATTERN.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "quote"; lines: string[] }
  | { kind: "code"; text: string }
  | { kind: "hr" }
  | { kind: "p"; text: string };

function parseBlocks(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === "") {
      i += 1;
      continue;
    }

    // Fenced code block
    if (trimmed.startsWith("```")) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1; // skip closing fence (or run off the end while still streaming)
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ kind: "hr" });
      i += 1;
      continue;
    }

    // Heading
    const heading = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      i += 1;
      continue;
    }

    // Unordered list
    if (/^[-*+]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*+]\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    // Ordered list
    if (/^\d+[.)]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.)]\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    // Blockquote
    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push({ kind: "quote", lines: quoteLines });
      continue;
    }

    // Paragraph: gather consecutive non-blank, non-special lines
    const paragraph: string[] = [line];
    i += 1;
    while (i < lines.length) {
      const next = lines[i].trim();
      if (
        next === "" ||
        next.startsWith("```") ||
        next.startsWith(">") ||
        /^(#{1,4})\s+/.test(next) ||
        /^[-*+]\s+/.test(next) ||
        /^\d+[.)]\s+/.test(next) ||
        /^(-{3,}|\*{3,}|_{3,})$/.test(next)
      ) {
        break;
      }
      paragraph.push(lines[i]);
      i += 1;
    }
    blocks.push({ kind: "p", text: paragraph.join("\n") });
  }

  return blocks;
}

function withBreaks(text: string, keyPrefix: string): ReactNode[] {
  return text.split("\n").flatMap((segment, idx, all) => {
    const rendered = renderInline(segment, `${keyPrefix}-l${idx}`);
    return idx < all.length - 1
      ? [...rendered, <br key={`${keyPrefix}-br${idx}`} />]
      : rendered;
  });
}

export function MessageContent({ content }: { content: string }) {
  const blocks = parseBlocks(content);

  return (
    <div className="chat-prose">
      {blocks.map((block, index) => {
        const key = `b${index}`;
        switch (block.kind) {
          case "heading": {
            const Tag = (`h${Math.min(block.level + 2, 6)}` as "h3" | "h4" | "h5" | "h6");
            return <Tag key={key}>{renderInline(block.text, key)}</Tag>;
          }
          case "ul":
            return (
              <ul key={key}>
                {block.items.map((item, idx) => (
                  <li key={`${key}-${idx}`}>{renderInline(item, `${key}-${idx}`)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={key}>
                {block.items.map((item, idx) => (
                  <li key={`${key}-${idx}`}>{renderInline(item, `${key}-${idx}`)}</li>
                ))}
              </ol>
            );
          case "quote":
            return (
              <blockquote key={key}>
                {block.lines.map((line, idx) => (
                  <Fragment key={`${key}-${idx}`}>
                    {renderInline(line, `${key}-${idx}`)}
                    {idx < block.lines.length - 1 ? <br /> : null}
                  </Fragment>
                ))}
              </blockquote>
            );
          case "code":
            return (
              <pre key={key}>
                <code>{block.text}</code>
              </pre>
            );
          case "hr":
            return <hr key={key} />;
          default:
            return <p key={key}>{withBreaks(block.text, key)}</p>;
        }
      })}
    </div>
  );
}
