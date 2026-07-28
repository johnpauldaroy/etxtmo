import { FormEvent, useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { AdminApiKeysPage } from "./AdminApiKeysPage";
import { AdminRolesPage } from "./AdminRolesPage";
import { AdminAssignmentsPage } from "./AdminAssignmentsPage";
import { Branch, BranchAssignmentUser, Role, User } from "./types";

type AdminAccessPageProps = {
  roles: Role[];
  newRoleName: string;
  newRoleDescription: string;
  onNewRoleNameChange: (value: string) => void;
  onNewRoleDescriptionChange: (value: string) => void;
  onCreateRole: (event: FormEvent<HTMLFormElement>) => void;
  branches: Branch[];
  users: User[];
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
  token: string;
};

export function AdminAccessPage(props: AdminAccessPageProps) {
  const [tab, setTab] = useState("roles");

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="roles">Roles</TabsTrigger>
        <TabsTrigger value="assignments">Branch Assignment</TabsTrigger>
        <TabsTrigger value="api-keys">API Keys</TabsTrigger>
      </TabsList>

      <TabsContent value="roles">
        <AdminRolesPage
          roles={props.roles}
          newRoleName={props.newRoleName}
          newRoleDescription={props.newRoleDescription}
          onNewRoleNameChange={props.onNewRoleNameChange}
          onNewRoleDescriptionChange={props.onNewRoleDescriptionChange}
          onCreateRole={props.onCreateRole}
        />
      </TabsContent>

      <TabsContent value="assignments">
        <AdminAssignmentsPage
          branches={props.branches}
          users={props.users}
          roles={props.roles}
          branchUsers={props.branchUsers}
          assignmentBranchId={props.assignmentBranchId}
          assignUserId={props.assignUserId}
          assignBranchId={props.assignBranchId}
          assignRoleId={props.assignRoleId}
          onAssignmentBranchChange={props.onAssignmentBranchChange}
          onAssignUserChange={props.onAssignUserChange}
          onAssignBranchChange={props.onAssignBranchChange}
          onAssignRoleChange={props.onAssignRoleChange}
          onAssignUserBranch={props.onAssignUserBranch}
        />
      </TabsContent>

      <TabsContent value="api-keys">
        <AdminApiKeysPage branches={props.branches} token={props.token} />
      </TabsContent>
    </Tabs>
  );
}
