import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "../components/ui/table";
import { AuditLog } from "./types";
import { EmptyRow, formatDate, Pagination, usePagination } from "./common";

type AuditPageProps = {
  auditLogs: AuditLog[];
};

export function AuditPage({ auditLogs }: AuditPageProps) {
  const pagination = usePagination(auditLogs);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit Log</CardTitle>
        <CardDescription>Recent branch-level actions and system events.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Entity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pagination.pageItems.map((log) => (
              <TableRow key={log.id}>
                <TableCell>{formatDate(log.created_at)}</TableCell>
                <TableCell className="font-medium">{log.action}</TableCell>
                <TableCell>{log.entity_type}</TableCell>
              </TableRow>
            ))}
            {auditLogs.length === 0 && <EmptyRow colSpan={3} message="No audit events found." />}
          </TableBody>
        </Table>
        <Pagination {...pagination} totalItems={auditLogs.length} onPageChange={pagination.setPage} onPageSizeChange={pagination.setPageSize} />
      </CardContent>
    </Card>
  );
}
