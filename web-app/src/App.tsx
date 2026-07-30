import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "./components/ui/alert";
import { useAdminActions, useAuth, useBranchData, useCampaignActions } from "./hooks";
import {
  AdminAccessPage,
  AdminBranchesPage,
  AdminUsersPage,
  AppHeader,
  AppSidebar,
  AuditPage,
  CampaignsPage,
  ContactsPage,
  DashboardPage,
  GroupsPage,
  IncomingPage,
  LoginPage,
  ModemsPage,
  QueuePage,
  RulesPage,
  TabKey,
  TemplatesPage,
} from "./pages";

const pageMeta: Record<TabKey, { eyebrow: string; title: string; description: string }> = {
  dashboard: { eyebrow: "Workspace", title: "Overview", description: "A live snapshot of messaging activity for the active branch." },
  contacts: { eyebrow: "Workspace", title: "Contacts", description: "Manage consented recipients for campaigns." },
  groups: { eyebrow: "Workspace", title: "Contact groups", description: "Organize branch contacts into reusable recipient groups." },
  templates: { eyebrow: "Workspace", title: "Message templates", description: "Create reusable, approved content for faster sending." },
  campaigns: { eyebrow: "Workspace", title: "Campaigns", description: "Create individual or batch messaging campaigns." },
  rules: { eyebrow: "Operations", title: "Schedules", description: "Automate recurring branch messaging." },
  queue: { eyebrow: "Operations", title: "Message queue", description: "Monitor deliveries and retry failed messages." },
  incoming: { eyebrow: "Operations", title: "Inbox & opt-outs", description: "Review replies and keep recipient preferences current." },
  modems: { eyebrow: "System", title: "Modems", description: "Monitor registered hardware and branch connectivity." },
  audit: { eyebrow: "System", title: "Audit log", description: "Trace recent branch activity and system events." },
  admin_users: { eyebrow: "Administration", title: "Users", description: "Create accounts and control system-level access." },
  admin_access: { eyebrow: "Administration", title: "Access control", description: "Define roles and assign users to branches." },
  admin_branches: { eyebrow: "Administration", title: "Branches", description: "Manage the organization’s messaging locations." },
};

