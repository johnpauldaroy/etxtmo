import { FormEvent } from "react";
import { CalendarClock, CheckCircle2, Download, FileSpreadsheet, Info, Megaphone, Pencil, Send, Users } from "lucide-react";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Textarea } from "../components/ui/textarea";
import { CampaignBatchUploadResult, CampaignSubmitResult, ContactGroup, Template } from "./types";
import {
  appendMessagePlaceholder,
  getSmsMeta,
  MessagePlaceholderButtons,
} from "./common";

type CampaignsPageProps = {
  templates: Template[];
  groups: ContactGroup[];
  eligibleContactsCount: number;
  newCampaignName: string;
  newCampaignMessage: string;
  newCampaignScheduledAt: string;
  selectedCampaignTemplateId: string;
  selectedCampaignGroupId: string;
  campaignSubmitSummary: CampaignSubmitResult | null;
  isSubmittingCampaign: boolean;
  batchCampaignName: string;
  batchUploadInputKey: number;
  batchUploadSummary: CampaignBatchUploadResult | null;
  isUploadingBatch: boolean;
  onCampaignNameChange: (value: string) => void;
  onCampaignMessageChange: (value: string) => void;
  onCampaignScheduledAtChange: (value: string) => void;
  onCampaignTemplateChange: (value: string) => void;
  onCampaignGroupChange: (value: string) => void;
  onBatchCampaignNameChange: (value: string) => void;
  onBatchFileChange: (file: File | null) => void;
  onManageGroup: (groupId: string) => void;
  onCreateAndSubmitCampaign: (event: FormEvent<HTMLFormElement>) => Promise<boolean>;
  onUploadBatchCampaign: (event: FormEvent<HTMLFormElement>) => Promise<boolean>;
  onDownloadBatchTemplate: () => void;
};

const readableStatus = (status: string) => {
  if (status === "approved") return "Scheduled";
  if (status === "sent") return "Submitted";
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
};

