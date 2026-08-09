'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { User } from '@/lib/types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  isAuthModalOpen: boolean;
  setIsAuthModalOpen: (open: boolean) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  useEffect(() => {
    async function loadUser() {
      try {
        const token = localStorage.getItem('token');
        if (token) {
          const currentUser = await api.getMe();
          setUser(currentUser);
        }
      } catch (err) {
        console.warn('Failed to load user session:', err);
        api.logout();
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  const login = async (email: string, password: string) => {
    await api.login(email, password);
    const currentUser = await api.getMe();
    setUser(currentUser);
    setIsAuthModalOpen(false);
  };

  const register = async (email: string, password: string, fullName?: string) => {
    await api.register({ email, password, full_name: fullName });
    await login(email, password);
  };

  const logout = () => {
    api.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        isAuthModalOpen,
        setIsAuthModalOpen,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
