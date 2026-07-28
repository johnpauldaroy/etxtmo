import { FormEvent, useEffect, useState } from "react";

import { apiDownload, apiRequest } from "../api/client";
import {
  Campaign,
  CampaignBatchUploadResult,
  CampaignSubmitResult,
  ContactImportResult,
} from "../pages/types";

type UseCampaignActionsOptions = {
  token: string;
  selectedBranch: string;
  selectedBranchTimezone?: string;
  refreshBranchData: (activeToken: string, branchId: string) => Promise<void>;
  onError: (message: string) => void;
};

type BatchRow = { phone_number: string; message_body: string };
type ContactImportRow = {
  phone_number: string;
  first_name: string;
  last_name: string;
  consented: string;
};

function normalizeHeader(header: string) {
  return header.toLowerCase().replace(/[\s_-]+/g, "");
}

function asTrimmedText(value: unknown) {
  if (value === undefined || value === null) {
    return "";
  }
  return String(value).trim();
}

function getValueByHeader(row: Record<string, unknown>, aliases: string[]) {
  const normalized = new Map<string, string>();
  Object.entries(row).forEach(([header, value]) => normalized.set(normalizeHeader(header), asTrimmedText(value)));
  for (const alias of aliases) {
    const value = normalized.get(alias);
    if (value) {
      return value;
    }
  }
  return "";
}

async function parseBatchRowsFromFile(file: File): Promise<BatchRow[]> {
  const XLSX = await import("xlsx");
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheetName = workbook.SheetNames[0];
  if (!firstSheetName) {
    throw new Error("Spreadsheet is empty");
  }
  const firstSheet = workbook.Sheets[firstSheetName];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(firstSheet, { defval: "" });
  if (rows.length === 0) {
    throw new Error("Spreadsheet has no rows");
  }

  const parsed = rows
    .map((row) => ({
      phone_number: getValueByHeader(row, ["phonenumber", "phone", "number", "mobile", "msisdn"]),
      message_body: getValueByHeader(row, ["message", "messagebody", "text", "sms", "body"]),
    }))
    .filter((row) => row.phone_number && row.message_body);

  if (parsed.length === 0) {
    throw new Error("No valid rows found. Add columns named phone_number and message.");
  }
  return parsed;
}

async function parseContactRowsFromFile(file: File): Promise<{ rows: ContactImportRow[]; invalidRows: number }> {
  const XLSX = await import("xlsx");
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheetName = workbook.SheetNames[0];
  if (!firstSheetName) throw new Error("The contact file is empty");

  const rawRows = XLSX.utils.sheet_to_json<Record<string, unknown>>(workbook.Sheets[firstSheetName], { defval: "" });
  if (rawRows.length === 0) throw new Error("The contact file has no rows");

  let invalidRows = 0;
  const rows = rawRows.flatMap((row) => {
    const phone = getValueByHeader(row, ["phonenumber", "phone", "number", "mobile", "mobilenumber", "msisdn"]);
    if (!phone) {
      invalidRows += 1;
      return [];
    }
    const consentValue = getValueByHeader(row, ["consented", "consent", "optedin"]).toLowerCase();
    return [{
      phone_number: phone,
      first_name: getValueByHeader(row, ["firstname", "givenname", "first"]),
      last_name: getValueByHeader(row, ["lastname", "surname", "familyname", "last"]),
      consented: ["0", "false", "no", "n"].includes(consentValue) ? "false" : "true",
    }];
  });

  if (rows.length === 0) {
    throw new Error("No valid contacts found. Add a phone_number or phone column.");
  }
  return { rows, invalidRows };
}

