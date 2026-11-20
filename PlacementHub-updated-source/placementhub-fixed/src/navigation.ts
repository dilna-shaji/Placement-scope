import {
  LayoutDashboard, Users2, GraduationCap, Building2, Briefcase, FileSpreadsheet, CheckCheck, Send, CalendarDays,
  Target, Clock, Award, BarChart3, FileText, Bell, FileCheck2, ScrollText, ShieldAlert, Settings, Library,
} from 'lucide-react';
import type { ElementType } from 'react';
import type { AuthUser, ModuleId } from './types';

export interface ModuleDef { id: ModuleId; label: string; icon: ElementType; permission: string; section: string; description: string }

/** Single catalogue of the 20 modules and the permission each one needs.
 *  Mirrors MODULE_PERMISSION in backend/app/permissions.py. The backend is still the authority. */
export const MODULES: ModuleDef[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, permission: 'dashboard:view', section: 'Overview', description: 'Your role-specific workspace.' },
  { id: 'analytics', label: 'Analytics & Insights', icon: BarChart3, permission: 'analytics:view', section: 'Overview', description: 'Placement intelligence from live records.' },
  { id: 'students', label: 'Students', icon: GraduationCap, permission: 'students:read', section: 'People', description: 'Student profiles and placement status.' },
  { id: 'academic-departments', label: 'Academic & Departments', icon: Library, permission: 'departments:read', section: 'People', description: 'Specialisations and department performance.' },
  { id: 'companies', label: 'Companies', icon: Building2, permission: 'companies:read', section: 'Corporate', description: 'Recruiter directory and MoUs.' },
  { id: 'vacancies', label: 'Vacancies', icon: Briefcase, permission: 'vacancies:read', section: 'Corporate', description: 'Opportunities and job notification forms.' },
  { id: 'opportunity-import', label: 'Data Import', icon: FileSpreadsheet, permission: 'vacancies:import', section: 'Corporate', description: 'Bulk-collect opportunities from CSV.' },
  { id: 'vacancy-verification', label: 'Vacancy Approvals', icon: CheckCheck, permission: 'vacancies:verify', section: 'Corporate', description: 'Verify vacancies before students see them.' },
  { id: 'company-outreach', label: 'Company Outreach', icon: Send, permission: 'outreach:read', section: 'Corporate', description: 'Communication log and follow-ups.' },
  { id: 'recruitment-drives', label: 'Recruitment Drives', icon: CalendarDays, permission: 'drives:read', section: 'Recruitment', description: 'Schedule and monitor campus drives.' },
  { id: 'application-tracking', label: 'Applications', icon: Target, permission: 'applications:read', section: 'Recruitment', description: 'Selection pipeline by stage.' },
  { id: 'internships', label: 'Internships', icon: Clock, permission: 'internships:read', section: 'Recruitment', description: 'Internship progress and PPOs.' },
  { id: 'placements', label: 'Placements', icon: Award, permission: 'placements:read', section: 'Recruitment', description: 'Offers, packages and verification.' },
  { id: 'reports-export', label: 'Reports & Export', icon: FileText, permission: 'reports:view', section: 'Operations', description: 'CSV and Excel exports.' },
  { id: 'notifications', label: 'Notifications', icon: Bell, permission: 'notifications:read', section: 'Operations', description: 'Inbox and announcements.' },
  { id: 'documents', label: 'Documents', icon: FileCheck2, permission: 'documents:read', section: 'Operations', description: 'Resumes, offer letters and certificates.' },
  { id: 'user-roles', label: 'Users & Roles', icon: Users2, permission: 'users:manage', section: 'Administration', description: 'Accounts, requests and permissions.' },
  { id: 'audit-logs', label: 'Audit Logs', icon: ScrollText, permission: 'audit:view', section: 'Administration', description: 'Every sensitive action, recorded.' },
  { id: 'security-privacy', label: 'Security & Privacy', icon: ShieldAlert, permission: 'security:manage', section: 'Administration', description: 'Sessions, lockouts and policy.' },
  { id: 'system-settings', label: 'System Settings', icon: Settings, permission: 'settings:manage', section: 'Administration', description: 'Institution-wide configuration.' },
];

export const allowedModules = (u: AuthUser) => MODULES.filter((m) => u.permissions.includes(m.permission));
export const moduleById = (id: string) => MODULES.find((m) => m.id === id);
