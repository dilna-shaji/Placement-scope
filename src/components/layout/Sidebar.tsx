import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronsLeft, ChevronsRight, GraduationCap, LogOut, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useUI } from '../../context/UIContext';
import { allowedModules } from '../../navigation';
import { cn, initials } from '../../lib/format';

function NavBody({ collapsed, mobile }: { collapsed: boolean; mobile?: boolean }) {
  const { user, logout } = useAuth();
  const { route, navigate, toggleCollapsed, setDrawerOpen } = useUI();
  const [tip, setTip] = useState<{ label: string; top: number } | null>(null);
  const mods = allowedModules(user!);
  const sections = Array.from(new Set(mods.map((m) => m.section)));
  const slim = collapsed && !mobile;

  return (
    <div className="h-full flex flex-col bg-midnight text-white relative overflow-hidden">
      <div aria-hidden className="absolute -top-20 -left-20 w-64 h-64 rounded-full bg-violet/25 blur-3xl orb-a" />
      <div aria-hidden className="absolute bottom-24 -right-24 w-60 h-60 rounded-full bg-aqua/15 blur-3xl orb-b" />

      {/* brand: always visible */}
      <div className={cn('relative shrink-0 h-[72px] flex items-center border-b border-white/10', slim ? 'justify-center px-2' : 'justify-between px-5')}>
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet to-aqua grid place-items-center shrink-0 shadow-lg shadow-violet/30"><GraduationCap className="w-5 h-5" /></div>
          {!slim && <div className="min-w-0"><p className="font-display font-extrabold text-[18px] leading-none">PlacementHub</p><p className="text-[12px] text-white/55 mt-1">Placement Cell</p></div>}
        </div>
        {mobile && <button aria-label="Close menu" onClick={() => setDrawerOpen(false)} className="p-2 rounded-lg hover:bg-white/10"><X className="w-5 h-5" /></button>}
      </div>

      {/* navigation: its own scroll container */}
      <nav aria-label="Main" className="relative flex-1 min-h-0 overflow-y-auto sidebar-scroll py-4 px-3" onScroll={() => setTip(null)}>
        {sections.map((s) => (
          <div key={s} className="mb-5">
            {!slim ? <p className="px-3 mb-2 text-[11.5px] font-bold uppercase tracking-[.12em] text-white/40">{s}</p> : <div className="mx-3 mb-2 h-px bg-white/10" />}
            <ul className="space-y-1">
              {mods.filter((m) => m.section === s).map((m) => {
                const active = route === m.id;
                return (
                  <li key={m.id}>
                    <button onClick={() => navigate(m.id)} aria-current={active ? 'page' : undefined}
                      onMouseEnter={(e) => slim && setTip({ label: m.label, top: e.currentTarget.getBoundingClientRect().top + e.currentTarget.offsetHeight / 2 })}
                      onMouseLeave={() => setTip(null)} onFocus={(e) => slim && setTip({ label: m.label, top: e.currentTarget.getBoundingClientRect().top + 20 })} onBlur={() => setTip(null)}
                      className={cn('group relative w-full flex items-center gap-3 rounded-xl text-[14px] font-medium transition-colors', slim ? 'justify-center h-11' : 'px-3.5 h-11', active ? 'text-white' : 'text-white/70 hover:text-white hover:bg-white/8')}>
                      {active && <motion.span layoutId={mobile ? 'nav-active-m' : 'nav-active'} className="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo/90 to-violet/70 shadow-lg shadow-indigo/30" transition={{ type: 'spring', damping: 28, stiffness: 380 }} />}
                      {active && <motion.span layoutId={mobile ? 'nav-bar-m' : 'nav-bar'} className="absolute -left-3 top-2.5 bottom-2.5 w-1 rounded-r-full bg-lime" />}
                      <m.icon className="relative w-[19px] h-[19px] shrink-0 transition-transform group-hover:scale-110" />
                      {!slim && <span className="relative truncate">{m.label}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* account: always visible */}
      <div className="relative shrink-0 border-t border-white/10 p-3">
        <div className={cn('flex items-center gap-3 rounded-xl bg-white/6 p-2.5', slim && 'justify-center')}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-coral to-violet grid place-items-center font-bold text-[14px] shrink-0">{initials(user!.fullName)}</div>
          {!slim && <div className="min-w-0 flex-1"><p className="text-[14px] font-semibold truncate">{user!.fullName}</p><p className="text-[12px] text-white/55 truncate">{user!.roleLabel}</p></div>}
          {!slim && <button onClick={logout} aria-label="Sign out" title="Sign out" className="p-2 rounded-lg text-white/60 hover:text-white hover:bg-white/10"><LogOut className="w-4 h-4" /></button>}
        </div>
        {slim && <button onClick={logout} aria-label="Sign out" className="mt-2 w-full grid place-items-center h-10 rounded-xl text-white/60 hover:text-white hover:bg-white/10"><LogOut className="w-4 h-4" /></button>}
        {!mobile && (
          <button onClick={toggleCollapsed} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} className="mt-2 w-full hidden lg:flex items-center justify-center gap-2 h-9 rounded-xl text-[13px] text-white/55 hover:text-white hover:bg-white/8">
            {collapsed ? <ChevronsRight className="w-4 h-4" /> : <><ChevronsLeft className="w-4 h-4" />Collapse</>}
          </button>
        )}
      </div>

      {tip && <div className="fixed z-[90] left-[84px] -translate-y-1/2 px-3 py-1.5 rounded-lg bg-ink text-white text-[13px] font-medium shadow-xl pointer-events-none" style={{ top: tip.top }}>{tip.label}</div>}
    </div>
  );
}

export function Sidebar() {
  const { collapsed, drawerOpen, setDrawerOpen } = useUI();
  return (
    <>
      <motion.aside aria-label="Sidebar" initial={false} animate={{ width: collapsed ? 72 : 240 }} transition={{ type: 'spring', damping: 30, stiffness: 320 }}
        className="hidden lg:block h-full shrink-0 z-20">
        <NavBody collapsed={collapsed} />
      </motion.aside>
      <AnimatePresence>
        {drawerOpen && (
          <motion.div className="lg:hidden fixed inset-0 z-[70]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-midnight/60" onClick={() => setDrawerOpen(false)} />
            <motion.div initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }} transition={{ type: 'spring', damping: 30, stiffness: 300 }} className="absolute left-0 top-0 h-full w-[280px] max-w-[85vw]">
              <NavBody collapsed={false} mobile />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
