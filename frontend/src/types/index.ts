export type BuildMode = "team" | "engineer" | "goal";

export type AgentName = "team_leader" | "product_manager" | "architect" | "engineer" | "data_scientist";

export type AgentStatusType = "idle" | "thinking" | "working" | "complete" | "error";

export interface ThinkingMessage {
  agent: AgentName;
  content: string;
  stream?: string;
  timestamp: number;
}

export type ProjectStatus =
  | "created"
  | "leading"
  | "analyzing"
  | "planning"
  | "architecting"
  | "building"
  | "awaiting_feedback"
  | "complete"
  | "error";

export type PhaseResultKind = "brief" | "analysis" | "plan" | "architecture" | "build" | "markdown";

export interface PhaseResult {
  id: string;
  phase: string;
  agent: AgentName;
  kind: PhaseResultKind;
  headline: string;
  summary: string;
  content?: string;
  spec?: Record<string, unknown> | null;
  hasStructuredSpec: boolean;
  timestamp: number;
}

export interface FeedbackRequest {
  phase: string;
  agent: AgentName;
  content: string;
  message: string;
  summary?: string;
  headline?: string;
  kind?: PhaseResultKind;
  spec?: Record<string, unknown> | null;
}

export interface AgentInfo {
  id: AgentName;
  name: string;
  role: string;
  avatar: string;
  color: string;
}

export interface AgentStatus {
  agent: AgentName;
  status: AgentStatusType;
  currentTask?: string;
}

export interface Message {
  id: string;
  role: "user" | "agent" | "system";
  agent?: AgentName;
  content: string;
  timestamp: number;
  kind?: "error" | "thinking" | "phase_result";
  phase?: string;
  category?: string;
  details?: string;
  nextAction?: string;
  phaseResult?: PhaseResult;
}

export interface ProjectFile {
  file_path: string;
  content: string;
}

export type BuildStack = "static" | "nextjs";

export interface Project {
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  template: string | null;
  stack?: BuildStack | string;
  created_at: string;
  updated_at: string;
  token_usage?: TokenUsage | null;
  token_budget?: number | null;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  prompt: string;
  stack?: BuildStack | string;
}

export interface TokenUsage {
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  successful_requests: number;
}

export type ActivityKind = "phase" | "agent" | "tool" | "file" | "checkpoint" | "step";
export type ActivityStatus = "active" | "complete" | "error";

export interface BuildActivity {
  id: string;
  kind: ActivityKind;
  title: string;
  summary?: string;
  details?: string;
  agent?: AgentName;
  phase?: string;
  status: ActivityStatus;
  timestamp: number;
  /** Elapsed tool/step runtime when known (milliseconds). */
  durationMs?: number;
}

export interface ProjectCheckpoint {
  id: string;
  created_at: string;
  parent_id: string;
  branch: string;
  location: string;
}

export interface CompletionChecklistItem {
  id: string;
  label: string;
  ok: boolean;
  detail?: string;
}

export interface CompletionChecklist {
  required_files?: boolean;
  entry_point?: boolean;
  styles?: boolean;
  interactions?: boolean;
  seeded_demo_data?: boolean;
  file_count?: number;
  items?: CompletionChecklistItem[];
}

export interface FollowUpSuggestion {
  id: string;
  label: string;
  prompt: string;
}

export interface BuildCompletion {
  message: string;
  mode?: string;
  files: string[];
  filesChanged: string[];
  checklist: CompletionChecklist | null;
  suggestions: FollowUpSuggestion[];
  timestamp: number;
  canUndo?: boolean;
}

export interface FileDiff {
  path: string;
  status: "added" | "removed" | "modified" | string;
  diff: string;
  truncated?: boolean;
}

export interface LastEditDiff {
  filesChanged: string[];
  diffs: FileDiff[];
  canUndo: boolean;
  message?: string;
  request?: string;
}

export interface WSEvent {
  type: string;
  agent?: AgentName;
  task?: string;
  content?: string;
  summary?: string;
  headline?: string;
  kind?: PhaseResultKind;
  spec?: Record<string, unknown> | null;
  has_structured_spec?: boolean;
  file_path?: string;
  files?: string[];
  files_changed?: string[];
  mode?: string;
  message?: string;
  checklist?: CompletionChecklist | null;
  suggestions?: FollowUpSuggestion[];
  can_undo?: boolean;
  diffs?: FileDiff[];
  restored?: string[];
  phase?: string;
  action?: string;
  feedback?: string;
  category?: string;
  details?: string;
  next_action?: string;
  usage?: TokenUsage;
  token_budget?: number;
  percent?: number;
  checkpoint?: string;
  can_resume?: boolean;
  tool_name?: string;
  status?: ActivityStatus | string;
  title?: string;
  step_type?: string;
  arguments?: string;
  duration_ms?: number;
  started_at?: number;
  branch?: string;
  attempt?: number;
  max_attempts?: number;
}

export const AGENTS: AgentInfo[] = [
  {
    id: "team_leader",
    name: "Kai",
    role: "Team Leader",
    avatar: "/agents/team_leader.svg",
    color: "var(--leader)",
  },
  {
    id: "product_manager",
    name: "Nina",
    role: "Product Manager",
    avatar: "/agents/pm.svg",
    color: "var(--pm)",
  },
  {
    id: "architect",
    name: "Theo",
    role: "System Architect",
    avatar: "/agents/architect.svg",
    color: "var(--architect)",
  },
  {
    id: "engineer",
    name: "Ravi",
    role: "Software Engineer",
    avatar: "/agents/engineer.svg",
    color: "var(--engineer)",
  },
  {
    id: "data_scientist",
    name: "Zara",
    role: "Data Scientist",
    avatar: "/agents/data_scientist.svg",
    color: "var(--scientist)",
  },
];
