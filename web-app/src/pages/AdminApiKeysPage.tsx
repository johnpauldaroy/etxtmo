import { useEffect, useState } from "react";
import { Check, Copy, KeyRound, Plus, Trash2, X } from "lucide-react";

import { apiRequest } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { EmptyRow, formatDate, Pagination, usePagination } from "./common";
import { ApiKey, ApiKeyCreated, Branch } from "./types";

type AdminApiKeysPageProps = {
  branches: Branch[];
  token: string;
};

export function AdminApiKeysPage({ branches, token }: AdminApiKeysPageProps) {
  const [selectedBranchId, setSelectedBranchId] = useState(branches[0]?.id ?? "");
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedPrefixId, setCopiedPrefixId] = useState<string | null>(null);

  const pagination = usePagination(keys);

  useEffect(() => {
    if (!selectedBranchId && branches[0]) setSelectedBranchId(branches[0].id);
  }, [branches, selectedBranchId]);

  async function refreshKeys() {
    if (!selectedBranchId) return;
    setIsLoading(true);
    setError("");
    try {
      const rows = await apiRequest<ApiKey[]>(`/api/admin/api-keys?branch_id=${selectedBranchId}`, "GET", undefined, token);
      setKeys(rows);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBranchId]);

  useEffect(() => {
    if (!isCreateOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsCreateOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [isCreateOpen]);

  async function createKey() {
    if (!selectedBranchId || !newKeyLabel.trim() || isCreating) return;
    setIsCreating(true);
    setError("");
    try {
      const created = await apiRequest<ApiKeyCreated>(
        "/api/admin/api-keys",
        "POST",
        { branch_id: selectedBranchId, label: newKeyLabel.trim() },
        token,
      );
      setIsCreateOpen(false);
      setNewKeyLabel("");
      setCreatedKey(created);
      setCopied(false);
      await refreshKeys();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsCreating(false);
    }
  }

  async function revokeKey(keyId: string, label: string) {
    if (!window.confirm(`Revoke API key "${label}"? Any integration using it will stop working immediately.`)) return;
    try {
      await apiRequest(`/api/admin/api-keys/${keyId}`, "DELETE", undefined, token);
      await refreshKeys();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function copyKey() {
    if (!createdKey) return;
    try {
      await navigator.clipboard.writeText(createdKey.api_key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  async function copyKeyPrefix(keyId: string, prefix: string) {
    try {
      await navigator.clipboard.writeText(prefix);
      setCopiedPrefixId(keyId);
      window.setTimeout(() => setCopiedPrefixId((current) => (current === keyId ? null : current)), 1500);
    } catch {
      setCopiedPrefixId(null);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
          <div>
            <CardTitle>SMS Gateway API Keys</CardTitle>
            <CardDescription>
              Let external systems send SMS through this branch via <code>POST /api/v1/sms/send</code> using an{" "}
              <code>X-API-Key</code> header.
            </CardDescription>
          </div>
          <Button type="button" onClick={() => setIsCreateOpen(true)} disabled={!selectedBranchId}>
            <Plus className="h-4 w-4" />
            New API key
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-sm space-y-2">
            <label htmlFor="api-key-branch" className="text-sm font-medium">Branch</label>
            <SelectNative id="api-key-branch" value={selectedBranchId} onChange={(event) => setSelectedBranchId(event.target.value)}>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.code} - {branch.name}
                </option>
              ))}
            </SelectNative>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Label</TableHead>
                <TableHead>Key</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last used</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.pageItems.map((key) => (
                <TableRow key={key.id}>
                  <TableCell className="font-medium">{key.label}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs text-muted-foreground">{key.key_prefix}...</span>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 text-muted-foreground hover:text-foreground"
                        title="Copy key prefix (the full secret is only shown once, at creation)"
                        aria-label={`Copy key prefix for ${key.label}`}
                        onClick={() => void copyKeyPrefix(key.id, key.key_prefix)}
                      >
                        {copiedPrefixId === key.id ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={key.is_active ? "success" : "secondary"}>{key.is_active ? "active" : "revoked"}</Badge>
                  </TableCell>
                  <TableCell>{key.last_used_at ? formatDate(key.last_used_at) : "Never"}</TableCell>
                  <TableCell>{formatDate(key.created_at)}</TableCell>
                  <TableCell className="text-right">
                    {key.is_active && (
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        aria-label={`Revoke ${key.label}`}
                        onClick={() => void revokeKey(key.id, key.label)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && keys.length === 0 && <EmptyRow colSpan={6} message="No API keys for this branch yet." />}
            </TableBody>
          </Table>
          <Pagination {...pagination} totalItems={keys.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
        </CardContent>
      </Card>

      {isCreateOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close create API key dialog"
            onClick={() => setIsCreateOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-api-key-title"
            className="relative z-10 w-full max-w-lg animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="create-api-key-title" className="text-xl font-semibold">Create API Key</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Generates a key scoped to the selected branch. The full key is shown once after creation.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setIsCreateOpen(false)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void createKey();
              }}
            >
              <div className="space-y-2">
                <label htmlFor="api-key-label" className="text-sm font-medium">Label</label>
                <Input
                  id="api-key-label"
                  required
                  autoFocus
                  placeholder="e.g. Loan system integration"
                  value={newKeyLabel}
                  onChange={(event) => setNewKeyLabel(event.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={isCreating}>{isCreating ? "Creating..." : "Create key"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {createdKey && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm" />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="created-api-key-title"
            className="relative z-10 w-full max-w-lg animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-4 flex items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-emerald-100 text-emerald-700">
                <KeyRound className="h-5 w-5" />
              </div>
              <div>
                <h2 id="created-api-key-title" className="text-xl font-semibold">API key created</h2>
                <p className="text-sm text-muted-foreground">Copy it now — it will not be shown again.</p>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-lg border bg-slate-50 p-3">
              <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-sm">{createdKey.api_key}</code>
              <Button type="button" size="icon" variant="outline" className="h-8 w-8 shrink-0" onClick={() => void copyKey()} aria-label="Copy API key">
                {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>

            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-muted-foreground">
              Use it as: <code>X-API-Key: {createdKey.api_key.slice(0, 12)}...</code> on requests to{" "}
              <code>POST /api/v1/sms/send</code>.
            </div>

            <div className="flex justify-end border-t pt-4 mt-4">
              <Button type="button" onClick={() => setCreatedKey(null)}>Done</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
