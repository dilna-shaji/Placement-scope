import { cn } from '../../lib/format';

/** Ambient animated background: gradient mesh + blurred orbs + subtle grid. Pure CSS, respects reduced motion. */
export function AnimatedBackground({ variant = 'dark', className }: { variant?: 'dark' | 'light'; className?: string }) {
  const dark = variant === 'dark';
  return (
    <div aria-hidden className={cn('absolute inset-0 overflow-hidden pointer-events-none', className)}>
      <div className={cn('absolute inset-0 mesh', dark
        ? 'bg-[linear-gradient(120deg,#17182F,#2a2570_35%,#17182F_60%,#1c4f6b)]'
        : 'bg-[linear-gradient(120deg,#f6f5fb,#ece8ff_40%,#e3f7f7_70%,#f6f5fb)]')} />
      <div className="orb-a absolute -top-24 -left-16 w-[420px] h-[420px] rounded-full blur-3xl bg-violet/40" />
      <div className="orb-b absolute top-1/3 -right-24 w-[380px] h-[380px] rounded-full blur-3xl bg-aqua/30" />
      <div className="orb-c absolute -bottom-32 left-1/3 w-[420px] h-[420px] rounded-full blur-3xl bg-coral/25" />
      <div className={cn('absolute inset-0', dark ? 'grid-pattern' : 'grid-pattern-dark')} />
      <div className="floaty absolute bottom-10 right-1/4 w-14 h-14 rounded-2xl border border-white/20 bg-white/5 backdrop-blur-sm rotate-12" />
      <div className="floaty absolute top-24 left-1/3 w-8 h-8 rounded-full border border-white/20 bg-white/5" style={{ animationDuration: '22s' }} />
    </div>
  );
}
