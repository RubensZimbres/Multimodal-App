import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// react-markdown does not render raw HTML, so model output cannot inject markup.
export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
