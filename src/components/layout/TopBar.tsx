import { useEffect, useRef, useState } from 'react';
import { Bell, Menu, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useUI } from '../../context/UIContext';
import { api } from '../../lib/api';
import { moduleById } from '../../navigation';
import { Badge } from '../ui/kit';

export function TopBar() {
  const { user, can } = useAuth();
  const { route, navigate, setDrawerOpen } = useUI();
  const [unread, setUnread] = useState(0);
  const timer = useRef<number>(0);
  const m = moduleById(route);
  const canNotify = can('notifications:read');  // a stable boolean: `can` itself changes identity on every auth-context update

  useEffect(() => {
    if (!canNotify) return;
    const load = () => api.get<{ unread: number }>('/api/notifications').then((r) => setUnread(r.unread)).catch(() => {});
    load();
    timer.current = window.setInterval(load, 60000);
    window.addEventListener('ph:notifications', load);

    let es: EventSource | null = null;
    try {
      es = new EventSource('/api/notifications/stream');
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (typeof data.unread === 'number') setUnread(data.unread);
        } catch { /* ignore parse error */ }
      };
    } catch { /* fallback to interval polling */ }

    return () => {
      clearInterval(timer.current);
      window.removeEventListener('ph:notifications', load);
      if (es) es.close();
    };
  }, [canNotify]);

  return (
    <header className="shrink-0 h-[72px] bg-white/85 backdrop-blur border-b border-line flex items-center gap-4 px-4 sm:px-7 z-10">
      <button className="lg:hidden p-2.5 -ml-1 rounded-xl hover:bg-slate-100" aria-label="Open menu" onClick={() => setDrawerOpen(true)}><Menu className="w-5 h-5" /></button>
      <div className="min-w-0">
        <p className="text-[12px] font-semibold uppercase tracking-wider text-mute">{m?.section ?? 'PlacementHub'}</p>
        <p className="font-display font-bold text-[18px] truncate leading-tight">{m?.label ?? 'Dashboard'}</p>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <span className="hidden md:block"><Badge tone="violet"><ShieldCheck className="w-3.5 h-3.5" />{user!.roleLabel}</Badge></span>
        {user!.departmentName && <span className="hidden xl:block"><Badge tone="aqua">{user!.departmentName}</Badge></span>}
        {user!.companyName && <span className="hidden xl:block"><Badge tone="coral">{user!.companyName}</Badge></span>}
        {can('notifications:read') && (
          <button onClick={() => navigate('notifications')} aria-label={`Notifications, ${unread} unread`} className="relative p-2.5 rounded-xl hover:bg-slate-100 transition">
            <Bell className="w-5 h-5" />
            {unread > 0 && <span className="absolute top-1 right-1 min-w-[18px] h-[18px] px-1 grid place-items-center rounded-full bg-coral text-white text-[11px] font-bold animate-[pop_.3s_ease]">{unread > 9 ? '9+' : unread}</span>}
          </button>
        )}
      </div>
    </header>
  );
}
