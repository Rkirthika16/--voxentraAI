import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { ProtectedRoute } from './components/ProtectedRoute';

// Pages
import { LandingPage } from './pages/LandingPage';
import { TollFreeHelplinePage } from './pages/TollFreeHelplinePage';
import { LiveTwoWayIVRPage } from './pages/LiveTwoWayIVRPage';
import { LiveMapPage } from './pages/LiveMapPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { CitizenDashboard } from './pages/CitizenDashboard';
import { SubmitComplaint } from './pages/SubmitComplaint';
import { VoiceAssistantPage } from './pages/VoiceAssistantPage';
import { VoiceComplaint } from './pages/VoiceComplaint';
import { TextComplaint } from './pages/TextComplaint';
import { AIAssistantPage } from './pages/AIAssistantPage';
import { ComplaintTracking } from './pages/ComplaintTracking';
import { ComplaintHistory } from './pages/ComplaintHistory';
import { ComplaintDetails } from './pages/ComplaintDetails';
import { OfficerDashboard } from './pages/OfficerDashboard';
import { AdminDashboard } from './pages/AdminDashboard';
import { NotificationsPage } from './pages/NotificationsPage';
import { ProfilePage } from './pages/ProfilePage';
import { VoiceAssistantWidget } from './components/VoiceAssistantWidget';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
          <Navbar />

          <div className="app-layout">
            <Sidebar />

            <main className="main-content">
              <Routes>
                {/* Friction-Free Public Routes (No Login Required) */}
                <Route path="/" element={<LandingPage />} />
                <Route path="/new-ivr" element={<LiveTwoWayIVRPage />} />
                <Route path="/live-ivr" element={<LiveTwoWayIVRPage />} />
                <Route path="/ivr" element={<TollFreeHelplinePage />} />
                <Route path="/toll-free" element={<TollFreeHelplinePage />} />
                <Route path="/helpline" element={<TollFreeHelplinePage />} />

                <Route path="/voice-assistant" element={<VoiceAssistantPage />} />
                <Route path="/map" element={<LiveMapPage />} />
                <Route path="/assistant" element={<AIAssistantPage />} />
                <Route path="/submit" element={<SubmitComplaint />} />
                <Route
                  path="/voice-complaint"
                  element={
                    <div className="page-container" style={{ maxWidth: '850px' }}>
                      <h1 style={{ fontSize: '1.85rem', marginBottom: '1.5rem', textAlign: 'center' }}>Voice Complaint Submission</h1>
                      <VoiceComplaint />
                    </div>
                  }
                />
                <Route
                  path="/text-complaint"
                  element={
                    <div className="page-container" style={{ maxWidth: '850px' }}>
                      <h1 style={{ fontSize: '1.85rem', marginBottom: '1.5rem', textAlign: 'center' }}>Text Complaint Submission</h1>
                      <TextComplaint />
                    </div>
                  }
                />
                <Route path="/track" element={<ComplaintTracking />} />
                <Route path="/complaints/:id" element={<ComplaintDetails />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />

                {/* Authenticated Dashboard Routes */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <CitizenDashboard />
                    </ProtectedRoute>
                  }
                />

                {/* Officer Routes */}
                <Route
                  path="/officer"
                  element={
                    <ProtectedRoute allowedRoles={['OFFICER', 'ADMIN']}>
                      <OfficerDashboard />
                    </ProtectedRoute>
                  }
                />

                {/* Admin Routes */}
                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute allowedRoles={['ADMIN']}>
                      <AdminDashboard />
                    </ProtectedRoute>
                  }
                />

                {/* Shared Authenticated Routes */}
                <Route
                  path="/history"
                  element={
                    <ProtectedRoute>
                      <ComplaintHistory />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/notifications"
                  element={
                    <ProtectedRoute>
                      <NotificationsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute>
                      <ProfilePage />
                    </ProtectedRoute>
                  }
                />

                {/* Catch-all */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
          </div>

          {/* Global Floating AI Voice & Talking Assistant Widget */}
          <VoiceAssistantWidget />
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
};