export function useCampaignActions({
  token,
  selectedBranch,
  selectedBranchTimezone,
  refreshBranchData,
  onError,
}: UseCampaignActionsOptions) {
  const [newPhone, setNewPhone] = useState("");
  const [newContactFirstName, setNewContactFirstName] = useState("");
  const [newContactLastName, setNewContactLastName] = useState("");
  const [contactImportFile, setContactImportFile] = useState<File | null>(null);
  const [contactImportInputKey, setContactImportInputKey] = useState(0);
  const [contactImportSummary, setContactImportSummary] = useState<ContactImportResult | null>(null);
  const [isImportingContacts, setIsImportingContacts] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateBody, setNewTemplateBody] = useState("");
  const [newCampaignName, setNewCampaignName] = useState("");
  const [newCampaignMessage, setNewCampaignMessage] = useState("");
  const [newCampaignScheduledAt, setNewCampaignScheduledAt] = useState("");
  const [selectedCampaignTemplateId, setSelectedCampaignTemplateId] = useState("");
  const [selectedCampaignGroupId, setSelectedCampaignGroupId] = useState("");
  const [campaignSubmitSummary, setCampaignSubmitSummary] = useState<CampaignSubmitResult | null>(null);
  const [isSubmittingCampaign, setIsSubmittingCampaign] = useState(false);
  const [batchCampaignName, setBatchCampaignName] = useState("");
  const [batchUploadFile, setBatchUploadFile] = useState<File | null>(null);
  const [batchUploadInputKey, setBatchUploadInputKey] = useState(0);
  const [batchUploadSummary, setBatchUploadSummary] = useState<CampaignBatchUploadResult | null>(null);
  const [isUploadingBatch, setIsUploadingBatch] = useState(false);

  const [newRuleName, setNewRuleName] = useState("");
  const [newRuleTime, setNewRuleTime] = useState("09:00");
  const [newRuleDaysOfWeek, setNewRuleDaysOfWeek] = useState("1,2,3,4,5");
  const [newRuleMessage, setNewRuleMessage] = useState("");
  const [selectedRuleTemplateId, setSelectedRuleTemplateId] = useState("");

  const [manualOptOutPhone, setManualOptOutPhone] = useState("");
  const [manualOptOutReason, setManualOptOutReason] = useState("");

  useEffect(() => {
    setSelectedCampaignTemplateId("");
    setSelectedCampaignGroupId("");
    setSelectedRuleTemplateId("");
    setCampaignSubmitSummary(null);
    setBatchUploadSummary(null);
  }, [selectedBranch]);

  async function addContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || !newPhone.trim()) {
      return false;
    }
    try {
      await apiRequest(
        "/api/contacts",
        "POST",
        {
          branch_id: selectedBranch,
          phone_number: newPhone.trim(),
          first_name: newContactFirstName.trim() || null,
          last_name: newContactLastName.trim() || null,
          consented: true,
        },
        token,
      );
      setNewPhone("");
      setNewContactFirstName("");
      setNewContactLastName("");
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  async function addTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || !newTemplateName.trim() || !newTemplateBody.trim()) {
      return;
    }
    try {
      await apiRequest(
        "/api/templates",
        "POST",
        {
          branch_id: selectedBranch,
          name: newTemplateName.trim(),
          body: newTemplateBody.trim(),
          is_official: true,
        },
        token,
      );
      setNewTemplateName("");
      setNewTemplateBody("");
      await refreshBranchData(token, selectedBranch);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function deleteContact(contactId: string) {
    if (!selectedBranch) return;
    try {
      await apiRequest(`/api/contacts/${contactId}`, "DELETE", undefined, token);
      await refreshBranchData(token, selectedBranch);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function updateContact(
    contactId: string,
    values: { phone_number: string; first_name: string | null; last_name: string | null },
  ) {
    if (!selectedBranch || !values.phone_number.trim()) return false;
    try {
      await apiRequest(
        `/api/contacts/${contactId}`,
        "PUT",
        {
          phone_number: values.phone_number.trim(),
          first_name: values.first_name?.trim() || null,
          last_name: values.last_name?.trim() || null,
        },
        token,
      );
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  async function importContacts(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || isImportingContacts) return false;
    if (!contactImportFile) {
      onError("Please select a CSV or Excel contact file");
      return false;
    }

    setIsImportingContacts(true);
    try {
      const { rows, invalidRows } = await parseContactRowsFromFile(contactImportFile);
      if (rows.length > 10000) throw new Error("Contact import supports up to 10,000 valid rows per file");

      const XLSX = await import("xlsx");
      const worksheet = XLSX.utils.json_to_sheet(rows, {
        header: ["phone_number", "first_name", "last_name", "consented"],
      });
      const csv = XLSX.utils.sheet_to_csv(worksheet);
      const formData = new FormData();
      formData.append("file", new File([csv], "contacts.csv", { type: "text/csv" }));

      const result = await apiRequest<ContactImportResult>(
        `/api/contacts/import-csv?branch_id=${encodeURIComponent(selectedBranch)}`,
        "POST",
        formData,
        token,
      );
      setContactImportSummary({ inserted: result.inserted, skipped: result.skipped + invalidRows });
      setContactImportFile(null);
      setContactImportInputKey((current) => current + 1);
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    } finally {
      setIsImportingContacts(false);
    }
  }

  async function exportContacts() {
    if (!selectedBranch) return;
    try {
      const { blob, filename } = await apiDownload(
        `/api/contacts/export-csv?branch_id=${encodeURIComponent(selectedBranch)}`,
        token,
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename || "textblast-contacts.csv";
      anchor.click();
      URL.revokeObjectURL(url);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  function updateContactImportFile(file: File | null) {
    setContactImportFile(file);
    setContactImportSummary(null);
  }

  async function deleteTemplate(templateId: string) {
    if (!selectedBranch) return;
    try {
      await apiRequest(`/api/templates/${templateId}`, "DELETE", undefined, token);
      await refreshBranchData(token, selectedBranch);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function updateTemplate(
    templateId: string,
    values: { name: string; body: string; is_official: boolean },
  ) {
    if (!selectedBranch || !values.name.trim() || !values.body.trim()) return false;
    try {
      await apiRequest(
        `/api/templates/${templateId}`,
        "PUT",
        {
          name: values.name.trim(),
          body: values.body.trim(),
          is_official: values.is_official,
        },
        token,
      );
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  async function createAndSubmitCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || !newCampaignName.trim() || !newCampaignMessage.trim() || isSubmittingCampaign) {
      return false;
    }
    if (newCampaignScheduledAt && new Date(newCampaignScheduledAt).getTime() <= Date.now()) {
      onError("Scheduled send time must be in the future");
      return false;
    }
    setIsSubmittingCampaign(true);
    setCampaignSubmitSummary(null);
    try {
      const campaign = await apiRequest<Campaign & { id: string }>(
        "/api/campaigns",
        "POST",
        {
          branch_id: selectedBranch,
          name: newCampaignName.trim(),
          template_id: selectedCampaignTemplateId || null,
          group_id: selectedCampaignGroupId || null,
          message_body: newCampaignMessage.trim(),
          scheduled_at: newCampaignScheduledAt ? new Date(newCampaignScheduledAt).toISOString() : null,
          timezone: selectedBranchTimezone ?? "Asia/Manila",
        },
        token,
      );
      const result = await apiRequest<CampaignSubmitResult>(`/api/campaigns/${campaign.id}/submit`, "POST", {}, token);
      setNewCampaignName("");
      setNewCampaignMessage("");
      setNewCampaignScheduledAt("");
      setSelectedCampaignTemplateId("");
      setSelectedCampaignGroupId("");
      setCampaignSubmitSummary(result);
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    } finally {
      setIsSubmittingCampaign(false);
    }
  }

  async function uploadBatchCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || isUploadingBatch) {
      return false;
    }
    if (!batchUploadFile) {
      onError("Please select an Excel/CSV file first");
      return false;
    }
    setIsUploadingBatch(true);
    try {
      const parsedRows = await parseBatchRowsFromFile(batchUploadFile);
      if (parsedRows.length > 10000) {
        onError("Upload supports up to 10,000 valid rows per file");
        return false;
      }
      const result = await apiRequest<CampaignBatchUploadResult>(
        "/api/campaigns/batch-upload",
        "POST",
        {
          branch_id: selectedBranch,
          name: batchCampaignName.trim() || null,
          timezone: selectedBranchTimezone ?? "Asia/Manila",
          rows: parsedRows,
        },
        token,
      );
      setBatchUploadSummary(result);
      setBatchCampaignName("");
      setBatchUploadFile(null);
      setBatchUploadInputKey((current) => current + 1);
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    } finally {
      setIsUploadingBatch(false);
    }
  }

  async function downloadBatchTemplate() {
    const XLSX = await import("xlsx");
    const worksheet = XLSX.utils.json_to_sheet(
      [
        { phone_number: "+639171234567", message: "Hi Juan, your loan payment is due on July 30." },
        { phone_number: "+639281234567", message: "Hi Maria, your loan payment is due on July 30." },
      ],
      { header: ["phone_number", "message"] },
    );
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Batch");
    XLSX.writeFile(workbook, "textblast-batch-template.xlsx");
  }

  function updateBatchUploadFile(file: File | null) {
    setBatchUploadFile(file);
    setBatchUploadSummary(null);
  }

  async function createRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || !newRuleName.trim() || (!selectedRuleTemplateId && !newRuleMessage.trim())) {
      return;
    }
    const [hours, minutes] = newRuleTime.split(":").map(Number);
    const minute = (hours * 60) + minutes;
    if (!Number.isInteger(hours) || !Number.isInteger(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      onError("Select a valid schedule time");
      return;
    }
    try {
      await apiRequest(
        "/api/rules",
        "POST",
        {
          branch_id: selectedBranch,
          name: newRuleName.trim(),
          minute_of_day: minute,
          days_of_week: newRuleDaysOfWeek.trim() || "0,1,2,3,4,5,6",
          timezone: selectedBranchTimezone ?? "Asia/Manila",
          template_id: selectedRuleTemplateId || null,
          message_body: selectedRuleTemplateId ? null : newRuleMessage.trim(),
          is_active: true,
        },
        token,
      );
      setNewRuleName("");
      setNewRuleMessage("");
      setSelectedRuleTemplateId("");
      await refreshBranchData(token, selectedBranch);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function disableRule(ruleId: string) {
    if (!selectedBranch) {
      return;
    }
    try {
      await apiRequest(`/api/rules/${ruleId}`, "DELETE", undefined, token);
      await refreshBranchData(token, selectedBranch);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function enableRule(ruleId: string) {
    if (!selectedBranch) {
      return;
    }
    try {
      await apiRequest(`/api/rules/${ruleId}/enable`, "POST", {}, token);
      await refreshBranchData(token, selectedBranch);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function updateRule(
    ruleId: string,
    values: {
      name: string;
      minuteOfDay: number;
      daysOfWeek: string;
      templateId: string;
      messageBody: string;
    },
  ) {
    if (!selectedBranch || !values.name.trim() || (!values.templateId && !values.messageBody.trim())) {
      return false;
    }
    try {
      await apiRequest(
        `/api/rules/${ruleId}`,
        "PUT",
        {
          name: values.name.trim(),
          minute_of_day: values.minuteOfDay,
          days_of_week: values.daysOfWeek.trim() || "0,1,2,3,4,5,6",
          template_id: values.templateId || null,
          message_body: values.templateId ? null : values.messageBody.trim(),
        },
        token,
      );
      await refreshBranchData(token, selectedBranch);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  async function addManualOptOut(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranch || !manualOptOutPhone.trim()) {
      return;
    }
    try {
      await apiRequest(
        "/api/contacts/opt-outs",
        "POST",
        {
          branch_id: selectedBranch,
          phone_number: manualOptOutPhone.trim(),
          reason: manualOptOutReason.trim() || null,
        },
        token,
      );
      setManualOptOutPhone("");
      setManualOptOutReason("");
      await refreshBranchData(token, selectedBranch);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function retryMessage(queueId: string) {
    if (!selectedBranch) {
      return;
    }
    try {
      await apiRequest(`/api/queue/${queueId}/retry`, "POST", {}, token);
      await refreshBranchData(token, selectedBranch);
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return {
    newPhone,
    setNewPhone,
    newContactFirstName,
    setNewContactFirstName,
    newContactLastName,
    setNewContactLastName,
    contactImportInputKey,
    contactImportSummary,
    isImportingContacts,
    setContactImportFile: updateContactImportFile,
    newTemplateName,
    setNewTemplateName,
    newTemplateBody,
    setNewTemplateBody,
    newCampaignName,
    setNewCampaignName,
    newCampaignMessage,
    setNewCampaignMessage,
    newCampaignScheduledAt,
    setNewCampaignScheduledAt,
    selectedCampaignTemplateId,
    setSelectedCampaignTemplateId,
    selectedCampaignGroupId,
    setSelectedCampaignGroupId,
    campaignSubmitSummary,
    isSubmittingCampaign,
    batchCampaignName,
    setBatchCampaignName,
    batchUploadFile,
    setBatchUploadFile: updateBatchUploadFile,
    batchUploadInputKey,
    batchUploadSummary,
    isUploadingBatch,
    newRuleName,
    setNewRuleName,
    newRuleTime,
    setNewRuleTime,
    newRuleDaysOfWeek,
    setNewRuleDaysOfWeek,
    newRuleMessage,
    setNewRuleMessage,
    selectedRuleTemplateId,
    setSelectedRuleTemplateId,
    manualOptOutPhone,
    setManualOptOutPhone,
    manualOptOutReason,
    setManualOptOutReason,
    addContact,
    importContacts,
    exportContacts,
    deleteContact,
    updateContact,
    addTemplate,
    deleteTemplate,
    updateTemplate,
    createAndSubmitCampaign,
    uploadBatchCampaign,
    downloadBatchTemplate,
    createRule,
    disableRule,
    enableRule,
    updateRule,
    addManualOptOut,
    retryMessage,
  };
}
