import { FormEvent, useEffect, useState } from "react";
import { Pencil, ToggleLeft, ToggleRight, X } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { ScheduleRule, Template } from "./types";
import {
  appendMessagePlaceholder,
  EmptyRow,
  formatMinuteOfDay,
  MessagePlaceholderButtons,
  Pagination,
  usePagination,
} from "./common";

type RulesPageProps = {
  rules: ScheduleRule[];
  templates: Template[];
  timezone: string;
  newRuleName: string;
  newRuleTime: string;
  newRuleDaysOfWeek: string;
  newRuleMessage: string;
  selectedRuleTemplateId: string;
  onRuleNameChange: (value: string) => void;
  onRuleTimeChange: (value: string) => void;
  onRuleDaysOfWeekChange: (value: string) => void;
  onRuleMessageChange: (value: string) => void;
  onRuleTemplateChange: (value: string) => void;
  onCreateRule: (event: FormEvent<HTMLFormElement>) => void;
  onDisableRule: (ruleId: string) => void;
  onEnableRule: (ruleId: string) => void;
  onEditRule: (
    ruleId: string,
    values: { name: string; minuteOfDay: number; daysOfWeek: string; templateId: string; messageBody: string },
  ) => Promise<boolean>;
};

export function RulesPage({
  rules,
  templates,
  timezone,
  newRuleName,
  newRuleTime,
  newRuleDaysOfWeek,
  newRuleMessage,
  selectedRuleTemplateId,
  onRuleNameChange,
  onRuleTimeChange,
  onRuleDaysOfWeekChange,
  onRuleMessageChange,
  onRuleTemplateChange,
  onCreateRule,
  onDisableRule,
  onEnableRule,
  onEditRule,
}: RulesPageProps) {
  const pagination = usePagination(rules);
  const selectedTemplate = templates.find((template) => template.id === selectedRuleTemplateId);
  const selectedDays = new Set(
    newRuleDaysOfWeek.split(",").map(Number).filter((day) => Number.isInteger(day) && day >= 0 && day <= 6),
  );

  const [editingRule, setEditingRule] = useState<ScheduleRule | null>(null);
  const [editName, setEditName] = useState("");
  const [editTime, setEditTime] = useState("09:00");
  const [editDaysOfWeek, setEditDaysOfWeek] = useState("0,1,2,3,4,5,6");
  const [editTemplateId, setEditTemplateId] = useState("");
  const [editMessage, setEditMessage] = useState("");

  useEffect(() => {
    if (!editingRule) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setEditingRule(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [editingRule]);

  const editSelectedDays = new Set(
    editDaysOfWeek.split(",").map(Number).filter((day) => Number.isInteger(day) && day >= 0 && day <= 6),
  );
  const editSelectedTemplate = templates.find((template) => template.id === editTemplateId);

  const weekdays = [
    { value: 0, short: "Sun", long: "Sunday" },
    { value: 1, short: "Mon", long: "Monday" },
    { value: 2, short: "Tue", long: "Tuesday" },
    { value: 3, short: "Wed", long: "Wednesday" },
    { value: 4, short: "Thu", long: "Thursday" },
    { value: 5, short: "Fri", long: "Friday" },
    { value: 6, short: "Sat", long: "Saturday" },
  ];

  const toggleDay = (day: number) => {
    const nextDays = new Set(selectedDays);
    if (nextDays.has(day)) nextDays.delete(day);
    else nextDays.add(day);
    onRuleDaysOfWeekChange([...nextDays].sort((a, b) => a - b).join(","));
  };

  const formatDays = (value: string) => {
    const days = new Set(value.split(",").map(Number));
    if (days.size === 7) return "Every day";
    if ([1, 2, 3, 4, 5].every((day) => days.has(day)) && days.size === 5) return "Weekdays";
    return weekdays.filter((day) => days.has(day.value)).map((day) => day.short).join(", ") || "-";
  };

  const toggleEditDay = (day: number) => {
    const nextDays = new Set(editSelectedDays);
    if (nextDays.has(day)) nextDays.delete(day);
    else nextDays.add(day);
    setEditDaysOfWeek([...nextDays].sort((a, b) => a - b).join(","));
  };

  const openEditDialog = (rule: ScheduleRule) => {
    setEditingRule(rule);
    setEditName(rule.name);
    setEditTime(formatMinuteOfDay(rule.minute_of_day));
    setEditDaysOfWeek(rule.days_of_week);
    setEditTemplateId(rule.template_id ?? "");
    setEditMessage(rule.message_body ?? "");
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Schedule Rules</CardTitle>
          <CardDescription>Create branch rules to auto-generate campaigns.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2" onSubmit={onCreateRule}>
            <label className="space-y-2 text-sm font-medium">
              Rule name
              <Input required placeholder="e.g. Weekday morning reminder" value={newRuleName} onChange={(event) => onRuleNameChange(event.target.value)} />
            </label>
            <label className="space-y-2 text-sm font-medium">
              Message template
              <SelectNative value={selectedRuleTemplateId} onChange={(event) => onRuleTemplateChange(event.target.value)}>
                <option value="">Custom scheduled message</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}{template.is_official ? " (Official)" : ""}
                  </option>
                ))}
              </SelectNative>
            </label>
            <label className="space-y-2 text-sm font-medium">
              Send time
              <Input
                type="time"
                required
                value={newRuleTime}
                onChange={(event) => onRuleTimeChange(event.target.value)}
              />
            </label>
            <label className="space-y-2 text-sm font-medium">
              Branch timezone
              <Input value={timezone} disabled />
            </label>
            <fieldset className="space-y-2 md:col-span-2">
              <legend className="text-sm font-medium">Repeat on</legend>
              <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
                {weekdays.map((day) => (
                  <label
                    key={day.value}
                    className={`flex cursor-pointer items-center justify-center rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                      selectedDays.has(day.value) ? "border-primary bg-primary/10 text-primary" : "bg-background hover:bg-muted"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={selectedDays.has(day.value)}
                      onChange={() => toggleDay(day.value)}
                    />
                    <span aria-label={day.long}>{day.short}</span>
                  </label>
                ))}
              </div>
              {selectedDays.size === 0 && <p className="text-xs text-destructive">Select at least one day.</p>}
            </fieldset>
            <div className="md:col-span-2">
              <label htmlFor="schedule-message" className="mb-2 block text-sm font-medium">Message</label>
              <Textarea
                id="schedule-message"
                required={!selectedRuleTemplateId}
                disabled={Boolean(selectedRuleTemplateId)}
                placeholder={selectedTemplate ? `Using message from "${selectedTemplate.name}"` : "Message sent to eligible branch contacts"}
                value={newRuleMessage}
                onChange={(event) => onRuleMessageChange(event.target.value)}
              />
              {!selectedRuleTemplateId && (
                <div className="mt-2">
                  <MessagePlaceholderButtons
                    onInsert={(placeholder) => onRuleMessageChange(appendMessagePlaceholder(newRuleMessage, placeholder))}
                  />
                </div>
              )}
              <p className="mt-2 text-xs text-muted-foreground">
                {selectedTemplate
                  ? "Each run uses this template's current message and sends it to eligible contacts in the active branch."
                  : "At the selected time, this message is queued for every consented contact in the active branch. Opted-out contacts are excluded."}
              </p>
            </div>
            <div className="md:col-span-2">
              <Button type="submit" disabled={selectedDays.size === 0}>Create schedule</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Rules</CardTitle>
          <CardDescription>Disable rules that should stop generating campaigns.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Days</TableHead>
                <TableHead>Template</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagination.pageItems.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-medium">{rule.name}</TableCell>
                  <TableCell>{formatMinuteOfDay(rule.minute_of_day)}</TableCell>
                  <TableCell>{formatDays(rule.days_of_week)}</TableCell>
                  <TableCell>
                    {rule.template_id
                      ? (templates.find((template) => template.id === rule.template_id)?.name ?? "Unavailable template")
                      : "Custom message"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={rule.is_active ? "success" : "secondary"}>
                      {rule.is_active ? "active" : "disabled"}
                    </Badge>
                  </TableCell>
                  <TableCell className="space-x-1 text-right">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 text-muted-foreground hover:text-primary"
                      aria-label={`Edit ${rule.name}`}
                      onClick={() => openEditDialog(rule)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className={`h-8 w-8 ${rule.is_active ? "text-emerald-600 hover:text-emerald-700" : "text-muted-foreground hover:text-foreground"}`}
                      aria-label={rule.is_active ? `Disable ${rule.name}` : `Enable ${rule.name}`}
                      title={rule.is_active ? "Disable" : "Enable"}
                      onClick={() => (rule.is_active ? onDisableRule(rule.id) : onEnableRule(rule.id))}
                    >
                      {rule.is_active ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && <EmptyRow colSpan={6} message="No schedule rules yet." />}
            </TableBody>
          </Table>
          <Pagination {...pagination} totalItems={rules.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
        </CardContent>
      </Card>

      {editingRule && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close edit rule dialog"
            onClick={() => setEditingRule(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-rule-title"
            className="relative z-10 w-full max-w-xl animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="edit-rule-title" className="text-xl font-semibold">Edit schedule rule</h2>
                <p className="mt-1 text-sm text-muted-foreground">Update when this rule runs and what it sends.</p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setEditingRule(null)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                if (editSelectedDays.size === 0) return;
                const updated = await onEditRule(editingRule.id, {
                  name: editName,
                  minuteOfDay: (() => {
                    const [hours, minutes] = editTime.split(":").map(Number);
                    return hours * 60 + minutes;
                  })(),
                  daysOfWeek: editDaysOfWeek,
                  templateId: editTemplateId,
                  messageBody: editMessage,
                });
                if (updated) setEditingRule(null);
              }}
            >
              <div className="space-y-2">
                <label htmlFor="edit-rule-name" className="text-sm font-medium">Rule name</label>
                <Input
                  id="edit-rule-name"
                  required
                  autoFocus
                  value={editName}
                  onChange={(event) => setEditName(event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="edit-rule-template" className="text-sm font-medium">Message template</label>
                  <SelectNative id="edit-rule-template" value={editTemplateId} onChange={(event) => setEditTemplateId(event.target.value)}>
                    <option value="">Custom scheduled message</option>
                    {templates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}{template.is_official ? " (Official)" : ""}
                      </option>
                    ))}
                  </SelectNative>
                </div>
                <div className="space-y-2">
                  <label htmlFor="edit-rule-time" className="text-sm font-medium">Send time</label>
                  <Input
                    id="edit-rule-time"
                    type="time"
                    required
                    value={editTime}
                    onChange={(event) => setEditTime(event.target.value)}
                  />
                </div>
              </div>
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">Repeat on</legend>
                <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
                  {weekdays.map((day) => (
                    <label
                      key={day.value}
                      className={`flex cursor-pointer items-center justify-center rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                        editSelectedDays.has(day.value) ? "border-primary bg-primary/10 text-primary" : "bg-background hover:bg-muted"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={editSelectedDays.has(day.value)}
                        onChange={() => toggleEditDay(day.value)}
                      />
                      <span aria-label={day.long}>{day.short}</span>
                    </label>
                  ))}
                </div>
                {editSelectedDays.size === 0 && <p className="text-xs text-destructive">Select at least one day.</p>}
              </fieldset>
              <div>
                <label htmlFor="edit-rule-message" className="mb-2 block text-sm font-medium">Message</label>
                <Textarea
                  id="edit-rule-message"
                  required={!editTemplateId}
                  disabled={Boolean(editTemplateId)}
                  placeholder={editSelectedTemplate ? `Using message from "${editSelectedTemplate.name}"` : "Message sent to eligible branch contacts"}
                  value={editMessage}
                  onChange={(event) => setEditMessage(event.target.value)}
                />
                {!editTemplateId && (
                  <div className="mt-2">
                    <MessagePlaceholderButtons
                      onInsert={(placeholder) => setEditMessage(appendMessagePlaceholder(editMessage, placeholder))}
                    />
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setEditingRule(null)}>Cancel</Button>
                <Button type="submit" disabled={editSelectedDays.size === 0}>Save changes</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
