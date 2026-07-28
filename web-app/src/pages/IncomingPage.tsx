import { FormEvent } from "react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "../components/ui/table";
import { IncomingMessage, OptOutItem } from "./types";
import { EmptyRow, formatDate, Pagination, usePagination } from "./common";

type IncomingPageProps = {
  incomingMessages: IncomingMessage[];
  optOuts: OptOutItem[];
  manualOptOutPhone: string;
  manualOptOutReason: string;
  onManualOptOutPhoneChange: (value: string) => void;
  onManualOptOutReasonChange: (value: string) => void;
  onAddManualOptOut: (event: FormEvent<HTMLFormElement>) => void;
};

export function IncomingPage({
  incomingMessages,
  optOuts,
  manualOptOutPhone,
  manualOptOutReason,
  onManualOptOutPhoneChange,
  onManualOptOutReasonChange,
  onAddManualOptOut,
}: IncomingPageProps) {
  const incomingPagination = usePagination(incomingMessages);
  const optOutPagination = usePagination(optOuts);

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Incoming Messages</CardTitle>
          <CardDescription>Messages received from branch nodes and modems.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Contact</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Processed</TableHead>
                <TableHead>Received</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {incomingPagination.pageItems.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="font-medium">{item.contact_name || "Unknown contact"}</div>
                    <div className="mt-0.5 whitespace-nowrap text-xs text-muted-foreground">{item.phone_number}</div>
                  </TableCell>
                  <TableCell className="max-w-md truncate">{item.message_text}</TableCell>
                  <TableCell>
                    <Badge variant={item.processed ? "success" : "warning"}>{item.processed ? "yes" : "no"}</Badge>
                  </TableCell>
                  <TableCell>{formatDate(item.received_at)}</TableCell>
                </TableRow>
              ))}
              {incomingMessages.length === 0 && <EmptyRow colSpan={4} message="No incoming messages yet." />}
            </TableBody>
          </Table>
          <Pagination
            {...incomingPagination}
            totalItems={incomingMessages.length}
            onPageChange={incomingPagination.setPage}
            onPageSizeChange={incomingPagination.setPageSize}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Opt-Outs</CardTitle>
          <CardDescription>Manually add opt-outs and review current opt-out list.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onAddManualOptOut}>
            <Input
              required
              inputMode="tel"
              placeholder="Phone number"
              value={manualOptOutPhone}
              onChange={(event) => onManualOptOutPhoneChange(event.target.value)}
            />
            <Input
              placeholder="Reason (optional)"
              value={manualOptOutReason}
              onChange={(event) => onManualOptOutReasonChange(event.target.value)}
            />
            <Button type="submit">Add opt-out</Button>
          </form>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Phone</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {optOutPagination.pageItems.map((optOut) => (
                <TableRow key={optOut.id}>
                  <TableCell className="font-medium">{optOut.phone_number}</TableCell>
                  <TableCell>{optOut.source}</TableCell>
                  <TableCell className="max-w-md truncate">{optOut.reason || "-"}</TableCell>
                  <TableCell>{formatDate(optOut.created_at)}</TableCell>
                </TableRow>
              ))}
              {optOuts.length === 0 && <EmptyRow colSpan={4} message="No opt-outs recorded." />}
            </TableBody>
          </Table>
          <Pagination
            {...optOutPagination}
            totalItems={optOuts.length}
            onPageChange={optOutPagination.setPage}
            onPageSizeChange={optOutPagination.setPageSize}
          />
        </CardContent>
      </Card>
    </div>
  );
}
