import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownContent({ children }: { children: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children: label, ...props }) => (
          <a href={browserHref(href)} {...props}>
            {label}
          </a>
        ),
      }}
    >
      {children}
    </Markdown>
  );
}

function browserHref(href?: string) {
  if (!href) return href;
  let localPath = href;
  if (href.startsWith("file://")) {
    try {
      localPath = decodeURIComponent(new URL(href).pathname);
    } catch {
      return href;
    }
  }
  if (
    localPath.startsWith("/") &&
    localPath.includes("/runtime/creative-projects/")
  ) {
    return `/api/creative-projects/file?path=${encodeURIComponent(localPath)}`;
  }
  return href;
}
