import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { notificationsApi } from '../api/notifications';
import { NotificationItem } from '../types';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import { Bell, Check, CheckCheck, ExternalLink, Calendar } from 'lucide-react';

export const NotificationsPage: React.FC = () => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotifications = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await notificationsApi.getNotifications();
      setNotifications(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch notifications.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleMarkAsRead = async (id: number) => {
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch (err) {
      console.error(err);
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="page-container animate-fade-in" style={{ maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.85rem', marginBottom: '0.35rem' }}>Notifications Center</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Real-time status alerts and assignment updates for your grievances
          </p>
        </div>

        {unreadCount > 0 && (
          <button onClick={handleMarkAllAsRead} className="btn btn-secondary btn-sm">
            <CheckCheck size={16} /> Mark All as Read
          </button>
        )}
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading notifications..." />
      ) : error ? (
        <ErrorMessage message={error} onRetry={fetchNotifications} />
      ) : notifications.length === 0 ? (
        <EmptyState
          title="No Notifications"
          message="You're all caught up! You'll receive updates here when your grievance status changes."
          icon={<Bell size={44} color="#64748b" />}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {notifications.map((notif) => {
            const dateStr = new Date(notif.created_at).toLocaleString('en-IN', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <div
                key={notif.id}
                className="glass-card"
                style={{
                  padding: '1.25rem',
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  borderLeft: notif.is_read ? '1px solid var(--border-color)' : '3px solid var(--color-primary)',
                  background: notif.is_read ? 'var(--bg-card)' : 'rgba(59, 130, 246, 0.08)',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.95rem', color: 'var(--text-main)' }}>{notif.title}</h4>
                    {!notif.is_read && (
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6' }} />
                    )}
                  </div>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                    {notif.message}
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <Calendar size={12} />
                      <span>{dateStr}</span>
                    </div>

                    {notif.complaint_id && (
                      <Link
                        to={`/complaints/${notif.complaint_id}`}
                        style={{ color: 'var(--color-primary)', display: 'flex', alignItems: 'center', gap: '0.25rem', textDecoration: 'none', fontWeight: 600 }}
                      >
                        View Grievance <ExternalLink size={12} />
                      </Link>
                    )}
                  </div>
                </div>

                {!notif.is_read && (
                  <button
                    onClick={() => handleMarkAsRead(notif.id)}
                    className="btn btn-secondary btn-sm"
                    title="Mark as Read"
                    style={{ padding: '0.3rem 0.5rem' }}
                  >
                    <Check size={14} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
