import "../styles/learner-candidate-pages.css";
import { useState } from "react";
import { Bell, Trophy, FileCheck2, Award, Check } from "lucide-react";
import { Card, Badge, Button } from "../components/ui/primitives.jsx";
import { PageHeader, Loading, DataSource, EmptyState } from "../components/ui/states.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { api, withFallback } from "../lib/api.js";
import { demoInbox } from "../lib/demo.js";

const ICON = { badge_earned: Trophy, exam_reminder: FileCheck2, certificate_issued: Award };

function ago(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function Notifications() {
  const feed = useAsync(() => withFallback(api.inbox(), demoInbox), []);
  const [items, setItems] = useState(null);
  const list = items ?? feed.data ?? [];

  if (feed.loading) return <Loading label="Loading notifications…" />;

  async function markRead(id) {
    setItems(list.map((n) => (n.id === id ? { ...n, read: true } : n)));
    try {
      await api.markRead(id);
    } catch {
      /* demo */
    }
  }

  const unread = list.filter((n) => !n.read).length;

  return (
    <div className="page-composition page-composition-account learner-screen-notifications"><div className="max-w-2xl">
      <PageHeader
        title="Notifications"
        subtitle={unread ? `${unread} unread` : "You're all caught up"}
        right={<DataSource live={feed.live} />}
      />
      {list.length === 0 ? (
        <EmptyState title="No notifications" hint="Updates about your learning and drives appear here." />
      ) : (
        <div className="notification-inbox-feed space-y-2" aria-label="Notification inbox">
          {list.map((n) => {
            const Icon = ICON[n.template_key] || Bell;
            return (
              <Card
                key={n.id}
                className={`p-4 flex items-start gap-3 ${n.read ? "" : "border-brand-500/30 bg-brand-500/[0.03]"}`}
              >
                <span className="grid place-items-center h-10 w-10 rounded-md bg-brand-500/10 text-brand-600 shrink-0">
                  <Icon size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-ink-900 truncate">{n.subject}</p>
                    {!n.read && <Badge tone="brand">new</Badge>}
                  </div>
                  <p className="text-sm text-slate-500 mt-0.5">{n.body}</p>
                  <p className="text-xs text-slate-400 mt-1">{ago(n.created_at)}</p>
                </div>
                {!n.read && (
                  <Button size="sm" variant="ghost" onClick={() => markRead(n.id)}>
                    <Check size={15} /> Read
                  </Button>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div></div>
  );
}
