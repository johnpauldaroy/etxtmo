import { FormEvent, useEffect, useState } from "react";
import { Plus, X } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { EmptyRow, Pagination, usePagination } from "./common";
import { Branch } from "./types";

type AdminBranchesPageProps = {
  branches: Branch[];
  newBranchCode: string;
  newBranchName: string;
  newBranchTimezone: string;
  onNewBranchCodeChange: (value: string) => void;
  onNewBranchNameChange: (value: string) => void;
  onNewBranchTimezoneChange: (value: string) => void;
  onCreateBranch: (event: FormEvent<HTMLFormElement>) => void;
};

export function AdminBranchesPage({
  branches,
  newBranchCode,
  newBranchName,
  newBranchTimezone,
  onNewBranchCodeChange,
  onNewBranchNameChange,
  onNewBranchTimezoneChange,
  onCreateBranch,
}: AdminBranchesPageProps) {
  const pagination = usePagination(branches);
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  useEffect(() => {
    if (!isCreateOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsCreateOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [isCreateOpen]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
          <div>
            <CardTitle>Branch Directory</CardTitle>
            <CardDescription>All branches available in the system and their current status.</CardDescription>
          </div>
          <Button type="button" onClick={() => setIsCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Add branch
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Timezone</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.pageItems.map((branch) => (
                <TableRow key={branch.id}>
                  <TableCell className="font-medium">{branch.code}</TableCell>
                  <TableCell>{branch.name}</TableCell>
                  <TableCell>{branch.timezone}</TableCell>
                  <TableCell>
                    <Badge variant={branch.is_active === false ? "destructive" : "success"}>
                      {branch.is_active === false ? "Inactive" : "Active"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {branches.length === 0 && <EmptyRow colSpan={4} message="No branches found." />}
            </TableBody>
          </Table>
          <Pagination {...pagination} totalItems={branches.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
        </CardContent>
      </Card>

      {isCreateOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close create branch dialog"
            onClick={() => setIsCreateOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-branch-title"
            className="relative z-10 w-full max-w-lg animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="create-branch-title" className="text-xl font-semibold">Create Branch</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Add a new branch so users, templates, and campaigns can be onboarded immediately.
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
                onCreateBranch(event);
                setIsCreateOpen(false);
              }}
            >
              <div className="space-y-2">
                <label htmlFor="branch-code" className="text-sm font-medium">Code</label>
                <Input
                  id="branch-code"
                  required
                  autoFocus
                  placeholder="e.g. 003"
                  value={newBranchCode}
                  onChange={(event) => onNewBranchCodeChange(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="branch-name" className="text-sm font-medium">Branch name</label>
                <Input
                  id="branch-name"
                  required
                  placeholder="e.g. Culasi Branch"
                  value={newBranchName}
                  onChange={(event) => onNewBranchNameChange(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="branch-timezone" className="text-sm font-medium">Timezone (IANA)</label>
                <Input
                  id="branch-timezone"
                  required
                  placeholder="Asia/Manila"
                  value={newBranchTimezone}
                  onChange={(event) => onNewBranchTimezoneChange(event.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                <Button type="submit">Create branch</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
