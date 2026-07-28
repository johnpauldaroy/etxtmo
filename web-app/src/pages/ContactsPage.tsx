import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, Download, FileDown, FileSpreadsheet, Pencil, Plus, Trash2, Upload, X } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "../components/ui/table";
import { Branch, Contact, ContactImportResult } from "./types";
import { EmptyRow, Pagination, usePagination } from "./common";

type ContactsPageProps = {
  contacts: Contact[];
  newPhone: string;
  newContactFirstName: string;
  newContactLastName: string;
  onNewPhoneChange: (value: string) => void;
  onNewContactFirstNameChange: (value: string) => void;
  onNewContactLastNameChange: (value: string) => void;
  onAddContact: (event: FormEvent<HTMLFormElement>) => Promise<boolean>;
  onDeleteContact: (contactId: string) => void;
  onEditContact: (
    contactId: string,
    values: { phone_number: string; first_name: string | null; last_name: string | null },
  ) => Promise<boolean>;
  contactImportInputKey: number;
  contactImportSummary: ContactImportResult | null;
  isImportingContacts: boolean;
  onContactImportFileChange: (file: File | null) => void;
  onImportContacts: (event: FormEvent<HTMLFormElement>) => Promise<boolean>;
  onExportContacts: () => void;
  branchLabel: string;
  branches: Branch[];
  selectedBranch: string;
  onBranchChange: (branchId: string) => void;
};

