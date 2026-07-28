import { useCallback, useEffect, useMemo, useState } from "react";

import { apiRequest } from "../api/client";
import {
  AuditLog,
  Branch,
  Campaign,
  Contact,
  ContactGroup,
  DeliveryTrendPoint,
  FailoverStatus,
  Heartbeat,
  IncomingMessage,
  Modem,
  OptOutItem,
  QueueItem,
  Report,
  ScheduleRule,
  Template,
  User,
} from "../pages/types";

type UseBranchDataOptions = {
  token: string;
  onError: (message: string) => void;
  onAuthInvalid: () => void;
};

export function useBranchData({ token, onError, onAuthInvalid }: UseBranchDataOptions) {
  const [me, setMe] = useState<User | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("");

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactGroups, setContactGroups] = useState<ContactGroup[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [modems, setModems] = useState<Modem[]>([]);
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([]);
  const [failoverStatus, setFailoverStatus] = useState<FailoverStatus | null>(null);
  const [incomingMessages, setIncomingMessages] = useState<IncomingMessage[]>([]);
  const [optOuts, setOptOuts] = useState<OptOutItem[]>([]);
  const [rules, setRules] = useState<ScheduleRule[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [deliveryTrend, setDeliveryTrend] = useState<DeliveryTrendPoint[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const selectedBranchMeta = useMemo(
    () => branches.find((branch) => branch.id === selectedBranch),
    [branches, selectedBranch],
  );

  const clearData = useCallback(() => {
    setMe(null);
    setBranches([]);
    setSelectedBranch("");
    setContacts([]);
    setContactGroups([]);
    setTemplates([]);
    setCampaigns([]);
    setQueueItems([]);
    setModems([]);
    setHeartbeats([]);
    setFailoverStatus(null);
    setIncomingMessages([]);
    setOptOuts([]);
    setRules([]);
    setReport(null);
    setDeliveryTrend([]);
    setAuditLogs([]);
  }, []);

  const refreshBranchData = useCallback(
    async (activeToken: string, branchId: string) => {
      const query = `?branch_id=${branchId}`;
      try {
        const [
          contactRows,
          contactGroupRows,
          templateRows,
          campaignRows,
          ruleRows,
          queueRows,
          incomingRows,
          optOutRows,
          modemRows,
          heartbeatRows,
          failoverRow,
          reportRow,
          deliveryTrendRows,
          auditRows,
        ] = await Promise.all([
          apiRequest<Contact[]>(`/api/contacts${query}`, "GET", undefined, activeToken),
          apiRequest<ContactGroup[]>(`/api/contacts/groups${query}`, "GET", undefined, activeToken),
          apiRequest<Template[]>(`/api/templates${query}`, "GET", undefined, activeToken),
          apiRequest<Campaign[]>(`/api/campaigns${query}`, "GET", undefined, activeToken),
          apiRequest<ScheduleRule[]>(`/api/rules${query}`, "GET", undefined, activeToken),
          apiRequest<QueueItem[]>(`/api/queue${query}`, "GET", undefined, activeToken),
          apiRequest<IncomingMessage[]>(`/api/incoming${query}`, "GET", undefined, activeToken),
          apiRequest<{ items: OptOutItem[] }>(`/api/contacts/opt-outs${query}`, "GET", undefined, activeToken),
          apiRequest<Modem[]>(`/api/modems${query}`, "GET", undefined, activeToken),
          apiRequest<{ items: Heartbeat[] }>(`/api/modems/heartbeats${query}`, "GET", undefined, activeToken),
          apiRequest<FailoverStatus>(`/api/failover/${branchId}`, "GET", undefined, activeToken),
          apiRequest<Report>(`/api/reports/summary${query}`, "GET", undefined, activeToken),
          apiRequest<DeliveryTrendPoint[]>(
            `/api/reports/delivery-trend${query}&days=7`,
            "GET",
            undefined,
            activeToken,
          ).catch(() => []),
          apiRequest<AuditLog[]>(`/api/audit${query}`, "GET", undefined, activeToken),
        ]);
        setContacts(contactRows);
        setContactGroups(contactGroupRows);
        setTemplates(templateRows);
        setCampaigns(campaignRows);
        setRules(ruleRows);
        setQueueItems(queueRows);
        setIncomingMessages(incomingRows);
        setOptOuts(optOutRows.items);
        setModems(modemRows);
        setHeartbeats(heartbeatRows.items);
        setFailoverStatus(failoverRow);
        setReport(reportRow);
        setDeliveryTrend(deliveryTrendRows);
        setAuditLogs(auditRows);
        onError("");
      } catch (err) {
        onError((err as Error).message);
      }
    },
    [onError],
  );

  const refreshCampaigns = useCallback(async (activeToken: string, branchId: string) => {
    const campaignRows = await apiRequest<Campaign[]>(
      `/api/campaigns?branch_id=${branchId}`,
      "GET",
      undefined,
      activeToken,
    );
    setCampaigns(campaignRows);
  }, []);

  const refreshContactGroups = useCallback(async (activeToken: string, branchId: string) => {
    const groupRows = await apiRequest<ContactGroup[]>(
      `/api/contacts/groups?branch_id=${branchId}`,
      "GET",
      undefined,
      activeToken,
    );
    setContactGroups(groupRows);
  }, []);

  const refreshProfileAndBranches = useCallback(
    async (activeToken: string) => {
      try {
        const user = await apiRequest<User>("/api/auth/me", "GET", undefined, activeToken);
        const branchRows = await apiRequest<Branch[]>("/api/admin/branches", "GET", undefined, activeToken);
        setMe(user);
        setBranches(branchRows);
        setSelectedBranch((current) =>
          current && branchRows.some((branch) => branch.id === current) ? current : (branchRows[0]?.id ?? ""),
        );
        onError("");
      } catch (err) {
        onError((err as Error).message);
        onAuthInvalid();
        throw err;
      }
    },
    [onError, onAuthInvalid],
  );

  useEffect(() => {
    if (!token) {
      clearData();
      return;
    }
    void refreshProfileAndBranches(token).catch(() => undefined);
  }, [token, clearData, refreshProfileAndBranches]);

  useEffect(() => {
    if (!token || !selectedBranch) {
      return;
    }
    void refreshBranchData(token, selectedBranch);
  }, [token, selectedBranch, refreshBranchData]);

  return {
    me,
    branches,
    selectedBranch,
    setSelectedBranch,
    selectedBranchMeta,
    contacts,
    contactGroups,
    templates,
    campaigns,
    queueItems,
    modems,
    heartbeats,
    failoverStatus,
    incomingMessages,
    optOuts,
    rules,
    report,
    deliveryTrend,
    auditLogs,
    refreshBranchData,
    refreshCampaigns,
    refreshContactGroups,
    refreshProfileAndBranches,
  };
}
