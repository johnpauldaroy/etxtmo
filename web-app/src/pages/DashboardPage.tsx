import { AlertTriangle, Clock3, Megaphone, Send } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { DeliveryTrendPoint, Report } from "./types";

type DashboardPageProps = {
  report: Report | null;
  deliveryTrend: DeliveryTrendPoint[];
};

const compactNumber = (value: number) => new Intl.NumberFormat(undefined, { notation: "compact" }).format(value);

function DeliveryLineChart({ data }: { data: DeliveryTrendPoint[] }) {
  const width = 760;
  const height = 250;
  const padding = { top: 20, right: 18, bottom: 42, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(1, ...data.flatMap((point) => [point.sent, point.failed]));
  const x = (index: number) => padding.left + (index * plotWidth) / Math.max(1, data.length - 1);
  const y = (value: number) => padding.top + plotHeight - (value / maxValue) * plotHeight;
  const sentPoints = data.map((point, index) => `${x(index)},${y(point.sent)}`).join(" ");
  const failedPoints = data.map((point, index) => `${x(index)},${y(point.failed)}`).join(" ");

  return (
    <div>
      <div className="mb-3 flex items-center gap-5 text-xs">
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />Submitted</span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-rose-500" />Failed</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label="Submitted and failed messages over the last seven days">
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const lineY = padding.top + plotHeight - ratio * plotHeight;
          return (
            <g key={ratio}>
              <line x1={padding.left} x2={width - padding.right} y1={lineY} y2={lineY} stroke="#e2e8f0" strokeDasharray="4 5" />
              <text x={padding.left - 9} y={lineY + 4} textAnchor="end" className="fill-slate-400 text-[11px]">
                {compactNumber(Math.round(maxValue * ratio))}
              </text>
            </g>
          );
        })}
        {data.map((point, index) => (
          <text key={point.date} x={x(index)} y={height - 12} textAnchor="middle" className="fill-slate-400 text-[11px]">
            {new Date(`${point.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </text>
        ))}
        <polyline points={sentPoints} fill="none" stroke="#10b981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <polyline points={failedPoints} fill="none" stroke="#f43f5e" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((point, index) => (
          <g key={`points-${point.date}`}>
            <circle cx={x(index)} cy={y(point.sent)} r="4" fill="#fff" stroke="#10b981" strokeWidth="3">
              <title>{`${point.date}: ${point.sent} submitted`}</title>
            </circle>
            <circle cx={x(index)} cy={y(point.failed)} r="4" fill="#fff" stroke="#f43f5e" strokeWidth="3">
              <title>{`${point.date}: ${point.failed} failed`}</title>
            </circle>
          </g>
        ))}
      </svg>
    </div>
  );
}

function DeliveryBarChart({ sent, failed }: { sent: number; failed: number }) {
  const maximum = Math.max(1, sent, failed);
  const total = sent + failed;
  const successRate = total ? Math.round((sent / total) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between rounded-xl bg-slate-50 p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Submission success</p>
          <p className="mt-1 text-4xl font-semibold tracking-tight">{successRate}%</p>
        </div>
        <p className="text-right text-xs text-muted-foreground">{compactNumber(total)} total<br />completed messages</p>
      </div>
      <div className="space-y-5">
        <div>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 font-medium"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />Submitted</span>
            <span className="font-semibold">{sent.toLocaleString()}</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${(sent / maximum) * 100}%` }} />
          </div>
        </div>
        <div>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 font-medium"><span className="h-2.5 w-2.5 rounded-full bg-rose-500" />Failed</span>
            <span className="font-semibold">{failed.toLocaleString()}</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-rose-500 transition-all" style={{ width: `${(failed / maximum) * 100}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function DashboardPage({ report, deliveryTrend }: DashboardPageProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-orange-100 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription>Total Campaigns</CardDescription>
            <CardTitle className="text-3xl">{report?.campaigns_total ?? 0}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2 text-xs text-muted-foreground">
            <Megaphone className="h-4 w-4 text-primary" />
            Active branch campaign volume
          </CardContent>
        </Card>
        <Card className="border-emerald-100 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription>Messages Submitted</CardDescription>
            <CardTitle className="text-3xl">{report?.messages_sent ?? 0}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2 text-xs text-muted-foreground">
            <Send className="h-4 w-4 text-emerald-600" />
            Accepted by the modem and mobile network
          </CardContent>
        </Card>
        <Card className="border-red-100 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription>Messages Failed</CardDescription>
            <CardTitle className="text-3xl">{report?.messages_failed ?? 0}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2 text-xs text-muted-foreground">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            Modem submission failures requiring review
          </CardContent>
        </Card>
        <Card className="border-amber-100 shadow-sm">
          <CardHeader className="pb-2">
            <CardDescription>Pending Queue</CardDescription>
            <CardTitle className="text-3xl">{report?.pending_queue ?? 0}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock3 className="h-4 w-4 text-amber-600" />
            Messages waiting for modem pickup
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Submission Trend</CardTitle>
            <CardDescription>Submitted and failed messages over the last 7 days.</CardDescription>
          </CardHeader>
          <CardContent>
            <DeliveryLineChart data={deliveryTrend} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Submission Performance</CardTitle>
            <CardDescription>Overall modem submission and failure totals.</CardDescription>
          </CardHeader>
          <CardContent>
            <DeliveryBarChart sent={report?.messages_sent ?? 0} failed={report?.messages_failed ?? 0} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
