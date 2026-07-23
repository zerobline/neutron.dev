"use client";

import { Highlight, themes } from "prism-react-renderer";

interface CodeViewerProps {
  code: string;
  language: string;
}

const langMap: Record<string, string> = {
  html: "markup",
  htm: "markup",
  css: "css",
  js: "javascript",
  jsx: "jsx",
  ts: "typescript",
  tsx: "tsx",
  json: "json",
  md: "markdown",
  py: "python",
};

export function getLanguage(filePath: string): string {
  const ext = filePath.substring(filePath.lastIndexOf(".") + 1).toLowerCase();
  return langMap[ext] ?? "markup";
}

export function CodeViewer({ code, language }: CodeViewerProps) {
  return (
    <Highlight theme={themes.nightOwl} code={code} language={language}>
      {({ style, tokens, getLineProps, getTokenProps }) => (
        <pre
          className="p-4 text-sm font-mono overflow-auto h-full m-0"
          style={{ ...style, background: "transparent" }}
        >
          {tokens.map((line, i) => (
            <div key={i} {...getLineProps({ line })} className="table-row">
              <span className="table-cell pr-4 text-right select-none text-muted/40 w-8">
                {i + 1}
              </span>
              <span className="table-cell">
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </span>
            </div>
          ))}
        </pre>
      )}
    </Highlight>
  );
}
