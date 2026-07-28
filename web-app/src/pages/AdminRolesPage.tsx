import { FormEvent } from "react";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { EmptyRow, Pagination, usePagination } from "./common";
import { Role } from "./types";

type AdminRolesPageProps = {
  roles: Role[];
  newRoleName: string;
  newRoleDescription: string;
  onNewRoleNameChange: (value: string) => void;
  onNewRoleDescriptionChange: (value: string) => void;
  onCreateRole: (event: FormEvent<HTMLFormElement>) => void;
};

export function AdminRolesPage({
  roles,
  newRoleName,
  newRoleDescription,
  onNewRoleNameChange,
  onNewRoleDescriptionChange,
  onCreateRole,
}: AdminRolesPageProps) {
  const pagination = usePagination(roles);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Admin Roles</CardTitle>
        <CardDescription>Define branch role labels to be used in user branch assignments.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-[1fr_2fr_auto]" onSubmit={onCreateRole}>
          <Input required placeholder="Role name (e.g. BRANCH_MANAGER)" value={newRoleName} onChange={(event) => onNewRoleNameChange(event.target.value)} />
          <Input
            placeholder="Role description"
            value={newRoleDescription}
            onChange={(event) => onNewRoleDescriptionChange(event.target.value)}
          />
          <Button type="submit">Create role</Button>
        </form>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pagination.pageItems.map((role) => (
              <TableRow key={role.id}>
                <TableCell>{role.id}</TableCell>
                <TableCell className="font-medium">{role.name}</TableCell>
                <TableCell>{role.description || "-"}</TableCell>
              </TableRow>
            ))}
            {roles.length === 0 && <EmptyRow colSpan={3} message="No roles found." />}
          </TableBody>
        </Table>
        <Pagination {...pagination} totalItems={roles.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
      </CardContent>
    </Card>
  );
}
