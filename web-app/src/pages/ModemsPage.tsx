import { FormEvent, useEffect, useMemo, useState } from "react";
import { Activity, Plus, Save, ShieldCheck, Trash2, TriangleAlert, X } from "lucide-react";

import { apiRequest } from "../api/client";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "../components/ui/table";
import { Branch, FailoverStatus, Modem } from "./types";
import { EmptyRow, formatDate, mapStatusToBadge, Pagination, usePagination } from "./common";

type ModemsPageProps = {
  modems: Modem[];
  failoverStatus: FailoverStatus | null;
  branches: Branch[];
  selectedBranch: string;
  token: string;
  isSuperuser: boolean;
  onRefresh: () => Promise<void>;
};

export function ModemsPage({
  modems,
  failoverStatus,
  branches,
  selectedBranch,
  token,
  isSuperuser,
  onRefresh,
}: ModemsPageProps) {
  const pagination = usePagination(modems);
  const [enabled, setEnabled] = useState(false);
  const [offlineAfter, setOfflineAfter] = useState(90);
  const [failoverDelay, setFailoverDelay] = useState(60);
  const [claimTimeout, setClaimTimeout] = useState(120);
  const [backupBranch, setBackupBranch] = useState("");
  const [priority, setPriority] = useState(1);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const [isAddModemOpen, setIsAddModemOpen] = useState(false);
  const [newModemBranch, setNewModemBranch] = useState(selectedBranch);
  const [newModemName, setNewModemName] = useState("");
  const [newModemNode, setNewModemNode] = useState("");
  const [newModemPort, setNewModemPort] = useState("");
  const [newModemImei, setNewModemImei] = useState("");
  const [modemError, setModemError] = useState("");

  useEffect(() => {
    if (!failoverStatus) return;
    setEnabled(failoverStatus.policy.enabled);
    setOfflineAfter(failoverStatus.policy.offline_after_seconds);
    setFailoverDelay(failoverStatus.policy.failover_delay_seconds);
    setClaimTimeout(failoverStatus.policy.claim_timeout_seconds);
  }, [failoverStatus]);

  useEffect(() => {
    if (!isAddModemOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsAddModemOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [isAddModemOpen]);

  function openAddModem() {
    setNewModemBranch(selectedBranch);
    setNewModemName("");
    setNewModemNode("");
    setNewModemPort("");
    setNewModemImei("");
    setModemError("");
    setIsAddModemOpen(true);
  }

  async function createModem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setModemError("");
    try {
      await apiRequest("/api/modems", "POST", {
        branch_id: newModemBranch,
        name: newModemName,
        node_name: newModemNode,
        port: newModemPort || null,
        imei: newModemImei || null,
      }, token);
      await onRefresh();
      setIsAddModemOpen(false);
      setNotice("Modem registered.");
    } catch (error) {
      setModemError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const backupOptions = useMemo(
    () => branches.filter((branch) => branch.id !== selectedBranch && !failoverStatus?.routes.some((route) => route.backup_branch_id === branch.id)),
    [branches, failoverStatus?.routes, selectedBranch],
  );

  async function savePolicy() {
    setBusy(true);
    setNotice("");
    try {
      await apiRequest(`/api/failover/policy/${selectedBranch}`, "PUT", {
        branch_id: selectedBranch,
        enabled,
        offline_after_seconds: offlineAfter,
        failover_delay_seconds: failoverDelay,
        claim_timeout_seconds: claimTimeout,
      }, token);
      await onRefresh();
      setNotice("Failover policy saved.");
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function recoverStale() {
    setBusy(true);
    setNotice("");
    try {
      const result = await apiRequest<{ recovered: number }>(`/api/failover/${selectedBranch}/recover-stale`, "POST", {}, token);
      await onRefresh();
      setNotice(`${result.recovered} stale delivery ${result.recovered === 1 ? "was" : "were"} moved to failed for review.`);
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addRoute() {
    if (!backupBranch) return;
    setBusy(true);
    setNotice("");
    try {
      await apiRequest("/api/failover/routes", "POST", {
        source_branch_id: selectedBranch,
        backup_branch_id: backupBranch,
        priority,
        enabled: true,
      }, token);
      setBackupBranch("");
      await onRefresh();
      setNotice("Backup branch added.");
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeRoute(routeId: string) {
    setBusy(true);
    setNotice("");
    try {
      await apiRequest(`/api/failover/routes/${routeId}`, "DELETE", undefined, token);
      await onRefresh();
      setNotice("Backup route removed.");
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 p-5">
            <div className={`rounded-xl p-3 ${failoverStatus?.local_modems_healthy ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Local modem health</p>
              <p className="font-semibold">{failoverStatus?.local_modems_healthy ? `${failoverStatus.healthy_local_modems} healthy` : "No healthy modem"}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-5">
            <div className={`rounded-xl p-3 ${failoverStatus?.failover_active ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
              {failoverStatus?.failover_active ? <TriangleAlert className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Routing mode</p>
              <p className="font-semibold">{failoverStatus?.failover_active ? "Backup available" : "Local first"}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-muted-foreground">Active backup deliveries</p>
            <p className="mt-1 text-2xl font-semibold">{failoverStatus?.failover_messages ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cross-branch failover</CardTitle>
          <CardDescription>Use approved branch modems only when every local modem is unhealthy. The recipient will see the backup SIM number.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {!isSuperuser && <p className="text-sm text-muted-foreground">Only a system administrator can change failover routing.</p>}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1.3fr_1fr_1fr_1fr_auto] xl:items-end">
            <label className="flex h-10 items-center gap-3 rounded-md border bg-slate-50 px-3 text-sm font-medium">
              <input type="checkbox" checked={enabled} disabled={!isSuperuser} onChange={(event) => setEnabled(event.target.checked)} />
              Enable automatic failover
            </label>
            <label className="space-y-1 text-sm font-medium">
              Offline after (seconds)
              <Input type="number" min={30} max={3600} value={offlineAfter} disabled={!isSuperuser} onChange={(event) => setOfflineAfter(Number(event.target.value))} />
            </label>
            <label className="space-y-1 text-sm font-medium">
              Failover delay (seconds)
              <Input type="number" min={0} max={86400} value={failoverDelay} disabled={!isSuperuser} onChange={(event) => setFailoverDelay(Number(event.target.value))} />
            </label>
            <label className="space-y-1 text-sm font-medium">
              Stuck delivery after (seconds)
              <Input type="number" min={30} max={3600} value={claimTimeout} disabled={!isSuperuser} onChange={(event) => setClaimTimeout(Number(event.target.value))} />
            </label>
            <Button disabled={!isSuperuser || busy} onClick={() => void savePolicy()}><Save className="h-4 w-4" />Save policy</Button>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-sm text-amber-900">Stale deliveries are marked for manual review, never automatically resent, to prevent duplicate SMS.</p>
            <Button variant="outline" size="sm" disabled={!isSuperuser || busy} onClick={() => void recoverStale()}>Review stale deliveries</Button>
          </div>

          <div className="border-t pt-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="font-semibold">Backup priority</h3>
                <p className="text-sm text-muted-foreground">The first healthy branch in priority order receives failover work.</p>
              </div>
            </div>
            <div className="mb-4 grid gap-3 md:grid-cols-[1fr_140px_auto]">
              <SelectNative value={backupBranch} disabled={!isSuperuser || busy} onChange={(event) => setBackupBranch(event.target.value)}>
                <option value="">Select backup branch</option>
                {backupOptions.map((branch) => <option key={branch.id} value={branch.id}>{branch.code} — {branch.name}</option>)}
              </SelectNative>
              <Input type="number" min={1} max={100} value={priority} disabled={!isSuperuser || busy} onChange={(event) => setPriority(Number(event.target.value))} />
              <Button variant="outline" disabled={!isSuperuser || busy || !backupBranch} onClick={() => void addRoute()}><Plus className="h-4 w-4" />Add backup</Button>
            </div>
            <div className="space-y-2">
              {failoverStatus?.routes.map((route) => (
                <div key={route.id} className="flex items-center justify-between rounded-lg border bg-slate-50 px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Badge variant="outline">Priority {route.priority}</Badge>
                    <span className="font-medium">{route.backup_branch_code} — {route.backup_branch_name}</span>
                  </div>
                  {isSuperuser && <Button size="icon" variant="ghost" disabled={busy} aria-label="Remove backup route" onClick={() => void removeRoute(route.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button>}
                </div>
              ))}
              {!failoverStatus?.routes.length && <p className="rounded-lg border border-dashed p-5 text-center text-sm text-muted-foreground">No backup branches configured.</p>}
            </div>
          </div>
          {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
          <div>
            <CardTitle>Registered Modems</CardTitle>
            <CardDescription>Current modem inventory and connectivity state.</CardDescription>
          </div>
          <Button type="button" onClick={openAddModem}>
            <Plus className="h-4 w-4" />
            Add modem
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Node</TableHead><TableHead>Status</TableHead><TableHead>Last seen</TableHead></TableRow></TableHeader>
            <TableBody>
              {pagination.pageItems.map((modem) => <TableRow key={modem.id}><TableCell className="font-medium">{modem.name}</TableCell><TableCell>{modem.node_name}</TableCell><TableCell><Badge variant={mapStatusToBadge(modem.status)}>{modem.status}</Badge></TableCell><TableCell>{formatDate(modem.last_seen_at)}</TableCell></TableRow>)}
              {modems.length === 0 && <EmptyRow colSpan={4} message="No registered modems." />}
            </TableBody>
          </Table>
          <Pagination {...pagination} totalItems={modems.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
        </CardContent>
      </Card>

      {isAddModemOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close add modem dialog"
            onClick={() => setIsAddModemOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-modem-title"
            className="relative z-10 w-full max-w-lg animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="add-modem-title" className="text-xl font-semibold">Register Modem</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Pre-provision a modem before it comes online. If the IMEI matches what branch-agent later reports, this entry updates in place instead of duplicating.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setIsAddModemOpen(false)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form className="space-y-4" onSubmit={(event) => void createModem(event)}>
              <div className="space-y-2">
                <label htmlFor="modem-branch" className="text-sm font-medium">Branch</label>
                <SelectNative
                  id="modem-branch"
                  required
                  value={newModemBranch}
                  onChange={(event) => setNewModemBranch(event.target.value)}
                >
                  <option value="">Select branch</option>
                  {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.code} — {branch.name}</option>)}
                </SelectNative>
              </div>
              <div className="space-y-2">
                <label htmlFor="modem-name" className="text-sm font-medium">Modem name</label>
                <Input
                  id="modem-name"
                  required
                  autoFocus
                  placeholder="e.g. modem-001"
                  value={newModemName}
                  onChange={(event) => setNewModemName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="modem-node" className="text-sm font-medium">Node name</label>
                <Input
                  id="modem-node"
                  required
                  placeholder="e.g. branch-001-node-01"
                  value={newModemNode}
                  onChange={(event) => setNewModemNode(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="modem-port" className="text-sm font-medium">COM port (optional)</label>
                <Input
                  id="modem-port"
                  placeholder="e.g. COM11"
                  value={newModemPort}
                  onChange={(event) => setNewModemPort(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="modem-imei" className="text-sm font-medium">IMEI (optional)</label>
                <Input
                  id="modem-imei"
                  placeholder="Used to match this entry with branch-agent's report"
                  value={newModemImei}
                  onChange={(event) => setNewModemImei(event.target.value)}
                />
              </div>
              {modemError && <p className="text-sm text-destructive">{modemError}</p>}
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setIsAddModemOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={busy || !newModemBranch}>Register modem</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
