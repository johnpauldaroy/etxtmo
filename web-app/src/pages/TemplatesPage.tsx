import { FormEvent, useEffect, useState } from "react";
import { Pencil, Trash2, X } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { SelectNative } from "../components/ui/select-native";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { Template } from "./types";
import {
  appendMessagePlaceholder,
  EmptyRow,
  MessagePlaceholderButtons,
  Pagination,
  SmsLengthMeter,
  usePagination,
} from "./common";

type TemplatesPageProps = {
  templates: Template[];
  newTemplateName: string;
  newTemplateBody: string;
  onTemplateNameChange: (value: string) => void;
  onTemplateBodyChange: (value: string) => void;
  onAddTemplate: (event: FormEvent<HTMLFormElement>) => void;
  onDeleteTemplate: (templateId: string) => void;
  onEditTemplate: (
    templateId: string,
    values: { name: string; body: string; is_official: boolean },
  ) => Promise<boolean>;
};

export function TemplatesPage({
  templates,
  newTemplateName,
  newTemplateBody,
  onTemplateNameChange,
  onTemplateBodyChange,
  onAddTemplate,
  onDeleteTemplate,
  onEditTemplate,
}: TemplatesPageProps) {
  const pagination = usePagination(templates);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [editName, setEditName] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editOfficial, setEditOfficial] = useState("true");

  useEffect(() => {
    if (!editingTemplate) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setEditingTemplate(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [editingTemplate]);

  function openEditDialog(template: Template) {
    setEditingTemplate(template);
    setEditName(template.name);
    setEditBody(template.body);
    setEditOfficial(template.is_official ? "true" : "false");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Templates</CardTitle>
        <CardDescription>Create reusable message templates for faster campaign setup.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-2" onSubmit={onAddTemplate}>
            <Input
              required
            placeholder="Template name"
            value={newTemplateName}
            onChange={(event) => onTemplateNameChange(event.target.value)}
          />
          <div className="space-y-1 md:col-span-2">
            <Textarea
              required
              placeholder="Message body"
              value={newTemplateBody}
              onChange={(event) => onTemplateBodyChange(event.target.value)}
            />
            <MessagePlaceholderButtons
              onInsert={(placeholder) => onTemplateBodyChange(appendMessagePlaceholder(newTemplateBody, placeholder))}
            />
            <div className="text-right">
              <SmsLengthMeter message={newTemplateBody} />
            </div>
          </div>
          <div className="md:col-span-2">
            <Button type="submit">Save template</Button>
          </div>
        </form>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Message</TableHead>
              <TableHead>Official</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pagination.pageItems.map((template) => (
              <TableRow key={template.id}>
                <TableCell className="font-medium">{template.name}</TableCell>
                <TableCell className="max-w-xl truncate">{template.body}</TableCell>
                <TableCell>
                  <Badge variant={template.is_official ? "default" : "outline"}>
                    {template.is_official ? "Official" : "Custom"}
                  </Badge>
                </TableCell>
                <TableCell className="space-x-1 text-right">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground hover:text-primary"
                    aria-label={`Edit ${template.name}`}
                    onClick={() => openEditDialog(template)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    aria-label={`Delete ${template.name}`}
                    onClick={() => {
                      if (window.confirm(`Delete template “${template.name}”?`)) onDeleteTemplate(template.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {templates.length === 0 && <EmptyRow colSpan={4} message="No templates yet." />}
          </TableBody>
        </Table>
        <Pagination {...pagination} totalItems={templates.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
      </CardContent>

      {editingTemplate && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close edit template dialog"
            onClick={() => setEditingTemplate(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-template-title"
            className="relative z-10 w-full max-w-xl animate-slide-up rounded-xl border bg-card p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="edit-template-title" className="text-xl font-semibold">Edit template</h2>
                <p className="mt-1 text-sm text-muted-foreground">Update the template details used by campaigns.</p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-2" onClick={() => setEditingTemplate(null)}>
                <X className="h-5 w-5" />
                <span className="sr-only">Close</span>
              </Button>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const updated = await onEditTemplate(editingTemplate.id, {
                  name: editName,
                  body: editBody,
                  is_official: editOfficial === "true",
                });
                if (updated) setEditingTemplate(null);
              }}
            >
              <div className="space-y-2">
                <label htmlFor="edit-template-name" className="text-sm font-medium">Template name</label>
                <Input
                  id="edit-template-name"
                  required
                  autoFocus
                  value={editName}
                  onChange={(event) => setEditName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="edit-template-body" className="text-sm font-medium">Message body</label>
                <Textarea
                  id="edit-template-body"
                  required
                  className="min-h-32"
                  value={editBody}
                  onChange={(event) => setEditBody(event.target.value)}
                />
                <MessagePlaceholderButtons
                  onInsert={(placeholder) => setEditBody(appendMessagePlaceholder(editBody, placeholder))}
                />
                <div className="text-right">
                  <SmsLengthMeter message={editBody} />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="edit-template-status" className="text-sm font-medium">Template type</label>
                <SelectNative id="edit-template-status" value={editOfficial} onChange={(event) => setEditOfficial(event.target.value)}>
                  <option value="true">Official</option>
                  <option value="false">Custom</option>
                </SelectNative>
              </div>
              <div className="flex justify-end gap-2 border-t pt-4">
                <Button type="button" variant="outline" onClick={() => setEditingTemplate(null)}>Cancel</Button>
                <Button type="submit">Save changes</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Card>
  );
}
