import { Route, Routes } from 'react-router-dom';
import ProtectedRoute from './routes/ProtectedRoute';
import PublicOnlyRoute from './routes/PublicOnlyRoute';
import AuthLayout from './layouts/AuthLayout';
import DashboardLayout from './layouts/DashboardLayout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import CreateBusinessPage from './pages/CreateBusinessPage';
import BusinessDetailsPage from './pages/BusinessDetailsPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import TeamPage from './pages/TeamPage';
import InvitationsPage from './pages/InvitationsPage';
import ProfilePage from './pages/ProfilePage';
import NotFoundPage from './pages/NotFoundPage';
import AgentManagementPage from './pages/AgentManagementPage';

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/businesses/new" element={<CreateBusinessPage />} />
          <Route path="/businesses/:id" element={<BusinessDetailsPage />} />
          <Route path="/knowledge" element={<KnowledgeBasePage />} />
          <Route path="/agents" element={<AgentManagementPage />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/invitations" element={<InvitationsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
