export type RoleName = 'super_admin' | 'placement_director' | 'department_tpo' | 'corporate_recruiter' | 'student_coordinator' | 'department_faculty' | 'student';

export interface AuthUser {
  id: number;
  email: string;
  fullName: string;
  role: RoleName;
  roleLabel: string;
  departmentId: number | null;
  departmentName: string | null;
  departmentCode: string | null;
  companyId: number | null;
  companyName: string | null;
  designation: string;
  employeeId: string | null;
  status: 'active' | 'disabled';
  mustChangePassword: boolean;
  permissions: string[];
  lastLoginAt: string | null;
  lockedNow?: boolean;
  createdAt?: string;
}

export interface Lookups {
  departments?: { id: number; code: string; label: string }[];
  companies?: { id: number; label: string }[];
  students?: { id: number; label: string; departmentId: number }[];
  vacancies?: { id: number; label: string; companyId: number; status: string }[];
  coordinators?: { id: number; label: string }[];
}

export type Row = Record<string, any>;
export interface Page<T = Row> { items: T[]; total: number; page: number; pageSize: number }

export type ModuleId =
  | 'dashboard' | 'user-roles' | 'students' | 'academic-departments' | 'companies' | 'vacancies'
  | 'opportunity-import' | 'vacancy-verification' | 'company-outreach' | 'recruitment-drives'
  | 'application-tracking' | 'internships' | 'placements' | 'analytics' | 'reports-export'
  | 'notifications' | 'documents' | 'audit-logs' | 'security-privacy' | 'system-settings';
