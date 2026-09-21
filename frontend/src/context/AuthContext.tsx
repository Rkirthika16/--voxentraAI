import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, UserRole, AuthResponse } from '../types';
import { authApi } from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<AuthResponse>;
  register: (data: { full_name: string; email: string; password: string; phone?: string }) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  demoLogin: (role: 'CITIZEN' | 'OFFICER_WATER' | 'OFFICER_ROADS' | 'ADMIN') => Promise<AuthResponse>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('voxentra_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('voxentra_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const verifyAuth = async () => {
      if (token) {
        try {
          const profile = await authApi.getMe();
          setUser(profile);
          localStorage.setItem('voxentra_user', JSON.stringify(profile));
        } catch (err) {
          console.error('Failed to restore session:', err);
          setUser(null);
          setToken(null);
          localStorage.removeItem('voxentra_token');
          localStorage.removeItem('voxentra_user');
        }
      }
      setIsLoading(false);
    };

    verifyAuth();
  }, [token]);

  const login = async (email: string, pass: string): Promise<AuthResponse> => {
    const data = await authApi.login(email, pass);
    localStorage.setItem('voxentra_token', data.access_token);
    setToken(data.access_token);
    const profile: User = {
      id: data.user_id,
      public_id: data.public_id,
      full_name: data.full_name,
      email: data.email,
      role: data.role,
      department_id: data.department_id,
      is_active: true,
      created_at: new Date().toISOString()
    };
    setUser(profile);
    localStorage.setItem('voxentra_user', JSON.stringify(profile));
    return data;
  };

  const register = async (regData: { full_name: string; email: string; password: string; phone?: string }): Promise<AuthResponse> => {
    const data = await authApi.register(regData);
    localStorage.setItem('voxentra_token', data.access_token);
    setToken(data.access_token);
    const profile: User = {
      id: data.user_id,
      public_id: data.public_id,
      full_name: data.full_name,
      email: data.email,
      role: data.role,
      department_id: data.department_id,
      is_active: true,
      created_at: new Date().toISOString()
    };
    setUser(profile);
    localStorage.setItem('voxentra_user', JSON.stringify(profile));
    return data;
  };

  const demoLogin = async (role: 'CITIZEN' | 'OFFICER_WATER' | 'OFFICER_ROADS' | 'ADMIN'): Promise<AuthResponse> => {
    let email = 'citizen@voxentra.tn.gov.in';
    let pass = 'Citizen@123';

    if (role === 'OFFICER_WATER') {
      email = 'officer.water@voxentra.tn.gov.in';
      pass = 'Officer@123';
    } else if (role === 'OFFICER_ROADS') {
      email = 'officer.roads@voxentra.tn.gov.in';
      pass = 'Officer@123';
    } else if (role === 'ADMIN') {
      email = 'admin@voxentra.tn.gov.in';
      pass = 'Admin@123';
    }

    return login(email, pass);
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (e) {
      // Ignore network errors on logout
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem('voxentra_token');
      localStorage.removeItem('voxentra_user');
    }
  };

  const refreshUser = async () => {
    if (token) {
      const profile = await authApi.getMe();
      setUser(profile);
      localStorage.setItem('voxentra_user', JSON.stringify(profile));
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout, refreshUser, demoLogin }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