export function CampaignsPage({
  templates,
  groups,
  eligibleContactsCount,
  newCampaignName,
  newCampaignMessage,
  newCampaignScheduledAt,
  selectedCampaignTemplateId,
  selectedCampaignGroupId,
  campaignSubmitSummary,
  isSubmittingCampaign,
  batchCampaignName,
  batchUploadInputKey,
  batchUploadSummary,
  isUploadingBatch,
  onCampaignNameChange,
  onCampaignMessageChange,
  onCampaignScheduledAtChange,
  onCampaignTemplateChange,
  onCampaignGroupChange,
  onBatchCampaignNameChange,
  onBatchFileChange,
  onManageGroup,
  onCreateAndSubmitCampaign,
  onUploadBatchCampaign,
  onDownloadBatchTemplate,
}: CampaignsPageProps) {
  const messageMeta = getSmsMeta(newCampaignMessage);
  const selectedGroup = groups.find((group) => group.id === selectedCampaignGroupId);
  const audienceCount = selectedGroup
    ? (selectedGroup.eligible_member_count ?? selectedGroup.member_count)
    : eligibleContactsCount;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,.75fr)]">
        <Card>
          <CardHeader className="border-b bg-slate-50/60">
            <div className="flex items-start gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-orange-100 text-primary">
                <Megaphone className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Create campaign</CardTitle>
                <CardDescription className="mt-1">
                  Send one message to all eligible contacts or a selected contact group.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <form className="space-y-5" onSubmit={onCreateAndSubmitCampaign}>
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="space-y-2">
                  <label htmlFor="campaign-name" className="text-sm font-medium">Campaign name</label>
                  <Input
                    id="campaign-name"
                    required
                    placeholder="e.g. Membership reminder"
                    value={newCampaignName}
                    onChange={(event) => onCampaignNameChange(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="campaign-template" className="text-sm font-medium">Message template</label>
                  <SelectNative
                    id="campaign-template"
                    value={selectedCampaignTemplateId}
                    onChange={(event) => {
                      const templateId = event.target.value;
                      onCampaignTemplateChange(templateId);
                      const template = templates.find((item) => item.id === templateId);
                      if (template) onCampaignMessageChange(template.body);
                    }}
                  >
                    <option value="">Write a custom message</option>
                    {templates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}{template.is_official ? " (Official)" : ""}
                      </option>
                    ))}
                  </SelectNative>
                </div>
                <div className="space-y-2">
                  <label htmlFor="campaign-group" className="text-sm font-medium">Recipient group</label>
                  <SelectNative
                    id="campaign-group"
                    value={selectedCampaignGroupId}
                    onChange={(event) => onCampaignGroupChange(event.target.value)}
                  >
                    <option value="">All eligible contacts ({eligibleContactsCount})</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name} ({group.eligible_member_count ?? group.member_count} eligible)
                      </option>
                    ))}
                  </SelectNative>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor="campaign-message" className="text-sm font-medium">Message</label>
                  <span className="text-xs text-muted-foreground">
                    {messageMeta.length} characters · {messageMeta.encoding} · {messageMeta.segments} SMS segment
                    {messageMeta.segments === 1 ? "" : "s"}
                    {messageMeta.segments > 0 && ` (${messageMeta.perSegmentLimit}/segment)`}
                  </span>
                </div>
                <Textarea
                  id="campaign-message"
                  required
                  className="min-h-36"
                  placeholder="Select a template or write your message here..."
                  value={newCampaignMessage}
                  onChange={(event) => onCampaignMessageChange(event.target.value)}
                />
                <MessagePlaceholderButtons
                  onInsert={(placeholder) => onCampaignMessageChange(appendMessagePlaceholder(newCampaignMessage, placeholder))}
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="campaign-scheduled-at" className="text-sm font-medium">
                  Send time <span className="font-normal text-muted-foreground">(optional)</span>
                </label>
                <div className="relative">
                  <CalendarClock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="campaign-scheduled-at"
                    type="datetime-local"
                    className="pl-9"
                    value={newCampaignScheduledAt}
                    onChange={(event) => onCampaignScheduledAtChange(event.target.value)}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Leave blank to queue immediately. Times use the active branch's timezone.
                </p>
              </div>

              <div className="rounded-xl border bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <Users className="h-5 w-5 text-slate-500" />
                    <div>
                      <p className="text-xs text-muted-foreground">
                        {selectedGroup ? selectedGroup.name : "All eligible contacts"}
                      </p>
                      <p className="font-semibold">{audienceCount.toLocaleString()} contact{audienceCount === 1 ? "" : "s"}</p>
                    </div>
                  </div>
                  {selectedGroup && (
                    <Button type="button" size="sm" variant="outline" onClick={() => onManageGroup(selectedGroup.id)}>
                      <Pencil className="h-4 w-4" />
                      Edit contacts
                    </Button>
                  )}
                </div>
              </div>

              {audienceCount === 0 && (
                <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  <Info className="mt-0.5 h-4 w-4 shrink-0" />
                  {selectedGroup
                    ? "This group has no eligible contacts. Add consented contacts to the group before submitting."
                    : "Add at least one eligible contact before submitting this campaign."}
                </div>
              )}

              {campaignSubmitSummary && (
                <div className="flex gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Campaign submitted for <strong>{campaignSubmitSummary.recipients}</strong> recipients. Status:{" "}
                    <strong>{readableStatus(campaignSubmitSummary.status)}</strong>
                    {campaignSubmitSummary.queued > 0 && <> · {campaignSubmitSummary.queued} queued</>}.
                  </span>
                </div>
              )}

              <div className="flex justify-end border-t pt-5">
                <Button type="submit" disabled={isSubmittingCampaign || audienceCount === 0}>
                  <Send className="h-4 w-4" />
                  {isSubmittingCampaign
                    ? "Submitting..."
                    : newCampaignScheduledAt
                      ? "Schedule campaign"
                      : "Create and queue"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b bg-slate-50/60">
            <div className="flex items-start gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-sky-100 text-sky-700">
                <FileSpreadsheet className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Personalized batch</CardTitle>
                <CardDescription className="mt-1">Send a different message to each uploaded number.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <form className="space-y-4" onSubmit={onUploadBatchCampaign}>
              <div className="space-y-2">
                <label htmlFor="batch-campaign-name" className="text-sm font-medium">Campaign name</label>
                <Input
                  id="batch-campaign-name"
                  placeholder="Optional"
                  value={batchCampaignName}
                  onChange={(event) => onBatchCampaignNameChange(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor="batch-campaign-file" className="text-sm font-medium">Excel or CSV file</label>
                  <button
                    type="button"
                    onClick={onDownloadBatchTemplate}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download template
                  </button>
                </div>
                <Input
                  id="batch-campaign-file"
                  key={batchUploadInputKey}
                  type="file"
                  required
                  accept=".xlsx,.xls,.csv"
                  onChange={(event) => onBatchFileChange(event.target.files?.[0] ?? null)}
                />
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-muted-foreground">
                Required columns: <code>phone_number</code> and <code>message</code>. Maximum 10,000 valid rows.
                Duplicate and opted-out numbers are skipped.
              </div>
              {batchUploadSummary && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                  <p className="font-medium">{readableStatus(batchUploadSummary.status)}</p>
                  <p className="mt-1 text-xs">
                    {batchUploadSummary.inserted} accepted · {batchUploadSummary.skipped} skipped · {batchUploadSummary.queued} queued
                  </p>
                </div>
              )}
              <Button className="w-full" type="submit" disabled={isUploadingBatch}>
                <Send className="h-4 w-4" />
                {isUploadingBatch ? "Uploading..." : "Upload and submit"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/*
      Campaign delivery history now lives in Message Queue.
      <Card className="order-1">
        <CardHeader>
          <CardTitle>Campaigns</CardTitle>
          <CardDescription>Select a campaign to review every recipient message and its delivery status.</CardDescription>
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
              {campaigns.length === 0 && <EmptyRow colSpan={5} message="No campaigns created yet." />}
            </TableBody>
          </Table>
          <Pagination {...pagination} totalItems={campaigns.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
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
                        </TableRow>
                      ))}
                      {recipientDetails.length === 0 && <EmptyRow colSpan={7} message="This campaign has no recipient messages." />}
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
      */}
    </div>
  );
}
