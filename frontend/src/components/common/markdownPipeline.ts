import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkRehype from 'remark-rehype';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import rehypeStringify from 'rehype-stringify';

export interface RenderMarkdownOptions {
  isStreaming?: boolean;
}

export const markdownSanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    '*': [...(defaultSchema.attributes?.['*'] || []), 'className', 'align'],
    code: [...(defaultSchema.attributes?.code || []), 'className'],
    th: [...(defaultSchema.attributes?.th || []), 'align'],
    td: [...(defaultSchema.attributes?.td || []), 'align'],
  },
};

function addClass(node: any, ...classes: string[]) {
  const existing = Array.isArray(node.properties?.className)
    ? node.properties.className
    : typeof node.properties?.className === 'string'
      ? node.properties.className.split(' ')
      : [];
  node.properties = {
    ...node.properties,
    className: Array.from(new Set([...existing, ...classes])),
  };
}

export function rehypeElementStyling() {
  return (tree: any) => {
    function visit(node: any, parent: any, index: number) {
      if (node && node.type === 'element') {
        switch (node.tagName) {
          case 'table': {
            addClass(node, 'w-full', 'text-left', 'border-collapse', 'text-xs');
            const isAlreadyWrapped =
              parent &&
              parent.tagName === 'div' &&
              parent.properties?.className?.includes('overflow-x-auto');
            if (!isAlreadyWrapped && parent && typeof index === 'number') {
              const wrapper = {
                type: 'element',
                tagName: 'div',
                properties: {
                  className: [
                    'overflow-x-auto',
                    'my-3',
                    'rounded-xl',
                    'border',
                    'border-slate-700/80',
                    'bg-slate-900/60',
                    'shadow-inner',
                    'max-w-full',
                  ],
                },
                children: [node],
              };
              parent.children[index] = wrapper;
              // Continue traversing the table node and its children (thead, tbody, tr, th, td)
            }
            break;
          }
          case 'thead':
            addClass(node, 'bg-slate-900/95', 'border-b', 'border-slate-700', 'text-emerald-400', 'font-bold');
            break;
          case 'tbody':
            addClass(node, 'divide-y', 'divide-slate-800/80');
            break;
          case 'tr':
            addClass(node, 'hover:bg-slate-800/40', 'transition-colors');
            break;
          case 'th':
            addClass(
              node,
              'py-2.5',
              'px-3',
              'text-xs',
              'font-semibold',
              'text-emerald-300',
              'border-r',
              'border-slate-800/70',
              'last:border-r-0',
              'whitespace-nowrap'
            );
            break;
          case 'td':
            addClass(
              node,
              'py-2',
              'px-3',
              'text-xs',
              'text-slate-200',
              'border-r',
              'border-slate-800/50',
              'last:border-r-0',
              'leading-relaxed',
              'min-w-[100px]'
            );
            break;
          case 'h1':
            addClass(node, 'text-base', 'sm:text-lg', 'font-bold', 'text-white', 'mt-3.5', 'mb-2', 'pb-1', 'border-b', 'border-slate-700/80');
            break;
          case 'h2':
            addClass(node, 'text-sm', 'sm:text-base', 'font-bold', 'text-white', 'mt-3', 'mb-1.5');
            break;
          case 'h3':
            addClass(node, 'text-xs', 'sm:text-sm', 'font-bold', 'text-emerald-300', 'mt-2.5', 'mb-1');
            break;
          case 'h4':
            addClass(node, 'text-xs', 'sm:text-sm', 'font-semibold', 'text-slate-200', 'mt-2', 'mb-1');
            break;
          case 'p':
            addClass(node, 'mb-2.5', 'last:mb-0', 'leading-relaxed', 'text-slate-200');
            break;
          case 'ul':
            addClass(node, 'list-disc', 'pl-5', 'space-y-1', 'mb-2.5', 'text-slate-200');
            break;
          case 'ol':
            addClass(node, 'list-decimal', 'pl-5', 'space-y-1', 'mb-2.5', 'text-slate-200');
            break;
          case 'li':
            addClass(node, 'leading-relaxed');
            break;
          case 'strong':
            addClass(node, 'font-bold', 'text-white');
            break;
          case 'code': {
            const isInsidePre = parent && parent.tagName === 'pre';
            if (!isInsidePre) {
              addClass(
                node,
                'bg-slate-900/90',
                'text-emerald-300',
                'px-1.5',
                'py-0.5',
                'rounded',
                'text-[11px]',
                'sm:text-xs',
                'font-mono',
                'border',
                'border-slate-700/60'
              );
            }
            break;
          }
          case 'pre':
            addClass(
              node,
              'bg-slate-950',
              'p-3',
              'rounded-xl',
              'overflow-x-auto',
              'max-w-full',
              'text-[11px]',
              'sm:text-xs',
              'font-mono',
              'border',
              'border-slate-800',
              'text-slate-200',
              'my-2.5'
            );
            break;
          case 'hr':
            addClass(node, 'border-slate-750', 'my-3');
            break;
          case 'blockquote':
            addClass(
              node,
              'border-l-2',
              'border-emerald-500/80',
              'pl-3',
              'my-2',
              'text-slate-400',
              'italic',
              'bg-slate-900/40',
              'py-1',
              'rounded-r-lg'
            );
            break;
        }
      }
      if (node && node.children && Array.isArray(node.children)) {
        for (let i = 0; i < node.children.length; i++) {
          visit(node.children[i], node, i);
        }
      }
    }
    visit(tree, null, 0);
  };
}

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkRehype, { allowDangerousHtml: true })
  .use(rehypeRaw)
  .use(rehypeSanitize, markdownSanitizeSchema)
  .use(rehypeElementStyling)
  .use(rehypeStringify);

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function renderMarkdownSync(content: string, options: RenderMarkdownOptions = {}): string {
  if (!content) return '';
  try {
    const file = processor.processSync(content);
    let html = String(file);
    if (options.isStreaming) {
      html += '<span data-testid="streaming-cursor" class="inline-block w-1.5 h-3.5 ml-1 bg-emerald-400 animate-pulse align-middle"></span>';
    }
    return html;
  } catch {
    // Fallback safely with full HTML escaping on parsing error
    let escaped = escapeHtml(content);
    if (options.isStreaming) {
      escaped += '<span data-testid="streaming-cursor" class="inline-block w-1.5 h-3.5 ml-1 bg-emerald-400 animate-pulse align-middle"></span>';
    }
    return escaped;
  }
}
