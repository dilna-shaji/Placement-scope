import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import type { ModuleId } from '../types';

type ToastKind = 'success' | 'error' | 'info';
interface Toast { id: number; msg: string; kind: ToastKind }
interface UICtx {
  route: ModuleId | string;
  navigate: (id: ModuleId) => void;
  collapsed: boolean;
  toggleCollapsed: () => void;
  drawerOpen: boolean;
  setDrawerOpen: (v: boolean) => void;
  toast: (msg: string, kind?: ToastKind) => void;
}
const Ctx = createContext<UICtx | null>(null);

const readRoute = () => window.location.hash.replace(/^#\/?/, '') || 'dashboard';

export function UIProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState(readRoute());
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('ph_sidebar_collapsed') === '1');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const on = () => { setRoute(readRoute()); setDrawerOpen(false); };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  const toast = useCallback((msg: string, kind: ToastKind = 'success') => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === 'error' ? 6000 : 3600);
  }, []);

  const value: UICtx = {
    route,
    navigate: (id) => { window.location.hash = `/${id}`; },
    collapsed,
    toggleCollapsed: () => setCollapsed((c) => { localStorage.setItem('ph_sidebar_collapsed', c ? '0' : '1'); return !c; }),
    drawerOpen, setDrawerOpen, toast,
  };

  const icons = { success: CheckCircle2, error: AlertTriangle, info: Info };
  const tones = { success: 'text-aqua', error: 'text-coral', info: 'text-violet' };
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 w-[min(92vw,380px)]" role="status" aria-live="polite">
        <AnimatePresence>
          {toasts.map((t) => {
            const I = icons[t.kind];
            return (
              <motion.div key={t.id} layout initial={{ opacity: 0, y: 24, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40 }} className="flex items-start gap-3 rounded-2xl bg-midnight text-white px-4 py-3.5 shadow-2xl text-[14px]">
                <I className={`w-5 h-5 shrink-0 mt-0.5 ${tones[t.kind]}`} />
                <span>{t.msg}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}

export const useUI = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('useUI outside UIProvider');
  return c;
};
