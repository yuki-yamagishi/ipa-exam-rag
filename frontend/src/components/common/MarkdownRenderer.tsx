import React, { useMemo } from 'react';
import { renderMarkdownSync } from './markdownPipeline';

export interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  isStreaming = false,
  className = '',
}) => {
  const htmlContent = useMemo(() => {
    return renderMarkdownSync(content, { isStreaming });
  }, [content, isStreaming]);

  return (
    <div
      className={`markdown-content select-text text-xs sm:text-sm leading-relaxed text-slate-100 min-w-0 max-w-full break-words ${className}`}
      dangerouslySetInnerHTML={{ __html: htmlContent }}
    />
  );
};
