import { Bell, CheckCheck, MessageSquare, RefreshCw, UserRoundPlus } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { UserNotification } from "@/lib/api"

type NotificationsInboxProps = {
  items: UserNotification[];
  total: number;
  unreadTotal: number;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onLoadMore: () => void;
  onMarkAllRead: () => void;
  onOpen: (notification: UserNotification) => void;
};

function eventIcon(eventType: UserNotification["event_type"]) {
  if (eventType === "task.assigned") return UserRoundPlus
  if (eventType === "task.comment_added") return MessageSquare
  return CheckCheck
}

export function NotificationsInbox({ items, total, unreadTotal, loading, error, onRefresh, onLoadMore, onMarkAllRead, onOpen }: NotificationsInboxProps) {
  return (
    <section aria-labelledby="task-notifications-title" className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 id="task-notifications-title" className="text-sm font-semibold text-foreground">Task updates</h3>
            {unreadTotal > 0 && <Badge variant="secondary" aria-label={`${unreadTotal} unread notifications`}>{unreadTotal} unread</Badge>}
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">Assignments, status changes, and discussion updates across your projects.</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" aria-label="Refresh notifications" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          </Button>
          <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-xs" onClick={onMarkAllRead} disabled={unreadTotal === 0 || loading}>Mark all read</Button>
        </div>
      </div>

      {error && <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800"><span>{error}</span><Button type="button" variant="outline" size="sm" onClick={onRefresh}>Try again</Button></div>}
      {loading && items.length === 0 && <p role="status" className="rounded-xl border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">Loading task updates…</p>}
      {!loading && !error && items.length === 0 && <div className="grid justify-items-center gap-2 rounded-xl border border-dashed bg-muted/20 p-6 text-center">
        <Bell className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium text-foreground">No task updates yet</p>
        <p className="max-w-xs text-xs leading-5 text-muted-foreground">New assignments and relevant task changes will appear here.</p>
      </div>}

      {items.length > 0 && <div className="divide-y overflow-hidden rounded-xl border" role="list" aria-label="Task notifications" aria-busy={loading}>
        {items.map((notification) => {
          const Icon = eventIcon(notification.event_type)
          const unread = notification.read_at === null
          return <div key={notification.id} role="listitem">
            <button type="button" className={`flex w-full items-start gap-3 p-3 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${unread ? "bg-[#f1f8f6]" : "bg-white"}`} onClick={() => onOpen(notification)}>
              <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${notification.event_type === "task.comment_added" ? "bg-blue-50 text-blue-800" : notification.event_type === "task.assigned" ? "bg-teal-50 text-teal-900" : "bg-slate-100 text-slate-700"}`}><Icon className="h-4 w-4" aria-hidden="true" /></span>
              <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-2">
                  <strong className={`block min-w-0 truncate text-sm ${unread ? "font-semibold text-foreground" : "font-medium text-[#43596b]"}`}>{notification.title}</strong>
                  {unread && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-teal-700" aria-label="Unread"><span className="sr-only">Unread</span></span>}
                </span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">{notification.message}</span>
                <span className="mt-1.5 flex flex-wrap items-center gap-x-2 text-[0.68rem] text-muted-foreground">
                  <span className="font-medium text-[#31515d]">{notification.project_title}</span>
                  <span aria-hidden="true">·</span>
                  <time dateTime={notification.created_at}>{new Date(notification.created_at).toLocaleString()}</time>
                </span>
              </span>
            </button>
          </div>
        })}
      </div>}

      {items.length > 0 && <div className="flex items-center justify-between gap-3">
        <p className="text-[0.68rem] text-muted-foreground">{items.length} shown of {total}</p>
        {items.length < total && <Button type="button" variant="outline" size="sm" onClick={onLoadMore} disabled={loading}>{loading ? "Loading…" : "Load more"}</Button>}
      </div>}
    </section>
  )
}
