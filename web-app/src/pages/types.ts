export type Branch = { id: string; code: string; name: string; timezone: string; is_active?: boolean };
export type User = {
  id: string;
  email?: string;
  username: string;
  full_name: string;
  is_active?: boolean;
  is_superuser: boolean;
};
export type Role = { id: number; name: string; description?: string | null };
export type BranchAssignmentUser = { user_id: string; username: string; email: string; role_id: number | null };
export type Contact = { id: string; phone_number: string; first_name?: string; last_name?: string; consented: boolean };
export type ContactImportResult = { inserted: number; skipped: number };
export type ContactGroup = {
  id: string;
  branch_id: string;
  name: string;
  description?: string | null;
  member_count: number;
  eligible_member_count: number;
  created_at: string;
};
export type ContactGroupDetail = ContactGroup & { members: Contact[] };
export type Template = { id: string; name: string; body: string; is_official: boolean };
export type Campaign = { id: string; name: string; status: string; created_at: string; scheduled_at?: string | null };
export type CampaignBatchUploadResult = {
  campaign_id: string;
  status: string;
  inserted: number;
  skipped: number;
  queued: number;
};
export type CampaignSubmitResult = { status: string; recipients: number; queued: number };
export type CampaignRecipientDetail = {
  id: string;
  queue_id: string | null;
  contact_name: string;
  phone_number: string;
  message_body: string;
  status: string;
  attempts: number;
  sent_at?: string | null;
  error_message?: string | null;
};
export type QueueItem = {
  id: string;
  campaign_name: string;
  status: string;
  attempts: number;
  sent_at?: string | null;
  error_message?: string;
  phone_number?: string;
  modem_id?: string | null;
  execution_branch_id?: string | null;
  failover_route_id?: string | null;
};
export type Modem = {
  id: string;
  branch_id: string;
  name: string;
  node_name: string;
  imei?: string | null;
  port?: string | null;
  status: string;
  last_seen_at?: string;
};
export type Heartbeat = { node_name: string; status: string; last_seen_at: string };
export type FailoverPolicy = {
  id?: string | null;
  branch_id: string;
  enabled: boolean;
  offline_after_seconds: number;
  failover_delay_seconds: number;
  claim_timeout_seconds: number;
};
export type FailoverRoute = {
  id: string;
  source_branch_id: string;
  backup_branch_id: string;
  backup_branch_code?: string | null;
  backup_branch_name?: string | null;
  priority: number;
  enabled: boolean;
};
export type FailoverStatus = {
  policy: FailoverPolicy;
  routes: FailoverRoute[];
  local_modems_healthy: boolean;
  healthy_local_modems: number;
  failover_active: boolean;
  pending_messages: number;
  failover_messages: number;
};
export type Report = {
  campaigns_total: number;
  messages_sent: number;
  messages_failed: number;
  pending_queue: number;
};
export type DeliveryTrendPoint = { date: string; sent: number; failed: number };
export type AuditLog = {
  id: string;
  action: string;
  entity_type: string;
  created_at: string;
  payload?: Record<string, unknown>;
};
export type ScheduleRule = {
  id: string;
  name: string;
  minute_of_day: number;
  days_of_week: string;
  timezone: string;
  is_active: boolean;
  template_id?: string | null;
  message_body?: string | null;
};
export type IncomingMessage = {
  id: string;
  phone_number: string;
  contact_name?: string | null;
  message_text: string;
  received_at: string;
  processed: boolean;
};
export type OptOutItem = { id: string; phone_number: string; source: string; reason: string; created_at: string };
export type ApiKey = {
  id: string;
  branch_id: string;
  label: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
};
export type ApiKeyCreated = ApiKey & { api_key: string };

export type BadgeVariant = "default" | "secondary" | "outline" | "success" | "warning" | "destructive";
export type TabKey =
  | "dashboard"
  | "contacts"
  | "groups"
  | "templates"
  | "campaigns"
  | "rules"
  | "queue"
  | "incoming"
  | "modems"
  | "audit"
  | "admin_users"
  | "admin_access"
  | "admin_branches";