export function App() {
  const [error, setError] = useState("");
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [groupToManage, setGroupToManage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("tb_sidebar_collapsed") === "true");

  useEffect(() => {
    localStorage.setItem("tb_sidebar_collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  const auth = useAuth({ onError: setError });
  const branchData = useBranchData({
    token: auth.token,
    onError: setError,
    onAuthInvalid: auth.signOut,
  });

  const actions = useCampaignActions({
    token: auth.token,
    selectedBranch: branchData.selectedBranch,
    selectedBranchTimezone: branchData.selectedBranchMeta?.timezone,
    refreshBranchData: branchData.refreshBranchData,
    onError: setError,
  });

  const isSuperuser = Boolean(branchData.me?.is_superuser);

  const admin = useAdminActions({
    token: auth.token,
    isSuperuser,
    selectedBranch: branchData.selectedBranch,
    branches: branchData.branches,
    refreshProfileAndBranches: branchData.refreshProfileAndBranches,
    setSelectedBranch: branchData.setSelectedBranch,
    refreshBranchData: branchData.refreshBranchData,
    onError: setError,
  });

  useEffect(() => {
    if (!isSuperuser && tab.startsWith("admin_")) {
      setTab("dashboard");
    }
  }, [isSuperuser, tab]);

  async function refreshCurrentData() {
    if (!auth.token || !branchData.selectedBranch || isRefreshing) return;
    setIsRefreshing(true);
    try {
      await branchData.refreshBranchData(auth.token, branchData.selectedBranch);
    } finally {
      setIsRefreshing(false);
    }
  }

  if (!auth.token) {
    return (
      <LoginPage
        username={auth.username}
        password={auth.password}
        error={error}
        onUsernameChange={auth.setUsername}
        onPasswordChange={auth.setPassword}
        onSubmit={auth.handleLogin}
      />
    );
  }

  const content = (() => {
    switch (tab) {
      case "dashboard":
        return (
          <DashboardPage
            report={branchData.report}
            deliveryTrend={branchData.deliveryTrend}
          />
        );
      case "contacts":
        return (
          <ContactsPage
            contacts={branchData.contacts}
            newPhone={actions.newPhone}
            newContactFirstName={actions.newContactFirstName}
            newContactLastName={actions.newContactLastName}
            onNewPhoneChange={actions.setNewPhone}
            onNewContactFirstNameChange={actions.setNewContactFirstName}
            onNewContactLastNameChange={actions.setNewContactLastName}
            onAddContact={actions.addContact}
            onDeleteContact={(contactId) => void actions.deleteContact(contactId)}
            onEditContact={actions.updateContact}
            contactImportInputKey={actions.contactImportInputKey}
            contactImportSummary={actions.contactImportSummary}
            isImportingContacts={actions.isImportingContacts}
            onContactImportFileChange={actions.setContactImportFile}
            onImportContacts={actions.importContacts}
            onExportContacts={() => void actions.exportContacts()}
            branchLabel={
              branchData.selectedBranchMeta
                ? `${branchData.selectedBranchMeta.code} — ${branchData.selectedBranchMeta.name}`
                : ""
            }
            branches={branchData.branches}
            selectedBranch={branchData.selectedBranch}
            onBranchChange={branchData.setSelectedBranch}
          />
        );
      case "templates":
        return (
          <TemplatesPage
            templates={branchData.templates}
            newTemplateName={actions.newTemplateName}
            newTemplateBody={actions.newTemplateBody}
            onTemplateNameChange={actions.setNewTemplateName}
            onTemplateBodyChange={actions.setNewTemplateBody}
            onAddTemplate={actions.addTemplate}
            onDeleteTemplate={(templateId) => void actions.deleteTemplate(templateId)}
            onEditTemplate={actions.updateTemplate}
          />
        );
      case "groups":
        return (
          <GroupsPage
            groups={branchData.contactGroups}
            contacts={branchData.contacts}
            token={auth.token}
            branchId={branchData.selectedBranch}
            onRefresh={() => branchData.refreshContactGroups(auth.token, branchData.selectedBranch)}
            initialGroupId={groupToManage}
            onInitialGroupHandled={() => setGroupToManage(null)}
            onExternalEditorClose={() => setTab("campaigns")}
          />
        );
      case "campaigns":
        return (
          <CampaignsPage
            templates={branchData.templates}
            groups={branchData.contactGroups}
            eligibleContactsCount={branchData.contacts.filter((contact) => contact.consented).length}
            newCampaignName={actions.newCampaignName}
            newCampaignMessage={actions.newCampaignMessage}
            newCampaignScheduledAt={actions.newCampaignScheduledAt}
            selectedCampaignTemplateId={actions.selectedCampaignTemplateId}
            selectedCampaignGroupId={actions.selectedCampaignGroupId}
            campaignSubmitSummary={actions.campaignSubmitSummary}
            isSubmittingCampaign={actions.isSubmittingCampaign}
            batchCampaignName={actions.batchCampaignName}
            batchUploadInputKey={actions.batchUploadInputKey}
            batchUploadSummary={actions.batchUploadSummary}
            isUploadingBatch={actions.isUploadingBatch}
            onCampaignNameChange={actions.setNewCampaignName}
            onCampaignMessageChange={actions.setNewCampaignMessage}
            onCampaignScheduledAtChange={actions.setNewCampaignScheduledAt}
            onCampaignTemplateChange={actions.setSelectedCampaignTemplateId}
            onCampaignGroupChange={actions.setSelectedCampaignGroupId}
            onBatchCampaignNameChange={actions.setBatchCampaignName}
            onBatchFileChange={actions.setBatchUploadFile}
            onManageGroup={(groupId) => {
              setGroupToManage(groupId);
              setTab("groups");
            }}
            onCreateAndSubmitCampaign={actions.createAndSubmitCampaign}
            onUploadBatchCampaign={actions.uploadBatchCampaign}
            onDownloadBatchTemplate={() => void actions.downloadBatchTemplate()}
          />
        );
      case "rules":
        return (
          <RulesPage
            rules={branchData.rules}
            templates={branchData.templates}
            timezone={branchData.selectedBranchMeta?.timezone ?? "Asia/Manila"}
            newRuleName={actions.newRuleName}
            newRuleTime={actions.newRuleTime}
            newRuleDaysOfWeek={actions.newRuleDaysOfWeek}
            newRuleMessage={actions.newRuleMessage}
            selectedRuleTemplateId={actions.selectedRuleTemplateId}
            onRuleNameChange={actions.setNewRuleName}
            onRuleTimeChange={actions.setNewRuleTime}
            onRuleDaysOfWeekChange={actions.setNewRuleDaysOfWeek}
            onRuleMessageChange={actions.setNewRuleMessage}
            onRuleTemplateChange={actions.setSelectedRuleTemplateId}
            onCreateRule={actions.createRule}
            onDisableRule={(ruleId) => void actions.disableRule(ruleId)}
            onEnableRule={(ruleId) => void actions.enableRule(ruleId)}
            onEditRule={actions.updateRule}
          />
        );
      case "queue":
        return (
          <QueuePage
            campaigns={branchData.campaigns}
            token={auth.token}
            branchId={branchData.selectedBranch}
            branches={branchData.branches}
            isSuperuser={isSuperuser}
            refreshCampaigns={branchData.refreshCampaigns}
          />
        );
      case "incoming":
        return (
          <IncomingPage
            incomingMessages={branchData.incomingMessages}
            optOuts={branchData.optOuts}
            manualOptOutPhone={actions.manualOptOutPhone}
            manualOptOutReason={actions.manualOptOutReason}
            onManualOptOutPhoneChange={actions.setManualOptOutPhone}
            onManualOptOutReasonChange={actions.setManualOptOutReason}
            onAddManualOptOut={actions.addManualOptOut}
          />
        );
      case "modems":
        return (
          <ModemsPage
            modems={branchData.modems}
            failoverStatus={branchData.failoverStatus}
            branches={branchData.branches}
            selectedBranch={branchData.selectedBranch}
            token={auth.token}
            isSuperuser={isSuperuser}
            onRefresh={() => branchData.refreshBranchData(auth.token, branchData.selectedBranch)}
          />
        );
      case "audit":
        return <AuditPage auditLogs={branchData.auditLogs} />;
      case "admin_users":
        return (
            <AdminUsersPage
              users={admin.users}
              branches={branchData.branches}
            newUserEmail={admin.newUserEmail}
            newUserUsername={admin.newUserUsername}
            newUserFullName={admin.newUserFullName}
            newUserPassword={admin.newUserPassword}
              newUserIsSuperuser={admin.newUserIsSuperuser}
              newUserBranchId={admin.newUserBranchId}
            onNewUserEmailChange={admin.setNewUserEmail}
            onNewUserUsernameChange={admin.setNewUserUsername}
            onNewUserFullNameChange={admin.setNewUserFullName}
            onNewUserPasswordChange={admin.setNewUserPassword}
              onNewUserIsSuperuserChange={admin.setNewUserIsSuperuser}
              onNewUserBranchChange={admin.setNewUserBranchId}
            onCreateUser={admin.createUser}
            onUpdateUser={admin.updateUser}
          />
        );
      case "admin_access":
        return (
          <AdminAccessPage
            roles={admin.roles}
            newRoleName={admin.newRoleName}
            newRoleDescription={admin.newRoleDescription}
            onNewRoleNameChange={admin.setNewRoleName}
            onNewRoleDescriptionChange={admin.setNewRoleDescription}
            onCreateRole={admin.createRole}
            branches={branchData.branches}
            users={admin.users}
            branchUsers={admin.branchUsers}
            assignmentBranchId={admin.assignmentBranchId}
            assignUserId={admin.assignUserId}
            assignBranchId={admin.assignBranchId}
            assignRoleId={admin.assignRoleId}
            onAssignmentBranchChange={admin.setAssignmentBranchId}
            onAssignUserChange={admin.setAssignUserId}
            onAssignBranchChange={admin.setAssignBranchId}
            onAssignRoleChange={admin.setAssignRoleId}
            onAssignUserBranch={admin.assignUserBranch}
            token={auth.token}
          />
        );
      case "admin_branches":
        return (
          <AdminBranchesPage
            branches={branchData.branches}
            newBranchCode={admin.newBranchCode}
            newBranchName={admin.newBranchName}
            newBranchTimezone={admin.newBranchTimezone}
            onNewBranchCodeChange={admin.setNewBranchCode}
            onNewBranchNameChange={admin.setNewBranchName}
            onNewBranchTimezoneChange={admin.setNewBranchTimezone}
            onCreateBranch={admin.createBranch}
          />
        );
    }
  })();

  const meta = pageMeta[tab];

  return (
    <div className="min-h-screen bg-slate-50/80">
      <AppSidebar
        activeTab={tab}
        isSuperuser={isSuperuser}
        mobileOpen={mobileOpen}
        collapsed={sidebarCollapsed}
        onNavigate={setTab}
        onClose={() => setMobileOpen(false)}
        onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
      />
      <div className={`min-h-screen transition-[padding] duration-200 ${sidebarCollapsed ? "lg:pl-[84px]" : "lg:pl-[280px]"}`}>
        <AppHeader
          me={branchData.me}
          branches={branchData.branches}
          selectedBranch={branchData.selectedBranch}
          selectedBranchTimezone={branchData.selectedBranchMeta?.timezone}
          onBranchChange={branchData.setSelectedBranch}
          onOpenMenu={() => setMobileOpen(true)}
          onRefresh={() => void refreshCurrentData()}
          isRefreshing={isRefreshing}
          onSignOut={() => {
            auth.signOut();
            setError("");
          }}
        />

        <main className="mx-auto max-w-[1500px] p-4 md:p-6 lg:p-8">
          <div className="mb-6 animate-fade-in">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">{meta.eyebrow}</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight md:text-3xl">{meta.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{meta.description}</p>
          </div>

          {error && (
            <Alert className="mb-5" variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Request failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="animate-slide-up">{content}</div>
        </main>
      </div>
    </div>
  );
}