export function ContactsPage({
  contacts,
  newPhone,
  newContactFirstName,
  newContactLastName,
  onNewPhoneChange,
  onNewContactFirstNameChange,
  onNewContactLastNameChange,
  onAddContact,
  onDeleteContact,
  onEditContact,
  contactImportInputKey,
  contactImportSummary,
  isImportingContacts,
  onContactImportFileChange,
  onImportContacts,
  onExportContacts,
  branchLabel,
  branches,
  selectedBranch,
  onBranchChange,
}: ContactsPageProps) {
  const pagination = usePagination(contacts);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [editPhone, setEditPhone] = useState("");
  const [editFirstName, setEditFirstName] = useState("");
  const [editLastName, setEditLastName] = useState("");

  useEffect(() => {
    if (!addDialogOpen && !importDialogOpen && !editingContact) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setAddDialogOpen(false);
        setImportDialogOpen(false);
        setEditingContact(null);
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [addDialogOpen, importDialogOpen, editingContact]);

  function openEditDialog(contact: Contact) {
    setEditingContact(contact);
    setEditPhone(contact.phone_number);
    setEditFirstName(contact.first_name ?? "");
    setEditLastName(contact.last_name ?? "");
  }

  function downloadTemplate() {
    const csv = `phone_number,first_name,last_name,branch\r\n+639171234567,Juan,Dela Cruz,"${branchLabel}"\r\n`;
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "textblast-contacts-template.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card>
      <CardHeader className="flex-col items-start justify-between gap-4 space-y-0 sm:flex-row">
        <div className="space-y-1.5">
          <CardTitle>Contacts</CardTitle>
          <CardDescription>Add recipients and manage the active branch contact list.</CardDescription>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
          <Button type="button" onClick={() => setAddDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Add contact
          </Button>
          <Button type="button" variant="outline" onClick={() => setImportDialogOpen(true)}>
            <Upload className="h-4 w-4" />
            Import
          </Button>
          <Button type="button" variant="outline" onClick={onExportContacts}>
            <FileDown className="h-4 w-4" />
            Export
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="hidden">
          <form onSubmit={onImportContacts}>
            <Input
              key={contactImportInputKey}
              required
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) => onContactImportFileChange(event.target.files?.[0] ?? null)}
            />
            <Button type="submit" disabled={isImportingContacts}>
              <Upload className="h-4 w-4" />
              {isImportingContacts ? "Importing…" : "Import contacts"}
            </Button>
          </form>
          <p className="mt-3 text-xs text-muted-foreground">
            Supported headings: <code>phone_number</code>, <code>phone</code>, <code>mobile</code>,{" "}
            <code>first_name</code>, <code>last_name</code>, and <code>branch</code>. Uploaded contacts are assigned to the active branch.
          </p>

          {contactImportSummary && (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              Imported <strong>{contactImportSummary.inserted}</strong> contacts; skipped{" "}
              <strong>{contactImportSummary.skipped}</strong> duplicate or invalid rows.
            </div>
          )}
        </div>

        {contactImportSummary && (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Imported <strong>{contactImportSummary.inserted}</strong> contacts; skipped{" "}
            <strong>{contactImportSummary.skipped}</strong> duplicate or invalid rows.
          </div>
        )}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Phone</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Branch</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pagination.pageItems.map((contact) => (
              <TableRow key={contact.id}>
                <TableCell className="font-medium">{contact.phone_number}</TableCell>
                <TableCell>{`${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim() || "-"}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{branchLabel || "Active branch"}</Badge>
                </TableCell>
                <TableCell className="space-x-1 text-right">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground hover:text-primary"
                    aria-label={`Edit ${contact.phone_number}`}
                    onClick={() => openEditDialog(contact)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    aria-label={`Delete ${contact.phone_number}`}
                    onClick={() => {
                      if (window.confirm(`Delete contact ${contact.phone_number}?`)) onDeleteContact(contact.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {contacts.length === 0 && <EmptyRow colSpan={4} message="No contacts yet." />}
          </TableBody>
        </Table>
        <Pagination {...pagination} totalItems={contacts.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
      </CardContent>

      {addDialogOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close add contact dialog"
            onClick={() => setAddDialogOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-contact-title"
            className="relative z-10 w-full max-w-lg animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="add-contact-title" className="text-xl font-semibold">Add contact</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Add a recipient to {branchLabel || "the active branch"}.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setAddDialogOpen(false)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                const created = await onAddContact(event);
                if (created) setAddDialogOpen(false);
              }}
            >
              <div className="space-y-2">
                <label htmlFor="contact-phone" className="text-sm font-medium">Phone number</label>
                <Input
                  id="contact-phone"
                  required
                  autoFocus
                  inputMode="tel"
                  placeholder="+639171234567"
                  value={newPhone}
                  onChange={(event) => onNewPhoneChange(event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="contact-first-name" className="text-sm font-medium">First name</label>
                  <Input
                    id="contact-first-name"
                    placeholder="Juan"
                    value={newContactFirstName}
                    onChange={(event) => onNewContactFirstNameChange(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="contact-last-name" className="text-sm font-medium">Last name</label>
                  <Input
                    id="contact-last-name"
                    placeholder="Dela Cruz"
                    value={newContactLastName}
                    onChange={(event) => onNewContactLastNameChange(event.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="contact-branch" className="text-sm font-medium">Branch</label>
                <SelectNative
                  id="contact-branch"
                  required
                  value={selectedBranch}
                  onChange={(event) => onBranchChange(event.target.value)}
                >
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.code} — {branch.name}
                    </option>
                  ))}
                </SelectNative>
              </div>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button>
                <Button type="submit">Save contact</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {importDialogOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close import contacts dialog"
            onClick={() => setImportDialogOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="import-contacts-title"
            className="relative z-10 w-full max-w-xl animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div className="flex gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-orange-100 text-primary">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
                <div>
                  <h2 id="import-contacts-title" className="text-xl font-semibold">Import bulk contacts</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Upload CSV or Excel into {branchLabel || "the active branch"}.
                  </p>
                </div>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setImportDialogOpen(false)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                const imported = await onImportContacts(event);
                if (imported) setImportDialogOpen(false);
              }}
            >
              <div className="space-y-2">
                <label htmlFor="contact-import-file" className="text-sm font-medium">Contact file</label>
                <Input
                  id="contact-import-file"
                  key={contactImportInputKey}
                  required
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(event) => onContactImportFileChange(event.target.files?.[0] ?? null)}
                />
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-muted-foreground">
                Required: <code>phone_number</code>, <code>phone</code>, or <code>mobile</code>. Optional:{" "}
                <code>first_name</code>, <code>last_name</code>, and <code>branch</code>. Duplicate or blank numbers are skipped.
              </div>
              <div className="flex flex-col-reverse justify-between gap-2 border-t pt-4 sm:flex-row">
                <Button type="button" variant="ghost" onClick={downloadTemplate}>
                  <Download className="h-4 w-4" />
                  Download template
                </Button>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setImportDialogOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={isImportingContacts}>
                    <Upload className="h-4 w-4" />
                    {isImportingContacts ? "Importing..." : "Import contacts"}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingContact && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close edit contact dialog"
            onClick={() => setEditingContact(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-contact-title"
            className="relative z-10 w-full max-w-lg animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="edit-contact-title" className="text-xl font-semibold">Edit contact</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Update this recipient in {branchLabel || "the active branch"}.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setEditingContact(null)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const updated = await onEditContact(editingContact.id, {
                  phone_number: editPhone,
                  first_name: editFirstName || null,
                  last_name: editLastName || null,
                });
                if (updated) setEditingContact(null);
              }}
            >
              <div className="space-y-2">
                <label htmlFor="edit-contact-phone" className="text-sm font-medium">Phone number</label>
                <Input
                  id="edit-contact-phone"
                  required
                  autoFocus
                  inputMode="tel"
                  value={editPhone}
                  onChange={(event) => setEditPhone(event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="edit-contact-first-name" className="text-sm font-medium">First name</label>
                  <Input
                    id="edit-contact-first-name"
                    value={editFirstName}
                    onChange={(event) => setEditFirstName(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label htmlFor="edit-contact-last-name" className="text-sm font-medium">Last name</label>
                  <Input
                    id="edit-contact-last-name"
                    value={editLastName}
                    onChange={(event) => setEditLastName(event.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="edit-contact-branch" className="text-sm font-medium">Branch</label>
                <Input id="edit-contact-branch" value={branchLabel || "Active branch"} disabled />
              </div>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setEditingContact(null)}>Cancel</Button>
                <Button type="submit">Save changes</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Card>
  );
}
