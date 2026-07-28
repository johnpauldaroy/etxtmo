import { useEffect, useId, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "../components/ui/button";
import { SelectNative } from "../components/ui/select-native";
import { TableCell, TableRow } from "../components/ui/table";
import { BadgeVariant } from "./types";

export const mapStatusToBadge = (status: string): BadgeVariant => {
  const value = status.toLowerCase();
  if (["sent", "approved", "online", "ok"].includes(value)) return "success";
  if (["failed", "rejected", "error", "offline"].includes(value)) return "destructive";
  if (["pending", "queued", "sending", "draft"].includes(value)) return "warning";
  return "secondary";
};

export const formatDate = (value?: string) => (value ? new Date(value).toLocaleString() : "-");

export const formatMinuteOfDay = (minute: number) => {
  const hours = Math.floor(minute / 60)
    .toString()
    .padStart(2, "0");
  const minutes = (minute % 60).toString().padStart(2, "0");
  return `${hours}:${minutes}`;
};

// GSM 03.38 default alphabet (basic + extension table). Any character outside this set
// forces UCS-2 encoding, which cuts the per-segment character budget roughly in half.
const GSM_7BIT_BASIC =
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?" +
  "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
const GSM_7BIT_EXTENDED = "^{}\\[~]|€";

export type SmsEncoding = "GSM-7" | "UCS-2";

export function getSmsEncoding(message: string): SmsEncoding {
  for (const char of message) {
    if (!GSM_7BIT_BASIC.includes(char) && !GSM_7BIT_EXTENDED.includes(char)) {
      return "UCS-2";
    }
  }
  return "GSM-7";
}

export function countSmsLength(message: string): number {
  let length = 0;
  for (const char of message) {
    length += GSM_7BIT_EXTENDED.includes(char) ? 2 : 1;
  }
  return length;
}

export type SmsMeta = {
  encoding: SmsEncoding;
  length: number;
  segments: number;
  perSegmentLimit: number;
};

export function getSmsMeta(message: string): SmsMeta {
  const encoding = getSmsEncoding(message);
  const length = encoding === "GSM-7" ? countSmsLength(message) : message.length;
  const singleLimit = encoding === "GSM-7" ? 160 : 70;
  const concatLimit = encoding === "GSM-7" ? 153 : 67;
  const segments = length === 0 ? 0 : length <= singleLimit ? 1 : Math.ceil(length / concatLimit);
  return { encoding, length, segments, perSegmentLimit: segments <= 1 ? singleLimit : concatLimit };
}

export function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="py-7 text-center text-sm text-muted-foreground">
        {message}
      </TableCell>
    </TableRow>
  );
}

export function usePagination<T>(items: T[], initialPageSize = 10) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  const setPageSize = (size: number) => {
    setPageSizeState(size);
    setPage(1);
  };

  return { page, pageCount, pageSize, pageItems, setPage, setPageSize };
}

type PaginationProps = {
  page: number;
  pageCount: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

export function Pagination({
  page,
  pageCount,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const pageSizeId = useId();

  if (totalItems === 0) return null;

  const firstItem = (page - 1) * pageSize + 1;
  const lastItem = Math.min(page * pageSize, totalItems);

  return (
    <div className="flex flex-col gap-3 border-t pt-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <label htmlFor={pageSizeId} className="whitespace-nowrap">Rows per page</label>
        <SelectNative
          id={pageSizeId}
          className="h-8 w-[72px] py-1"
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
        >
          {[10, 25, 50].map((size) => <option key={size} value={size}>{size}</option>)}
        </SelectNative>
        <span className="whitespace-nowrap">{firstItem}-{lastItem} of {totalItems}</span>
      </div>
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <span className="whitespace-nowrap">Page {page} of {pageCount}</span>
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="h-8 w-8"
          disabled={page <= 1}
          aria-label="Previous page"
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="h-8 w-8"
          disabled={page >= pageCount}
          aria-label="Next page"
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

const messagePlaceholders = [
  { label: "First name", value: "{{first_name}}" },
  { label: "Last name", value: "{{last_name}}" },
  { label: "Full name", value: "{{full_name}}" },
];

export function appendMessagePlaceholder(message: string, placeholder: string) {
  const separator = message && !/\s$/.test(message) ? " " : "";
  return `${message}${separator}${placeholder}`;
}

export function MessagePlaceholderButtons({ onInsert }: { onInsert: (placeholder: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">Insert contact field:</span>
      {messagePlaceholders.map((placeholder) => (
        <Button
          key={placeholder.value}
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs"
          onClick={() => onInsert(placeholder.value)}
        >
          {placeholder.label}
        </Button>
      ))}
    </div>
  );
}

export function SmsLengthMeter({ message }: { message: string }) {
  const meta = getSmsMeta(message);
  const hasPlaceholders = /\{\{(?:first_name|last_name|full_name|phone_number)\}\}/.test(message);
  return (
    <p className="text-xs text-muted-foreground">
      {meta.length} character{meta.length === 1 ? "" : "s"} · {meta.encoding}
      {" · "}
      {meta.segments === 0 ? "0 SMS segments" : `${meta.segments} SMS segment${meta.segments === 1 ? "" : "s"}`}
      {meta.segments > 0 && ` (${meta.perSegmentLimit}/segment)`}
      {hasPlaceholders && " · final length varies by contact"}
    </p>
  );
}
