import { FormEvent, useEffect, useState } from "react";
import { Pencil, Plus, X } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { EmptyRow, Pagination, usePagination } from "./common";
import { Branch, User, UserUpdateInput } from "./types";

type AdminUsersPageProps = {
  users: User[];
  branches: Branch[];
  newUserEmail: string;
  newUserUsername: string;
  newUserFullName: string;
  newUserPassword: string;
  newUserIsSuperuser: string;
  newUserBranchId: string;
  onNewUserEmailChange: (value: string) => void;
  onNewUserUsernameChange: (value: string) => void;
  onNewUserFullNameChange: (value: string) => void;
  onNewUserPasswordChange: (value: string) => void;
  onNewUserIsSuperuserChange: (value: string) => void;
  onNewUserBranchChange: (value: string) => void;
  onCreateUser: (event: FormEvent<HTMLFormElement>) => Promise<boolean>;
  onUpdateUser: (userId: string, values: UserUpdateInput) => Promise<boolean>;
};

export function AdminUsersPage({
  users,
  branches,
  newUserEmail,
  newUserUsername,
  newUserFullName,
  newUserPassword,
  newUserIsSuperuser,
  newUserBranchId,
  onNewUserEmailChange,
  onNewUserUsernameChange,
  onNewUserFullNameChange,
  onNewUserPasswordChange,
  onNewUserIsSuperuserChange,
  onNewUserBranchChange,
  onCreateUser,
  onUpdateUser,
}: AdminUsersPageProps) {
  const pagination = usePagination(users);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editEmail, setEditEmail] = useState("");
  const [editUsername, setEditUsername] = useState("");
  const [editFullName, setEditFullName] = useState("");
  const [editPassword, setEditPassword] = useState("");
  const [editIsSuperuser, setEditIsSuperuser] = useState(false);
  const [editIsActive, setEditIsActive] = useState(true);
  const [editBusy, setEditBusy] = useState(false);
  const isStandardUser = newUserIsSuperuser !== "true";

  useEffect(() => {
    if (!dialogOpen && !editingUser) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDialogOpen(false);
        setEditingUser(null);
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [dialogOpen, editingUser]);

  function openEditDialog(user: User) {
    setEditEmail(user.email ?? "");
    setEditUsername(user.username);
    setEditFullName(user.full_name);
    setEditPassword("");
    setEditIsSuperuser(user.is_superuser);
    setEditIsActive(user.is_active !== false);
    setEditingUser(user);
  }

  return (
    <Card>
      <CardHeader className="flex-col items-start justify-between gap-4 space-y-0 sm:flex-row sm:items-center">
        <div className="space-y-1.5">
          <CardTitle>Admin Users</CardTitle>
          <CardDescription>Create user accounts and manage access level for onboarding.</CardDescription>
        </div>
        <Button type="button" onClick={() => setDialogOpen(true)}>
          <Plus className="h-4 w-4" />
          Add user
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead>Full Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pagination.pageItems.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.username}</TableCell>
                <TableCell>{user.full_name}</TableCell>
                <TableCell>{user.email ?? "-"}</TableCell>
                <TableCell>
                  <Badge variant={user.is_superuser ? "warning" : "secondary"}>
                    {user.is_superuser ? "Superuser" : "Standard"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={user.is_active === false ? "destructive" : "success"}>
                    {user.is_active === false ? "Inactive" : "Active"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button type="button" size="sm" variant="outline" onClick={() => openEditDialog(user)}>
                    <Pencil className="h-4 w-4" />
                    Edit
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {users.length === 0 && <EmptyRow colSpan={6} message="No users found." />}
          </TableBody>
        </Table>
        <Pagination {...pagination} totalItems={users.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
      </CardContent>

      {dialogOpen && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close create user dialog"
            onClick={() => setDialogOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-user-title"
            className="relative z-10 w-full max-w-2xl animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="create-user-title" className="text-xl font-semibold">Create user</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Create an account and assign its initial branch access.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setDialogOpen(false)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                const created = await onCreateUser(event);
                if (created) setDialogOpen(false);
              }}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  Full name
                  <Input
                    required
                    autoFocus
                    placeholder="Juan Dela Cruz"
                    value={newUserFullName}
                    onChange={(event) => onNewUserFullNameChange(event.target.value)}
                  />
                </label>
                <label className="space-y-2 text-sm font-medium">
                  Username
                  <Input
                    required
                    placeholder="juan.delacruz"
                    value={newUserUsername}
                    onChange={(event) => onNewUserUsernameChange(event.target.value)}
                  />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  Email
                  <Input
                    type="email"
                    required
                    autoComplete="off"
                    placeholder="juan@example.com"
                    value={newUserEmail}
                    onChange={(event) => onNewUserEmailChange(event.target.value)}
                  />
                </label>
                <label className="space-y-2 text-sm font-medium">
                  Temporary password
                  <Input
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="At least 8 characters"
                    value={newUserPassword}
                    onChange={(event) => onNewUserPasswordChange(event.target.value)}
                  />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  Access level
                  <SelectNative
                    value={newUserIsSuperuser}
                    onChange={(event) => {
                      const value = event.target.value;
                      onNewUserIsSuperuserChange(value);
                      if (value === "false" && !newUserBranchId && branches[0]) {
                        onNewUserBranchChange(branches[0].id);
                      }
                    }}
                  >
                    <option value="false">Standard user</option>
                    <option value="true">Superuser</option>
                  </SelectNative>
                </label>
                <label className="space-y-2 text-sm font-medium">
                  Branch {isStandardUser ? "" : "(optional)"}
                  <SelectNative
                    required={isStandardUser}
                    value={newUserBranchId}
                    onChange={(event) => onNewUserBranchChange(event.target.value)}
                  >
                    {!isStandardUser && <option value="">No branch assignment</option>}
                    {branches.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.code} — {branch.name}
                      </option>
                    ))}
                  </SelectNative>
                </label>
              </div>
              <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-muted-foreground">
                Standard users can access only assigned branches. Superusers have system-wide access even without a branch assignment.
              </p>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button type="submit">Create user</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingUser && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close edit user dialog"
            onClick={() => setEditingUser(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-user-title"
            className="relative z-10 w-full max-w-2xl animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="edit-user-title" className="text-xl font-semibold">Edit account</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Update profile details, access level, account status, or password.
                </p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setEditingUser(null)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                setEditBusy(true);
                const updated = await onUpdateUser(editingUser.id, {
                  email: editEmail.trim(),
                  username: editUsername.trim(),
                  full_name: editFullName.trim(),
                  is_active: editIsActive,
                  is_superuser: editIsSuperuser,
                  password: editPassword || null,
                });
                setEditBusy(false);
                if (updated) setEditingUser(null);
              }}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  Full name
                  <Input
                    required
                    autoFocus
                    value={editFullName}
                    onChange={(event) => setEditFullName(event.target.value)}
                  />
                </label>
                <label className="space-y-2 text-sm font-medium">
                  Username
                  <Input
                    required
                    value={editUsername}
                    onChange={(event) => setEditUsername(event.target.value)}
                  />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  Email
                  <Input
                    type="email"
                    required
                    value={editEmail}
                    onChange={(event) => setEditEmail(event.target.value)}
                  />
                </label>
                <label className="space-y-2 text-sm font-medium">
                  New password (optional)
                  <Input
                    type="password"
                    minLength={4}
                    autoComplete="new-password"
                    placeholder="Leave blank to keep current password"
                    value={editPassword}
                    onChange={(event) => setEditPassword(event.target.value)}
                  />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  Access level
                  <SelectNative
                    value={String(editIsSuperuser)}
                    onChange={(event) => setEditIsSuperuser(event.target.value === "true")}
                  >
                    <option value="false">Standard user</option>
                    <option value="true">Superuser</option>
                  </SelectNative>
                </label>
                <label className="space-y-2 text-sm font-medium">
                  Account status
                  <SelectNative
                    value={String(editIsActive)}
                    onChange={(event) => setEditIsActive(event.target.value === "true")}
                  >
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </SelectNative>
                </label>
              </div>
              <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-muted-foreground">
                Existing branch assignments are preserved. Assign a branch in Admin Access before changing an unassigned superuser to a standard user.
              </p>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" disabled={editBusy} onClick={() => setEditingUser(null)}>Cancel</Button>
                <Button type="submit" disabled={editBusy}>
                  {editBusy ? "Saving..." : "Save changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Card>
  );
}
