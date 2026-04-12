import { useRef } from 'react';
import { cn } from '../../lib/utils';
import { RichContent } from '../shared/RichContent';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  model?: string;
  created_at: string;
}

function formatTime(date: string): string {
  return new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const contentRef = useRef<HTMLDivElement>(null);

  return (
    <div className={cn('flex gap-3', isUser ? 'justify-end' : 'justify-start')}>
      {/* CoCo avatar for assistant */}
      {!isUser && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent flex items-center justify-center mt-1">
          <span className="text-xs font-bold text-accent-foreground">C</span>
        </div>
      )}

      <div
        className={cn(
          'max-w-[70%] px-4 py-2',
          isUser
            ? 'bg-accent text-accent-foreground rounded-2xl rounded-br-sm'
            : 'bg-card border border-border rounded-2xl rounded-bl-sm',
        )}
      >
        <div
          ref={contentRef}
          className={cn(
            'text-sm leading-relaxed chat-content',
            isUser ? 'text-accent-foreground' : 'text-foreground',
          )}
        >
          <RichContent text={message.content} html />
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-0.5 bg-accent animate-pulse rounded-sm align-text-bottom" />
          )}
        </div>
        <p className={cn(
          'text-xs mt-1 text-right',
          isUser ? 'text-accent-foreground/70' : 'text-muted-foreground',
        )}>
          {isStreaming ? (
            <span className="italic">Streaming...</span>
          ) : (
            <>
              {formatTime(message.created_at)}
              {message.model && <span className="ml-2 font-mono">{message.model}</span>}
            </>
          )}
        </p>
      </div>
    </div>
  );
}
