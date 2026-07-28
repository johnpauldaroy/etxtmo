import { FormEvent, useEffect, useMemo, useState } from "react";
import { LoaderCircle, Pencil, Plus, Search, Trash2, Users, X } from "lucide-react";

import { apiRequest } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { EmptyRow, formatDate, Pagination, usePagination } from "./common";
import { Contact, ContactGroup, ContactGroupDetail } from "./types";

type GroupsPageProps = {
  groups: ContactGroup[];
  contacts: Contact[];
  token: string;
  branchId: string;
  onRefresh: () => Promise<void>;
  initialGroupId?: string | null;
  onInitialGroupHandled?: () => void;
  onExternalEditorClose?: () => void;
};

function contactName(contact: Contact) {
  return [contact.first_name, contact.last_name].filter(Boolean).join(" ") || "Unnamed contact";
}

export function GroupsPage({
  groups,
  contacts,
  token,
  branchId,
  onRefresh,
  initialGroupId,
  onInitialGroupHandled,
  onExternalEditorClose,
}: GroupsPageProps) {
  const pagination = usePagination(groups);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<ContactGroup | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedContactIds, setSelectedContactIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [returnAfterClose, setReturnAfterClose] = useState(false);

  const filteredContacts = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return contacts;
    return contacts.filter((contact) =>
      `${contactName(contact)} ${contact.phone_number}`.toLowerCase().includes(query),
    );
  }, [contacts, search]);

  useEffect(() => {
    if (!initialGroupId) return;
    const group = groups.find((item) => item.id === initialGroupId);
    if (!group) return;
    void openManageDialog(group, true);
    onInitialGroupHandled?.();
  }, [groups, initialGroupId]);

  function closeDialog() {
    setDialogOpen(false);
    if (returnAfterClose) {
      setReturnAfterClose(false);
      onExternalEditorClose?.();
    }
  }

  function openCreateDialog() {
    setReturnAfterClose(false);
    setEditingGroup(null);
    setName("");
    setDescription("");
    setSelectedContactIds(new Set());
    setSearch("");
    setError("");
    setDialogOpen(true);
  }

  async function openManageDialog(group: ContactGroup, returnToPreviousPage = false) {
    setReturnAfterClose(returnToPreviousPage);
    setEditingGroup(group);
    setName(group.name);
    setDescription(group.description ?? "");
    setSelectedContactIds(new Set());
    setSearch("");
    setError("");
    setDialogOpen(true);
    setLoadingMembers(true);
    try {
      const detail = await apiRequest<ContactGroupDetail>(
        `/api/contacts/groups/${group.id}`,
        "GET",
        undefined,
        token,
      );
      setSelectedContactIds(new Set(detail.members.map((member) => member.id)));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoadingMembers(false);
    }
  }

  function toggleContact(contactId: string) {
    setSelectedContactIds((current) => {
      const next = new Set(current);
      if (next.has(contactId)) next.delete(contactId);
      else next.add(contactId);
      return next;
    });
  }

  function toggleFilteredContacts() {
    setSelectedContactIds((current) => {
      const next = new Set(current);
      const allSelected = filteredContacts.length > 0 && filteredContacts.every((contact) => next.has(contact.id));
      filteredContacts.forEach((contact) => {
        if (allSelected) next.delete(contact.id);
        else next.add(contact.id);
      });
      return next;
    });
  }

  async function saveGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!branchId || saving) return;
    setSaving(true);
    setError("");
    try {
      let groupId = editingGroup?.id;
      if (!groupId) {
        const created = await apiRequest<ContactGroup>(
          "/api/contacts/groups",
          "POST",
          {
            branch_id: branchId,
            name: name.trim(),
            description: description.trim() || null,
          },
          token,
        );
        groupId = created.id;
      }
      await apiRequest<ContactGroupDetail>(
        `/api/contacts/groups/${groupId}/members`,
        "PUT",
        { contact_ids: Array.from(selectedContactIds) },
        token,
      );
      await onRefresh();
      closeDialog();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteGroup(group: ContactGroup) {
    if (!window.confirm(`Delete contact group "${group.name}"?`)) return;
    try {
      await apiRequest<void>(`/api/contacts/groups/${group.id}`, "DELETE", undefined, token);
      await onRefresh();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Contact groups</CardTitle>
            <CardDescription>Create reusable recipient lists for campaigns and schedules.</CardDescription>
          </div>
          <Button type="button" onClick={openCreateDialog}>
            <Plus className="h-4 w-4" />
            Create group
          </Button>
        </CardHeader>
        <CardContent>
          {error && !dialogOpen && (
            <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Members</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.pageItems.map((group) => (
                <TableRow key={group.id}>
                  <TableCell className="font-medium">{group.name}</TableCell>
                  <TableCell className="max-w-md truncate text-muted-foreground">{group.description || "-"}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      <Users className="mr-1 h-3.5 w-3.5" />
                      {group.member_count}
                    </Badge>
                  </TableCell>
                  <TableCell>{formatDate(group.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button type="button" size="sm" variant="outline" onClick={() => void openManageDialog(group)}>
                        <Pencil className="h-4 w-4" />
                        Manage
                      </Button>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label={`Delete ${group.name}`}
                        onClick={() => void deleteGroup(group)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {groups.length === 0 && <EmptyRow colSpan={5} message="No contact groups yet." />}
            </TableBody>
          </Table>
          <Pagination
            {...pagination}
            totalItems={groups.length}
            onPageChange={pagination.setPage}
            onPageSizeChange={pagination.setPageSize}
          />
        </CardContent>
      </Card>

      {dialogOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close contact group dialog"
            onClick={closeDialog}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="contact-group-dialog-title"
            className="relative z-10 flex max-h-[82vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border bg-card shadow-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b p-4">
              <div>
                <h2 id="contact-group-dialog-title" className="text-lg font-semibold">
                  {editingGroup ? "Manage contact group" : "Create contact group"}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {editingGroup ? "Update the contacts included in this group." : "Name the group and choose its contacts."}
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={closeDialog}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form className="flex min-h-0 flex-1 flex-col" onSubmit={saveGroup}>
              <div className="space-y-4 overflow-y-auto p-4">
                {error && (
                  <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label htmlFor="group-name" className="text-sm font-medium">Group name</label>
                    <Input
                      id="group-name"
                      required
                      disabled={Boolean(editingGroup)}
                      placeholder="e.g. Loan reminders"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="group-description" className="text-sm font-medium">Description</label>
                    <Textarea
                      id="group-description"
                      disabled={Boolean(editingGroup)}
                      className="min-h-10"
                      placeholder="Optional group description"
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                    <div>
                      <p className="text-sm font-medium">Contacts</p>
                      <p className="text-xs text-muted-foreground">{selectedContactIds.size} selected</p>
                    </div>
                    <div className="relative w-full sm:max-w-[14rem]">
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        className="pl-9"
                        placeholder="Search name or phone"
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                      />
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-lg border">
                    <div className="flex items-center gap-3 border-b bg-slate-50 px-3 py-2 text-sm">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300 accent-primary"
                        checked={filteredContacts.length > 0 && filteredContacts.every((contact) => selectedContactIds.has(contact.id))}
                        onChange={toggleFilteredContacts}
                        aria-label="Select all visible contacts"
                      />
                      <span className="font-medium">Select all visible</span>
                      <span className="ml-auto text-xs text-muted-foreground">{filteredContacts.length} contacts</span>
                    </div>
                    <div className="max-h-56 divide-y overflow-y-auto">
                      {loadingMembers ? (
                        <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
                          <LoaderCircle className="h-4 w-4 animate-spin" />
                          Loading members...
                        </div>
                      ) : filteredContacts.length === 0 ? (
                        <p className="p-8 text-center text-sm text-muted-foreground">No contacts match your search.</p>
                      ) : (
                        filteredContacts.map((contact) => (
                          <label key={contact.id} className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-slate-50">
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-slate-300 accent-primary"
                              checked={selectedContactIds.has(contact.id)}
                              onChange={() => toggleContact(contact.id)}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium">{contactName(contact)}</span>
                              <span className="block text-xs text-muted-foreground">{contact.phone_number}</span>
                            </span>
                            {!contact.consented && <Badge variant="warning">Not consented</Badge>}
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t bg-card p-3">
                <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
                <Button type="submit" disabled={saving || loadingMembers}>
                  {saving && <LoaderCircle className="h-4 w-4 animate-spin" />}
                  {saving ? "Saving..." : editingGroup ? "Save members" : "Create group"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
