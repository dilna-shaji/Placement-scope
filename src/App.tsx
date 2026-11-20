import type React from 'react';
import { Suspense, lazy, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { UIProvider, useUI } from './context/UIContext';
import { AppShell } from './components/layout/AppShell';
import { LoginScreen } from './components/auth/LoginScreen';
import { RequestAccountScreen } from './components/auth/RequestAccountScreen';
import { ForceChangePasswordScreen, ForgotPasswordScreen, ResetPasswordScreen } from './components/auth/PasswordScreens';
import { Empty, Skeleton } from './components/ui/kit';
import { allowedModules } from './navigation';
import type { ModuleId } from './types';

const L = {
  dashboard: lazy(() => import('./components/modules/1_Dashboard/DashboardView')),
  'user-roles': lazy(() => import('./components/modules/2_UserRoleManagement/UserRoleView')),
  students: lazy(() => import('./components/modules/3_StudentManagement/StudentManagementView')),
  'academic-departments': lazy(() => import('./components/modules/4_AcademicDepartment/AcademicDepartmentView')),
  companies: lazy(() => import('./components/modules/5_CompanyManagement/CompanyManagementView')),
  vacancies: lazy(() => import('./components/modules/6_VacancyOpportunity/VacancyView')),
  'opportunity-import': lazy(() => import('./components/modules/7_OpportunityCollection/OpportunityImportView')),
  'vacancy-verification': lazy(() => import('./components/modules/8_VacancyVerification/VerificationApprovalView')),
  'company-outreach': lazy(() => import('./components/modules/9_CompanyOutreach/CompanyOutreachView')),
  'recruitment-drives': lazy(() => import('./components/modules/10_RecruitmentDrive/RecruitmentDriveView')),
  'application-tracking': lazy(() => import('./components/modules/11_StudentApplication/ApplicationTrackingView')),
  internships: lazy(() => import('./components/modules/12_InternshipManagement/InternshipManagementView')),
  placements: lazy(() => import('./components/modules/13_PlacementManagement/PlacementManagementView')),
  analytics: lazy(() => import('./components/modules/14_AnalyticsInsights/AnalyticsView')),
  'reports-export': lazy(() => import('./components/modules/15_ReportsExport/ReportsExportView')),
  notifications: lazy(() => import('./components/modules/16_Notifications/NotificationsView')),
  documents: lazy(() => import('./components/modules/17_DocumentCertificate/DocumentCertificateView')),
  'audit-logs': lazy(() => import('./components/modules/18_ActivityLogs/ActivityAuditView')),
  'security-privacy': lazy(() => import('./components/modules/19_SecurityPrivacy/SecurityPrivacyView')),
  'system-settings': lazy(() => import('./components/modules/20_SystemSettings/SystemSettingsView')),
} as Record<ModuleId, React.LazyExoticComponent<React.ComponentType>>;

function Workspace() {
  const { user } = useAuth();
  const { route, navigate } = useUI();
  const allowed = allowedModules(user!);
  const ok = allowed.some((m) => m.id === route);
  const Page = ok ? L[route as ModuleId] : null;
  return (
    <AppShell>
      <Suspense fallback={<div className="space-y-5"><Skeleton className="h-24" /><div className="grid grid-cols-4 gap-5"><Skeleton className="h-36" /><Skeleton className="h-36" /><Skeleton className="h-36" /><Skeleton className="h-36" /></div></div>}>
        {Page ? <Page /> : (
          <Empty title="You don’t have access to this module" text="Your role is not permitted to open this page. The server enforces this too." action={<button className="font-semibold text-indigo" onClick={() => navigate('dashboard')}>Back to dashboard</button>} />
        )}
      </Suspense>
    </AppShell>
  );
}

function Gate() {
  const { user, loading } = useAuth();
  const [screen, setScreen] = useState<'login' | 'request' | 'forgot' | 'reset'>(() => new URLSearchParams(window.location.search).get('reset_token') ? 'reset' : 'login');
  const token = new URLSearchParams(window.location.search).get('reset_token') || '';

  if (loading) return <div className="h-screen grid place-items-center bg-canvas"><Loader2 className="w-8 h-8 animate-spin text-violet" /></div>;
  if (!user) {
    if (screen === 'request') return <RequestAccountScreen back={() => setScreen('login')} />;
    if (screen === 'forgot') return <ForgotPasswordScreen back={() => setScreen('login')} />;
    if (screen === 'reset') return <ResetPasswordScreen token={token} done={() => { window.history.replaceState({}, '', '/'); setScreen('login'); }} />;
    return <LoginScreen go={setScreen} />;
  }
  if (user.mustChangePassword) return <ForceChangePasswordScreen />;
  return <Workspace />;
}

export default function App() {
  return (
    <AuthProvider>
      <UIProvider>
        <Gate />
      </UIProvider>
    </AuthProvider>
  );
}
