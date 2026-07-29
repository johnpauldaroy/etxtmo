import { useEffect, useMemo, useState } from "react";
import { Eye, LoaderCircle, RotateCw, Shuffle, X } from "lucide-react";

import { apiRequest } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { EmptyRow, formatDate, mapStatusToBadge, Pagination, usePagination } from "./common";
import { Branch, Campaign, CampaignRecipientDetail, Modem } from "./types";

type CampaignDeliveryPanelProps = {
  campaigns: Campaign[];
  token: string;
  branches?: Branch[];
  isSuperuser?: boolean;
};

type CampaignDeliveryRow = Campaign & { kind: "campaign"; message_count: number };
type ApiKeyDeliveryRow = {
  kind: "api-key";
  id: string;
  branch_id: string;
  api_key_id: string;
  name: string;
  status: string;
  created_at: string;
  scheduled_at: null;
  message_count: number;
};
type DeliveryRow = CampaignDeliveryRow | ApiKeyDeliveryRow;

const readableStatus = (status: string) => {
  if (status === "approved") return "Scheduled";
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
};

function aggregateApiStatus(statuses: string[]): string {
  if (statuses.every((status) => status === "sent")) return "sent";
  if (statuses.every((status) => status === "failed")) return "failed";
  if (statuses.some((status) => status === "sending")) return "sending";
  if (statuses.some((status) => ["queued", "pending", "approved", "draft"].includes(status))) return "queued";
  if (statuses.includes("sent") && statuses.includes("failed")) return "mixed";
  return statuses[0] ?? "queued";
}

