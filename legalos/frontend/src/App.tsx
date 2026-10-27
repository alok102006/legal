import React from 'react';
import { Link, Navigate, Outlet, Route, Routes, useLocation, type Location } from 'react-router-dom';
import { useSession } from '@/lib/auth/session';
import { AppShell } from '@/app/AppShell';
import { LoginPage, RegisterPage } from '@/features/auth/AuthPages';
import { OnboardingPage } from '@/features/onboarding/OnboardingPage';
import { HomePage } from '@/features/home/HomePage';
import { ContractsPage } from '@/features/contracts/ContractsPage';
import { ContractPage } from '@/features/contracts/ContractPage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { CompliancePage } from '@/features/compliance/CompliancePage';
import { VendorsPage } from '@/features/vendors/VendorsPage';
import { VendorPage } from '@/features/vendors/VendorPage';
import { NoticesPage } from '@/features/notices/NoticesPage';
import { NoticePage } from '@/features/notices/NoticePage';
import { DocumentsPage } from '@/features/documents/DocumentsPage';
import { DocumentPage } from '@/features/documents/DocumentPage';
import { EmptyState, Spinner } from '@/ui/primitives';


const RequireAuth: React.FC = () => {
  const { status, user, org } = useSession();
  const location = useLocation();

  if (status === 'loading') {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading LegalOS" /></div>;
  }
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (!org?.onboarding_completed && !user?.is_demo && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }
  return <Outlet />;
};

const NotFound: React.FC = () => (
  <EmptyState title="Page not found" description="The page you are looking for doesn't exist or has moved."
    action={<Link to="/" className="inline-flex min-h-[44px] items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-on">Go to Home</Link>} />
);

export default function App() {
  const location = useLocation();
  const background = (location.state as { background?: Location } | null)?.background;
  return (
    <>
    <Routes location={background ?? location}>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<RequireAuth />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="contracts" element={<ContractsPage />} />
          <Route path="contracts/:id" element={<ContractPage />} />
          <Route path="vendors" element={<VendorsPage />} />
          <Route path="vendors/:id" element={<VendorPage />} />
          <Route path="notices" element={<NoticesPage />} />
          <Route path="notices/:id" element={<NoticePage />} />
          <Route path="compliance" element={<CompliancePage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="documents/c/:convId" element={<DocumentsPage />} />
          <Route path="documents/:id" element={<DocumentPage />} />
          <Route path="knowledge" element={<Navigate to="/documents" replace />} />
          <Route path="settings" element={<><HomePage /><SettingsPage /></>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
    {background && (
      <Routes>
        <Route element={<RequireAuth />}><Route path="/settings" element={<SettingsPage />} /></Route>
      </Routes>
    )}
    </>
  );
}
