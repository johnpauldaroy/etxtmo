import { useEffect, useState } from "react";
import { Eye, LoaderCircle, RotateCw, X } from "lucide-react";

import { apiRequest } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { EmptyRow, formatDate, mapStatusToBadge, Pagination, usePagination } from "./common";
import { Campaign, CampaignRecipientDetail } from "./types";

type CampaignDeliveryPanelProps = {
  campaigns: Campaign[];
  token: string;
};

const readableStatus = (status: string) => {
  if (status === "approved") return "Scheduled";
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
};

export function CampaignDeliveryPanel({ campaigns, token }: CampaignDeliveryPanelProps) {
  const pagination = usePagination(campaigns);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [recipientDetails, setRecipientDetails] = useState<CampaignRecipientDetail[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");
  const [retryBusyId, setRetryBusyId] = useState<string | null>(null);
  const [retryAllBusy, setRetryAllBusy] = useState(false);
  const recipientPagination = usePagination(recipientDetails);
  const deliveryCounts = recipientDetails.reduce<Record<string, number>>((counts, recipient) => {
    counts[recipient.status] = (counts[recipient.status] ?? 0) + 1;
    return counts;
  }, {});

  useEffect(() => {
    if (!selectedCampaign) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedCampaign(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [selectedCampaign]);

  async function viewCampaign(campaign: Campaign) {
    setSelectedCampaign(campaign);
    setRecipientDetails([]);
    setDetailsError("");
    setDetailsLoading(true);
    recipientPagination.setPage(1);
    try {
      const response = await apiRequest<{ items: CampaignRecipientDetail[] }>(
        `/api/campaigns/${campaign.id}/recipients`,
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
      if (selectedCampaign) await viewCampaign(selectedCampaign);
    } catch (error) {
      setDetailsError((error as Error).message);
    } finally {
      setRetryBusyId(null);
    }
  }

  async function retryAllFailed() {
    if (!selectedCampaign) return;
    setRetryAllBusy(true);
    try {
      await apiRequest(`/api/queue/campaigns/${selectedCampaign.id}/retry-failed`, "POST", undefined, token);
      await viewCampaign(selectedCampaign);
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
              {pagination.pageItems.map((campaign) => (
                <TableRow key={campaign.id}>
                  <TableCell className="font-medium">{campaign.name}</TableCell>
                  <TableCell>
                    <Badge variant={mapStatusToBadge(campaign.status)}>{readableStatus(campaign.status)}</Badge>
                  </TableCell>
                  <TableCell>{campaign.scheduled_at ? formatDate(campaign.scheduled_at) : "-"}</TableCell>
                  <TableCell>{formatDate(campaign.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <Button type="button" size="sm" variant="outline" onClick={() => void viewCampaign(campaign)}>
                      <Eye className="h-4 w-4" />
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {campaigns.length === 0 && <EmptyRow colSpan={5} message="No campaign deliveries yet." />}
            </TableBody>
          </Table>
          <Pagination
            {...pagination}
            totalItems={campaigns.length}
            onPageChange={pagination.setPage}
            onPageSizeChange={pagination.setPageSize}
          />
        </CardContent>
      </Card>

      {selectedCampaign && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close campaign details"
            onClick={() => setSelectedCampaign(null)}
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
                  <Badge variant={mapStatusToBadge(selectedCampaign.status)}>{readableStatus(selectedCampaign.status)}</Badge>
                  <span className="text-xs text-muted-foreground">{formatDate(selectedCampaign.created_at)}</span>
                </div>
                <h2 id="campaign-details-title" className="text-xl font-semibold">{selectedCampaign.name}</h2>
                <p className="mt-1 text-sm text-muted-foreground">Recipient messages and delivery results.</p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setSelectedCampaign(null)}>
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
                      {recipientDetails.length === 0 && <EmptyRow colSpan={8} message="This campaign has no recipient messages." />}
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
    </>
  );
}
