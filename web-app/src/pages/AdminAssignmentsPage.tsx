import { FormEvent, useMemo } from "react";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Branch, BranchAssignmentUser, Role, User } from "./types";
import { EmptyRow, Pagination, usePagination } from "./common";

type AdminAssignmentsPageProps = {
  branches: Branch[];
  users: User[];
  roles: Role[];
  branchUsers: BranchAssignmentUser[];
  assignmentBranchId: string;
  assignUserId: string;
  assignBranchId: string;
  assignRoleId: string;
  onAssignmentBranchChange: (value: string) => void;
  onAssignUserChange: (value: string) => void;
  onAssignBranchChange: (value: string) => void;
  onAssignRoleChange: (value: string) => void;
  onAssignUserBranch: (event: FormEvent<HTMLFormElement>) => void;
};

export function AdminAssignmentsPage({
  branches,
  users,
  roles,
  branchUsers,
  assignmentBranchId,
  assignUserId,
  assignBranchId,
  assignRoleId,
  onAssignmentBranchChange,
  onAssignUserChange,
  onAssignBranchChange,
  onAssignRoleChange,
  onAssignUserBranch,
}: AdminAssignmentsPageProps) {
  const roleNames = useMemo(() => {
    const values = new Map<number, string>();
    roles.forEach((role) => values.set(role.id, role.name));
    return values;
  }, [roles]);

  const activeBranch = useMemo(
    () => branches.find((branch) => branch.id === assignmentBranchId),
    [branches, assignmentBranchId],
  );
  const pagination = usePagination(branchUsers);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Branch Assignment</CardTitle>
          <CardDescription>Assign users to branches and optionally set a branch role in one step.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 xl:grid-cols-[1.3fr_1fr_1fr_auto]" onSubmit={onAssignUserBranch}>
            <SelectNative required value={assignUserId} onChange={(event) => onAssignUserChange(event.target.value)}>
              <option value="">Select user</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.username} ({user.email ?? user.full_name})
                </option>
              ))}
            </SelectNative>
            <SelectNative required value={assignBranchId} onChange={(event) => onAssignBranchChange(event.target.value)}>
              <option value="">Select branch</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.code} - {branch.name}
                </option>
              ))}
            </SelectNative>
            <SelectNative value={assignRoleId} onChange={(event) => onAssignRoleChange(event.target.value)}>
              <option value="">No branch role</option>
              {roles.map((role) => (
                <option key={role.id} value={String(role.id)}>
                  {role.name}
                </option>
              ))}
            </SelectNative>
            <Button type="submit">Assign</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Branch User Access</CardTitle>
          <CardDescription>Current assignments for the selected branch.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <SelectNative value={assignmentBranchId} onChange={(event) => onAssignmentBranchChange(event.target.value)}>
              <option value="">Select branch</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.code} - {branch.name}
                </option>
              ))}
            </SelectNative>
            {activeBranch && <div className="rounded-md bg-muted/60 px-3 py-2 text-sm text-muted-foreground">{activeBranch.timezone}</div>}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.pageItems.map((assignment) => (
                <TableRow key={assignment.user_id}>
                  <TableCell className="font-medium">{assignment.username}</TableCell>
                  <TableCell>{assignment.email}</TableCell>
                  <TableCell>
                    {assignment.role_id === null
                      ? "No branch role"
                      : (roleNames.get(assignment.role_id) ?? `Role #${assignment.role_id}`)}
                  </TableCell>
                </TableRow>
              ))}
              {branchUsers.length === 0 && (
                <EmptyRow colSpan={3} message="No users assigned to this branch yet." />
              )}
            </TableBody>
          </Table>
          <Pagination
            {...pagination}
            totalItems={branchUsers.length}
            onPageChange={pagination.setPage}
            onPageSizeChange={pagination.setPageSize}
          />
        </CardContent>
      </Card>
    </div>
  );
}
