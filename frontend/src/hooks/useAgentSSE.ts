import { useState, useEffect, useRef } from 'react';

export interface AgentStatus {
  id: string;
  name: string;
  status: string;
  role?: string;
}

export function useAgentSSE() {
  const [agents, setAgents] = useState<Map<string, AgentStatus>>(new Map());
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource('/api/events/agents');
    eventSourceRef.current = es;

    es.addEventListener('agent.snapshot', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        const list: AgentStatus[] = data.data?.agents ?? [];
        setAgents(new Map(list.map(a => [a.id, a])));
      } catch { /* malformed payload — skip */ }
    });

    const statusEvents = [
      'agent.spawned',
      'agent.paused',
      'agent.resumed',
      'agent.killed',
      'agent.completed',
      'agent.failed',
    ];

    for (const evt of statusEvents) {
      es.addEventListener(evt, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          const agentData = data.data;
          if (agentData?.agent_id) {
            setAgents(prev => {
              const next = new Map(prev);
              const existing = next.get(agentData.agent_id);
              next.set(agentData.agent_id, {
                ...existing,
                id: agentData.agent_id,
                name: agentData.name ?? existing?.name ?? '',
                status: agentData.status ?? evt.replace('agent.', ''),
              });
              return next;
            });
          }
        } catch { /* malformed payload — skip */ }
      });
    }

    es.onerror = () => {
      // EventSource auto-reconnects on error
    };

    return () => {
      es.close();
    };
  }, []);

  return agents;
}
