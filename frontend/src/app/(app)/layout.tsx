"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, CreditCard } from "lucide-react";
import { apiFetch, clearToken, getToken, switchOrganization } from "@/lib/api";
import { useWebSocket } from "@/hooks/use-websocket";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [showNotifs, setShowNotifs] = useState(false);

  // Real-time WebSocket connection for live tenant synchronization
  useWebSocket();

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
    }
  }, [router]);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<any>("/me"),
    retry: false,
  });

  const { data: notifData } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => apiFetch<any>("/notifications").catch(() => ({ unread_count: 0, notifications: [] })),
    refetchInterval: 20000,
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => apiFetch("/notifications/read-all", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markReadMutation = useMutation({
    mutationFn: (notifId: string) => apiFetch(`/notifications/${notifId}/read`, { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  const handleOrgChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newOrgId = e.target.value;
    if (newOrgId && newOrgId !== currentOrg?.id) {
      try {
        await switchOrganization(newOrgId);
        window.location.reload();
      } catch (err) {
        console.error("Failed to switch organization:", err);
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="text-sm font-medium text-slate-500 animate-pulse">Loading workspace...</div>
      </div>
    );
  }

  const currentOrg = profile?.organizations?.find((o: any) => o.id === profile?.current_org_id) || profile?.organizations?.[0];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white shadow-xs">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="flex items-center gap-2">
              <span className="text-xl">✈️</span>
              <span className="font-bold tracking-tight text-slate-900">TaskPilot</span>
            </Link>

            {profile?.organizations?.length > 1 ? (
              <div className="flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                <span>🏢</span>
                <select
                  value={currentOrg?.id}
                  onChange={handleOrgChange}
                  aria-label="Switch organization"
                  className="bg-transparent border-none text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer"
                >
                  {profile.organizations.map((org: any) => (
                    <option key={org.id} value={org.id}>
                      {org.name} ({org.role})
                    </option>
                  ))}
                </select>
              </div>
            ) : currentOrg ? (
              <div className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                <span>🏢 {currentOrg.name}</span>
                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-blue-700">
                  {currentOrg.role}
                </span>
              </div>
            ) : null}

            {/* Main Navigation Links */}
            <nav className="flex items-center gap-1">
              <Link
                href="/dashboard"
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                  pathname.startsWith("/dashboard") || pathname.startsWith("/projects")
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Projects
              </Link>
              <Link
                href="/teams"
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                  pathname.startsWith("/teams")
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Teams
              </Link>
              <Link
                href="/settings/billing"
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                  pathname.startsWith("/settings/billing")
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Billing
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            {/* Notification Bell Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowNotifs(!showNotifs)}
                className="relative rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                title="Notifications"
              >
                <Bell className="h-4 w-4" />
                {notifData?.unread_count > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-[9px] font-bold text-white ring-2 ring-white">
                    {notifData.unread_count}
                  </span>
                )}
              </button>

              {showNotifs && (
                <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden z-50">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 bg-slate-50">
                    <span className="text-xs font-bold text-slate-800">
                      Notifications ({notifData?.unread_count || 0})
                    </span>
                    {notifData?.unread_count > 0 && (
                      <button
                        onClick={() => markAllReadMutation.mutate()}
                        className="text-[11px] font-semibold text-blue-600 hover:underline"
                      >
                        Mark all read
                      </button>
                    )}
                  </div>

                  <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
                    {!notifData?.notifications || notifData.notifications.length === 0 ? (
                      <div className="p-4 text-center text-xs text-slate-400">No notifications yet</div>
                    ) : (
                      notifData.notifications.map((n: any) => (
                        <div
                          key={n.id}
                          className={`p-3 text-xs space-y-1 transition ${
                            n.is_read ? "bg-white opacity-70" : "bg-blue-50/30"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-900">{n.title}</span>
                            {!n.is_read && (
                              <button
                                onClick={() => markReadMutation.mutate(n.id)}
                                className="text-slate-400 hover:text-blue-600 p-0.5"
                                title="Mark read"
                              >
                                <Check className="h-3 w-3" />
                              </button>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-600">{n.message}</p>
                          {n.link && (
                            <Link
                              href={n.link}
                              onClick={() => setShowNotifs(false)}
                              className="text-[10px] font-semibold text-blue-600 hover:underline block pt-0.5"
                            >
                              View details →
                            </Link>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            <span className="text-xs text-slate-600 font-medium">{profile?.email}</span>
            <button
              onClick={handleLogout}
              className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
