export interface BrainDecision {
  id: number;
  project_id: number;
  thread_id: number | null;
  date: string;
  decision: string;
  context: string | null;
  decided_by: string | null;
  impact: string | null;
}

export interface BrainEvent {
  id: number;
  project_id: number;
  date: string;
  type: string; // milestone | deploy | meeting | email | call
  title: string;
  summary: string | null;
  source: string | null;
  participants_json: unknown[] | null;
}

export interface BrainTask {
  id: number;
  project_id: number;
  title: string;
  status: string; // open | in_progress | done | blocked | waiting | cancelled
  owner_entity_id: number | null;
  owner_name: string | null;
  priority: number;
  due_date: string | null;
  blocked_by_task_id: number | null;
  notes: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface BrainStats {
  available: boolean;
  entities: number;
  decisions: number;
  events: number;
  tasks: { total: number; open: number; done: number; [key: string]: number };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface BrainTasksResponse extends PaginatedResponse<BrainTask> {
  by_status: Record<string, number>;
}