export function CampaignDeliveryPanel({ campaigns, token, branches = [], isSuperuser = false }: CampaignDeliveryPanelProps) {
  const deliveryRows = useMemo<DeliveryRow[]>(() => {
    const rows: DeliveryRow[] = [];
    const apiGroups = new Map<string, Campaign[]>();

    for (const campaign of campaigns) {
      if (campaign.source === "sms_gateway_api" && campaign.api_key_id) {
        const grouped = apiGroups.get(campaign.api_key_id) ?? [];
        grouped.push(campaign);
        apiGroups.set(campaign.api_key_id, grouped);
      } else {
        rows.push({ ...campaign, kind: "campaign", message_count: 1 });
      }
    }

    for (const [apiKeyId, groupedCampaigns] of apiGroups) {
      const latest = groupedCampaigns.reduce((current, campaign) =>
        new Date(campaign.created_at) > new Date(current.created_at) ? campaign : current,
      );
      rows.push({
        kind: "api-key",
        id: `api-key:${apiKeyId}`,
        branch_id: latest.branch_id,
        api_key_id: apiKeyId,
        name: `API — ${latest.api_key_label || `Key ${apiKeyId.slice(0, 8)}`}`,
        status: aggregateApiStatus(groupedCampaigns.map((campaign) => campaign.status)),
        created_at: latest.created_at,
        scheduled_at: null,
        message_count: groupedCampaigns.length,
      });
    }

    return rows.sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  }, [campaigns]);

  const pagination = usePagination(deliveryRows);
  const [selectedDelivery, setSelectedDelivery] = useState<DeliveryRow | null>(null);
  const [recipientDetails, setRecipientDetails] = useState<CampaignRecipientDetail[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");
  const [retryBusyId, setRetryBusyId] = useState<string | null>(null);
  const [retryAllBusy, setRetryAllBusy] = useState(false);
  const [reassignTarget, setReassignTarget] = useState<CampaignDeliveryRow | null>(null);
  const [reassignBranchModems, setReassignBranchModems] = useState<Record<string, Modem[]>>({});
  const [reassignLoading, setReassignLoading] = useState(false);
  const [reassignBranchId, setReassignBranchId] = useState("");
  const [reassignBusy, setReassignBusy] = useState(false);
  const [reassignError, setReassignError] = useState("");
  const recipientPagination = usePagination(recipientDetails);
  const deliveryCounts = recipientDetails.reduce<Record<string, number>>((counts, recipient) => {
    counts[recipient.status] = (counts[recipient.status] ?? 0) + 1;
    return counts;
  }, {});

  useEffect(() => {
    if (!selectedDelivery) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedDelivery(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [selectedDelivery]);

  async function viewDelivery(delivery: DeliveryRow) {
    setSelectedDelivery(delivery);
    setRecipientDetails([]);
    setDetailsError("");
    setDetailsLoading(true);
    recipientPagination.setPage(1);
    try {
      const endpoint = delivery.kind === "api-key"
        ? `/api/campaigns/api-keys/${delivery.api_key_id}/recipients?branch_id=${delivery.branch_id}`
        : `/api/campaigns/${delivery.id}/recipients`;
      const response = await apiRequest<{ items: CampaignRecipientDetail[] }>(
        endpoint,
        "GET",
        undefined,
        token,
      );
      setRecipientDetails(response.items);
    } catch (error) {
      setDetailsError((error as Error).message);
    } finally {
      setDetailsLoading(false);
    }
  }

  async function retryOne(queueId: string) {
    setRetryBusyId(queueId);
    try {
      await apiRequest(`/api/queue/${queueId}/retry`, "POST", undefined, token);
      if (selectedDelivery) await viewDelivery(selectedDelivery);
    } catch (error) {
      setDetailsError((error as Error).message);
    } finally {
      setRetryBusyId(null);
    }
  }

  async function openReassignDialog(delivery: CampaignDeliveryRow) {
    setReassignTarget(delivery);
    setReassignBranchId("");
    setReassignError("");
    setReassignBranchModems({});
    setReassignLoading(true);
    try {
      const candidateBranches = branches.filter((branch) => branch.id !== delivery.branch_id);
      const results = await Promise.all(
        candidateBranches.map((branch) =>
          apiRequest<Modem[]>(`/api/modems?branch_id=${branch.id}`, "GET", undefined, token)
            .then((modems) => [branch.id, modems] as const)
            .catch(() => [branch.id, []] as const),
        ),
      );
      setReassignBranchModems(Object.fromEntries(results));
    } catch (error) {
      setReassignError((error as Error).message);
    } finally {
      setReassignLoading(false);
    }
  }

  async function submitReassign() {
    if (!reassignTarget || !reassignBranchId) return;
    setReassignBusy(true);
    setReassignError("");
    try {
      await apiRequest(
        `/api/queue/campaigns/${reassignTarget.id}/reassign-branch`,
        "POST",
        { target_branch_id: reassignBranchId },
        token,
      );
      setReassignTarget(null);
      if (selectedDelivery?.id === reassignTarget.id) await viewDelivery(selectedDelivery);
    } catch (error) {
      setReassignError((error as Error).message);
    } finally {
      setReassignBusy(false);
    }
  }

  async function retryAllFailed() {
    if (!selectedDelivery) return;
    setRetryAllBusy(true);
    try {
      if (selectedDelivery.kind === "api-key") {
        const failedQueueIds = recipientDetails
          .filter((recipient) => recipient.status === "failed" && recipient.queue_id)
          .map((recipient) => recipient.queue_id!);
        await Promise.all(
          failedQueueIds.map((queueId) => apiRequest(`/api/queue/${queueId}/retry`, "POST", undefined, token)),
        );
      } else {
        await apiRequest(`/api/queue/campaigns/${selectedDelivery.id}/retry-failed`, "POST", undefined, token);
      }
      await viewDelivery(selectedDelivery);
    } catch (error) {
      setDetailsError((error as Error).message);
    } finally {
      setRetryAllBusy(false);
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Campaign deliveries</CardTitle>
          <CardDescription>Select a campaign to review every queued recipient message and its delivery status.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Scheduled</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.pageItems.map((delivery) => (
                <TableRow key={delivery.id}>
                  <TableCell>
                    <p className="font-medium">{delivery.name}</p>
                    {delivery.kind === "api-key" && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {delivery.message_count} API message{delivery.message_count === 1 ? "" : "s"}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={mapStatusToBadge(delivery.status)}>{readableStatus(delivery.status)}</Badge>
                  </TableCell>
                  <TableCell>{delivery.scheduled_at ? formatDate(delivery.scheduled_at) : "-"}</TableCell>
                  <TableCell>{formatDate(delivery.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {isSuperuser && delivery.kind === "campaign" && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void openReassignDialog(delivery)}
                        >
                          <Shuffle className="h-4 w-4" />
                          Reassign
                        </Button>
                      )}
                      <Button type="button" size="sm" variant="outline" onClick={() => void viewDelivery(delivery)}>
                        <Eye className="h-4 w-4" />
                        View
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {deliveryRows.length === 0 && <EmptyRow colSpan={5} message="No campaign deliveries yet." />}
            </TableBody>
          </Table>
          <Pagination
            {...pagination}
            totalItems={deliveryRows.length}
            onPageChange={pagination.setPage}
            onPageSizeChange={pagination.setPageSize}
          />
        </CardContent>
      </Card>

      {selectedDelivery && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close campaign details"
            onClick={() => setSelectedDelivery(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="campaign-details-title"
            className="relative z-10 flex max-h-[90vh] w-full max-w-7xl flex-col animate-slide-up overflow-hidden rounded-xl border bg-card shadow-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b p-6">
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant={mapStatusToBadge(selectedDelivery.status)}>{readableStatus(selectedDelivery.status)}</Badge>
                  <span className="text-xs text-muted-foreground">{formatDate(selectedDelivery.created_at)}</span>
                </div>
                <h2 id="campaign-details-title" className="text-xl font-semibold">{selectedDelivery.name}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {selectedDelivery.kind === "api-key"
                    ? "All SMS requests sent with this API key."
                    : "Recipient messages and delivery results."}
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setSelectedDelivery(null)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <div className="overflow-y-auto p-6">
              {detailsLoading ? (
                <div className="grid min-h-52 place-items-center text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <LoaderCircle className="h-5 w-5 animate-spin" />
                    Loading recipient messages...
                  </div>
                </div>
              ) : detailsError ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                  {detailsError}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {[
                      ["Total", recipientDetails.length, "bg-slate-100 text-slate-700"],
                      ["Sent", deliveryCounts.sent ?? 0, "bg-emerald-100 text-emerald-700"],
                      ["Failed", deliveryCounts.failed ?? 0, "bg-red-100 text-red-700"],
                      ["Pending", deliveryCounts.pending ?? 0, "bg-amber-100 text-amber-700"],
                      ["Sending", deliveryCounts.sending ?? 0, "bg-sky-100 text-sky-700"],
                    ].map(([label, count, className]) => (
                      <div key={String(label)} className={`rounded-lg px-4 py-3 ${className}`}>
                        <p className="text-xs font-medium">{label}</p>
                        <p className="mt-1 text-xl font-semibold">{count}</p>
                      </div>
                    ))}
                  </div>

                  {(deliveryCounts.failed ?? 0) > 0 && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                      <p className="text-sm text-red-900">
                        {deliveryCounts.failed} message{deliveryCounts.failed === 1 ? "" : "s"} failed to send. Resend once the modem is back online.
                      </p>
                      <Button variant="outline" size="sm" disabled={retryAllBusy} onClick={() => void retryAllFailed()}>
                        <RotateCw className="h-4 w-4" />
                        Resend all failed
                      </Button>
                    </div>
                  )}

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Contact</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Message sent</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Attempts</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Sent at</TableHead>
                        <TableHead>Error</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recipientPagination.pageItems.map((recipient) => (
                        <TableRow key={recipient.id}>
                          <TableCell className="font-medium">{recipient.contact_name || "Unlinked contact"}</TableCell>
                          <TableCell className="whitespace-nowrap">{recipient.phone_number}</TableCell>
                          <TableCell className="min-w-72 max-w-xl whitespace-normal">{recipient.message_body}</TableCell>
                          <TableCell>
                            <Badge variant={mapStatusToBadge(recipient.status)}>{readableStatus(recipient.status)}</Badge>
                          </TableCell>
                          <TableCell>{recipient.attempts}</TableCell>
                          <TableCell className="whitespace-nowrap">{formatDate(recipient.created_at ?? undefined)}</TableCell>
                          <TableCell className="whitespace-nowrap">{formatDate(recipient.sent_at ?? undefined)}</TableCell>
                          <TableCell className="max-w-64 whitespace-normal text-muted-foreground">{recipient.error_message || "-"}</TableCell>
                          <TableCell className="text-right">
                            {recipient.status === "failed" && recipient.queue_id && (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={retryBusyId === recipient.queue_id}
                                onClick={() => void retryOne(recipient.queue_id!)}
                              >
                                <RotateCw className="h-4 w-4" />
                                Resend
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                      {recipientDetails.length === 0 && <EmptyRow colSpan={9} message="No recipient messages found." />}
                    </TableBody>
                  </Table>
                  <Pagination
                    {...recipientPagination}
                    totalItems={recipientDetails.length}
                    onPageChange={recipientPagination.setPage}
                    onPageSizeChange={recipientPagination.setPageSize}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {reassignTarget && (
        <div className="fixed inset-0 z-[80] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close reassign dialog"
            onClick={() => setReassignTarget(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="reassign-title"
            className="relative z-10 w-full max-w-md animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 id="reassign-title" className="text-lg font-semibold">Reassign to another modem</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Send &quot;{reassignTarget.name}&quot; through a different branch&apos;s modem instead of waiting for
                  automatic failover. Only pending and failed messages are affected.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setReassignTarget(null)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            {reassignLoading ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Checking modem status across branches...
              </div>
            ) : (
              <div className="space-y-3">
                <label className="block text-sm font-medium">Target branch</label>
                <SelectNative value={reassignBranchId} onChange={(event) => setReassignBranchId(event.target.value)}>
                  <option value="">Select a branch...</option>
                  {branches
                    .filter((branch) => branch.id !== reassignTarget.branch_id)
                    .map((branch) => {
                      const modems = reassignBranchModems[branch.id] ?? [];
                      const onlineCount = modems.filter((modem) => modem.status === "online").length;
                      return (
                        <option key={branch.id} value={branch.id}>
                          {branch.name} — {onlineCount > 0 ? `${onlineCount} modem(s) online` : "no modem online"}
                        </option>
                      );
                    })}
                </SelectNative>
                {reassignError && <p className="text-sm text-destructive">{reassignError}</p>}
                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="ghost" onClick={() => setReassignTarget(null)}>
                    Cancel
                  </Button>
                  <Button type="button" disabled={!reassignBranchId || reassignBusy} onClick={() => void submitReassign()}>
                    {reassignBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Shuffle className="h-4 w-4" />}
                    Reassign
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
