import { Building2, LogOut, Menu, RefreshCw } from "lucide-react";

import { Button } from "../components/ui/button";
import { SelectNative } from "../components/ui/select-native";
import { Branch, User } from "./types";

type AppHeaderProps = {
  me: User | null;
  branches: Branch[];
  selectedBranch: string;
  selectedBranchTimezone?: string;
  onBranchChange: (branchId: string) => void;
  onSignOut: () => void;
  onOpenMenu: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
};

export function AppHeader({
  me,
  branches,
  selectedBranch,
  selectedBranchTimezone,
  onBranchChange,
  onSignOut,
  onOpenMenu,
  onRefresh,
  isRefreshing,
}: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b bg-background/90 backdrop-blur-xl">
      <div className="flex min-h-20 items-center gap-3 px-4 md:px-6">
        <Button variant="outline" size="icon" className="shrink-0 lg:hidden" onClick={onOpenMenu} aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </Button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{me?.full_name ?? "User"}</p>
          <p className="truncate text-xs text-muted-foreground">
            {selectedBranchTimezone ? `Timezone: ${selectedBranchTimezone}` : "Select an active branch"}
          </p>
        </div>
        <div className="hidden min-w-[260px] items-center gap-2 sm:flex">
          <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
          <SelectNative value={selectedBranch} onChange={(event) => onBranchChange(event.target.value)}>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.code} — {branch.name}
              </option>
            ))}
          </SelectNative>
        </div>
        <Button variant="outline" size="icon" onClick={onRefresh} disabled={isRefreshing || !selectedBranch} aria-label="Refresh data">
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
        </Button>
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-900 text-xs font-semibold text-white">
          {(me?.full_name ?? "U")
            .split(" ")
            .map((part) => part[0])
            .join("")
            .slice(0, 2)
            .toUpperCase()}
        </div>
        <Button variant="ghost" size="icon" onClick={onSignOut} aria-label="Sign out">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
      <div className="border-t px-4 py-2 sm:hidden">
        <SelectNative value={selectedBranch} onChange={(event) => onBranchChange(event.target.value)}>
          {branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.code} — {branch.name}
            </option>
          ))}
        </SelectNative>
      </div>
    </header>
  );
}
