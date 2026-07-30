import { FormEvent, useCallback, useEffect, useState } from "react";

import { apiRequest } from "../api/client";
import { Branch, BranchAssignmentUser, Role, User, UserUpdateInput } from "../pages/types";

type UseAdminActionsOptions = {
  token: string;
  isSuperuser: boolean;
  selectedBranch: string;
  branches: Branch[];
  refreshProfileAndBranches: (activeToken: string) => Promise<void>;
  setSelectedBranch: (branchId: string) => void;
  refreshBranchData: (activeToken: string, branchId: string) => Promise<void>;
  onError: (message: string) => void;
};

export function useAdminActions({
  token,
  isSuperuser,
  selectedBranch,
  branches,
  refreshProfileAndBranches,
  setSelectedBranch,
  refreshBranchData,
  onError,
}: UseAdminActionsOptions) {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [branchUsers, setBranchUsers] = useState<BranchAssignmentUser[]>([]);

  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserUsername, setNewUserUsername] = useState("");
  const [newUserFullName, setNewUserFullName] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserIsSuperuser, setNewUserIsSuperuser] = useState("false");
  const [newUserBranchId, setNewUserBranchId] = useState("");

  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");

  const [assignmentBranchId, setAssignmentBranchId] = useState("");
  const [assignUserId, setAssignUserId] = useState("");
  const [assignBranchId, setAssignBranchId] = useState("");
  const [assignRoleId, setAssignRoleId] = useState("");

  const [newBranchCode, setNewBranchCode] = useState("");
  const [newBranchName, setNewBranchName] = useState("");
  const [newBranchTimezone, setNewBranchTimezone] = useState("Asia/Manila");

  const refreshUsersAndRoles = useCallback(
    async (activeToken: string) => {
      const [userRows, roleRows] = await Promise.all([
        apiRequest<User[]>("/api/admin/users", "GET", undefined, activeToken),
        apiRequest<Role[]>("/api/admin/roles", "GET", undefined, activeToken),
      ]);
      setUsers(userRows);
      setRoles(roleRows);
    },
    [],
  );

  const refreshAssignments = useCallback(async (activeToken: string, branchId: string) => {
    if (!branchId) {
      setBranchUsers([]);
      return;
    }
    const response = await apiRequest<{ users: BranchAssignmentUser[] }>(
      `/api/admin/branches/${branchId}`,
      "GET",
      undefined,
      activeToken,
    );
    setBranchUsers(response.users);
  }, []);

  useEffect(() => {
    if (!token || !isSuperuser) {
      setUsers([]);
      setRoles([]);
      setBranchUsers([]);
      setAssignmentBranchId("");
      setAssignUserId("");
      setAssignBranchId("");
      setAssignRoleId("");
      return;
    }
    async function loadAdminData() {
      try {
        await refreshUsersAndRoles(token);
        onError("");
      } catch (err) {
        onError((err as Error).message);
      }
    }
    void loadAdminData();
  }, [token, isSuperuser, refreshUsersAndRoles, onError]);

  useEffect(() => {
    if (!isSuperuser) {
      return;
    }
    const fallbackBranchId = selectedBranch || branches[0]?.id || "";
    if (!assignmentBranchId && fallbackBranchId) {
      setAssignmentBranchId(fallbackBranchId);
    }
    if (!assignBranchId && fallbackBranchId) {
      setAssignBranchId(fallbackBranchId);
    }
  }, [selectedBranch, branches, assignmentBranchId, assignBranchId, isSuperuser]);

  useEffect(() => {
    const fallbackBranchId = selectedBranch || branches[0]?.id || "";
    if (!newUserBranchId && fallbackBranchId) {
      setNewUserBranchId(fallbackBranchId);
    }
  }, [selectedBranch, branches, newUserBranchId]);

  useEffect(() => {
    if (!token || !isSuperuser || !assignmentBranchId) {
      setBranchUsers([]);
      return;
    }
    async function loadAssignments() {
      try {
        await refreshAssignments(token, assignmentBranchId);
        onError("");
      } catch (err) {
        onError((err as Error).message);
      }
    }
    void loadAssignments();
  }, [token, isSuperuser, assignmentBranchId, refreshAssignments, onError]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newUserEmail.trim() || !newUserUsername.trim() || !newUserFullName.trim() || !newUserPassword.trim()) {
      return false;
    }
    if (newUserIsSuperuser !== "true" && !newUserBranchId) {
      onError("Select a branch for the new standard user");
      return false;
    }
    try {
      await apiRequest<User>(
        "/api/auth/users",
        "POST",
        {
          email: newUserEmail.trim(),
          username: newUserUsername.trim(),
          full_name: newUserFullName.trim(),
          password: newUserPassword,
          is_superuser: newUserIsSuperuser === "true",
          branch_id: newUserBranchId || null,
        },
        token,
      );
      setNewUserEmail("");
      setNewUserUsername("");
      setNewUserFullName("");
      setNewUserPassword("");
      setNewUserIsSuperuser("false");
      await refreshUsersAndRoles(token);
      if (newUserBranchId && assignmentBranchId === newUserBranchId) {
        await refreshAssignments(token, newUserBranchId);
      }
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  async function updateUser(userId: string, values: UserUpdateInput) {
    try {
      await apiRequest<User>(
        `/api/admin/users/${userId}`,
        "PUT",
        values,
        token,
      );
      await refreshUsersAndRoles(token);
      onError("");
      return true;
    } catch (err) {
      onError((err as Error).message);
      return false;
    }
  }

  async function createRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newRoleName.trim()) {
      return;
    }
    try {
      await apiRequest(
        "/api/admin/roles",
        "POST",
        {
          name: newRoleName.trim(),
          description: newRoleDescription.trim() || null,
        },
        token,
      );
      setNewRoleName("");
      setNewRoleDescription("");
      await refreshUsersAndRoles(token);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function assignUserBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assignUserId || !assignBranchId) {
      return;
    }
    const parsedRoleId = assignRoleId ? Number(assignRoleId) : null;
    if (assignRoleId && !Number.isInteger(parsedRoleId)) {
      onError("Role selection is invalid");
      return;
    }
    try {
      await apiRequest(
        "/api/admin/user-branches",
        "POST",
        {
          user_id: assignUserId,
          branch_id: assignBranchId,
          role_id: parsedRoleId,
        },
        token,
      );
      setAssignmentBranchId(assignBranchId);
      await refreshAssignments(token, assignBranchId);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function createBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newBranchCode.trim() || !newBranchName.trim()) {
      return;
    }
    try {
      const createdBranch = await apiRequest<Branch>(
        "/api/admin/branches",
        "POST",
        {
          code: newBranchCode.trim(),
          name: newBranchName.trim(),
          timezone: newBranchTimezone.trim() || "Asia/Manila",
        },
        token,
      );
      setNewBranchCode("");
      setNewBranchName("");
      await refreshProfileAndBranches(token);
      setSelectedBranch(createdBranch.id);
      setAssignmentBranchId(createdBranch.id);
      setAssignBranchId(createdBranch.id);
      await Promise.all([refreshBranchData(token, createdBranch.id), refreshAssignments(token, createdBranch.id)]);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return {
    users,
    roles,
    branchUsers,
    newUserEmail,
    setNewUserEmail,
    newUserUsername,
    setNewUserUsername,
    newUserFullName,
    setNewUserFullName,
    newUserPassword,
    setNewUserPassword,
    newUserIsSuperuser,
    setNewUserIsSuperuser,
    newUserBranchId,
    setNewUserBranchId,
    newRoleName,
    setNewRoleName,
    newRoleDescription,
    setNewRoleDescription,
    assignmentBranchId,
    setAssignmentBranchId,
    assignUserId,
    setAssignUserId,
    assignBranchId,
    setAssignBranchId,
    assignRoleId,
    setAssignRoleId,
    newBranchCode,
    setNewBranchCode,
    newBranchName,
    setNewBranchName,
    newBranchTimezone,
    setNewBranchTimezone,
    createUser,
    updateUser,
    createRole,
    assignUserBranch,
    createBranch,
  };
}
