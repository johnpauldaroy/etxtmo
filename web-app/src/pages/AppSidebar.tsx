import {
  Activity,
  CalendarClock,
  ChevronRight,
  Clock3,
  Inbox,
  KeyRound,
  LayoutDashboard,
  Megaphone,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Radio,
  Smartphone,
  Users,
  X,
} from "lucide-react";

import logoMark from "../assets/logo-mark.png";

import { Button } from "../components/ui/button";
import { TabKey } from "./types";

type NavigationItem = {
  key: TabKey;
  label: string;
  icon: typeof Activity;
  badge?: number;
};

type NavigationGroup = {
  label: string;
  items: NavigationItem[];
};

type AppSidebarProps = {
  activeTab: TabKey;
  isSuperuser: boolean;
  mobileOpen: boolean;
  collapsed: boolean;
  onNavigate: (tab: TabKey) => void;
  onClose: () => void;
  onToggleCollapsed: () => void;
};

export function AppSidebar({
  activeTab,
  isSuperuser,
  mobileOpen,
  collapsed,
  onNavigate,
  onClose,
  onToggleCollapsed,
}: AppSidebarProps) {
  const groups: NavigationGroup[] = [
    {
      label: "Workspace",
      items: [
        { key: "dashboard", label: "Overview", icon: LayoutDashboard },
        { key: "contacts", label: "Contacts", icon: Users },
        { key: "groups", label: "Groups", icon: Users },
        { key: "templates", label: "Templates", icon: MessageSquareText },
        { key: "campaigns", label: "Campaigns", icon: Megaphone },
      ],
    },
    {
      label: "Operations",
      items: [
        { key: "rules", label: "Schedules", icon: CalendarClock },
        { key: "queue", label: "Message queue", icon: Clock3 },
        { key: "incoming", label: "Inbox & opt-outs", icon: Inbox },
      ],
    },
    {
      label: "System",
      items: [
        { key: "modems", label: "Modems", icon: Smartphone },
        { key: "audit", label: "Audit log", icon: Activity },
      ],
    },
  ];

  if (isSuperuser) {
    groups.push({
      label: "Administration",
      items: [
        { key: "admin_users", label: "Users", icon: Users },
        { key: "admin_access", label: "Access control", icon: KeyRound },
        { key: "admin_branches", label: "Branches", icon: Radio },
      ],
    });
  }

  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-slate-800 bg-slate-950 text-white transition-[transform,width] duration-200 lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "lg:w-[84px]" : "lg:w-[280px]"} w-[280px]`}
      >
        <div className={`flex h-20 items-center border-b border-white/10 ${collapsed ? "lg:justify-center lg:px-2" : "justify-between px-5"}`}>
          <div className={`flex items-center gap-3 ${collapsed ? "lg:gap-0" : ""}`}>
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white shadow-lg shadow-orange-950/30">
              <img src={logoMark} alt="e-txtmo" className="h-8 w-8 object-contain" />
            </div>
            <div className={collapsed ? "lg:hidden" : ""}>
              <p className="font-heading text-lg font-semibold leading-none">e-txtmo</p>
              <p className="mt-1 text-xs text-slate-400">Messaging control center</p>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={`text-slate-300 hover:bg-white/10 hover:text-white lg:hidden ${collapsed ? "hidden" : ""}`}
            onClick={onClose}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {groups.map((group) => (
            <div key={group.label}>
              <p className={`mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 ${collapsed ? "lg:sr-only" : ""}`}>
                {group.label}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = activeTab === item.key;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      title={collapsed ? item.label : undefined}
                      onClick={() => {
                        onNavigate(item.key);
                        onClose();
                      }}
                      className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${
                        collapsed ? "lg:justify-center" : ""
                      } ${
                        active
                          ? "bg-orange-500 text-white shadow-md shadow-orange-950/30"
                          : "text-slate-300 hover:bg-white/[0.07] hover:text-white"
                      }`}
                    >
                      <Icon className="h-[18px] w-[18px] shrink-0" />
                      <span className={`flex-1 ${collapsed ? "lg:hidden" : ""}`}>{item.label}</span>
                      {!!item.badge && (
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] ${collapsed ? "lg:hidden" : ""} ${
                            active ? "bg-white/20" : "bg-amber-400 text-slate-950"
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                      <ChevronRight
                        className={`h-4 w-4 ${collapsed ? "lg:hidden" : ""} ${active ? "opacity-80" : "opacity-0 group-hover:opacity-50"}`}
                      />
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 px-3 py-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`hidden w-full items-center gap-2 text-slate-300 hover:bg-white/10 hover:text-white lg:flex ${
              collapsed ? "justify-center px-0" : "justify-start px-3"
            }`}
          >
            {collapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
            {!collapsed && <span className="text-sm font-medium">Collapse</span>}
          </Button>
        </div>

        <div className={`border-t border-white/10 px-5 py-4 ${collapsed ? "lg:px-0 lg:text-center" : ""}`}>
          <div className={`flex items-center gap-2 text-xs text-slate-400 ${collapsed ? "lg:justify-center" : ""}`}>
            <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,.8)]" />
            <span className={collapsed ? "lg:hidden" : ""}>API connected</span>
          </div>
        </div>
      </aside>
    </>
  );
}
