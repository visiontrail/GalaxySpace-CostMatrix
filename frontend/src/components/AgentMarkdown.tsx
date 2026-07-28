import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const AgentMarkdown = memo(({ content }: { content: string }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      a: ({ node, ...props }) => {
        void node
        return <a {...props} target="_blank" rel="noopener noreferrer" />
      },
      table: ({ node, ...props }) => {
        void node
        return (
          <div className="agent-markdown-table">
            <table {...props} />
          </div>
        )
      },
    }}
  >
    {content}
  </ReactMarkdown>
))

AgentMarkdown.displayName = 'AgentMarkdown'

export default AgentMarkdown
