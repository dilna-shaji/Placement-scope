import { GraduationCap, Users, Building2, Briefcase, CalendarDays, Target, Clock, Award, CheckCircle2 } from 'lucide-react';
import { StatCard } from '../ui/kit';
import type { Row } from '../../types';

export const STAGES = ['Applied', 'Shortlisted', 'Aptitude', 'Technical', 'HR', 'Selected', 'Rejected', 'Withdrawn'];
export const TIERS = ['Super Dream (>20 LPA)', 'Dream (12-20 LPA)', 'Core Corporate', 'Mass Recruiter'];
export const icons = { GraduationCap, Users, Building2, Briefcase, CalendarDays, Target, Clock, Award, CheckCircle2 };

export function StatsRow({ stats }: { stats: { label: string; value: number; hint?: string; tone?: string; suffix?: string; icon?: React.ElementType }[] }) {
  return <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">{stats.map((s, i) => <StatCard key={s.label} index={i} {...s} />)}</div>;
}
export const count = (rows: Row[], f: (r: Row) => boolean) => rows.filter(f).length;
