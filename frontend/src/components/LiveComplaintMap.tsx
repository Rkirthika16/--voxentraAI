import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Complaint } from '../types';
import { Link } from 'react-router-dom';
import {
  MapPin,
  Filter,
  Layers,
  Search,
  Maximize2,
  RefreshCw,
  Droplets,
  Zap,
  Car,
  Trash2,
  Waves,
  Sun,
  ShieldAlert,
  HelpCircle,
  ExternalLink,
  Flame,
  CheckCircle2,
  Clock
} from 'lucide-react';

interface LiveComplaintMapProps {
  complaints: Complaint[];
  height?: string;
  selectedComplaintId?: number | null;
  onSelectComplaint?: (complaint: Complaint) => void;
  showFilters?: boolean;
  interactive?: boolean;
  centerCoordinates?: [number, number];
  zoomLevel?: number;
}

// Map department/category to custom colors and Lucide icons
export const CATEGORY_CONFIG: Record<
  string,
  { color: string; bg: string; border: string; label: string; icon: string }
> = {
  Water: { color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.2)', border: '#0284c7', label: 'Water Supply', icon: '💧' },
  Electricity: { color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.2)', border: '#d97706', label: 'Electricity & Power', icon: '⚡' },
  Roads: { color: '#fb923c', bg: 'rgba(251, 146, 60, 0.2)', border: '#ea580c', label: 'Roads & Transport', icon: '🛣️' },
  'Sanitation/Garbage': { color: '#34d399', bg: 'rgba(52, 211, 153, 0.2)', border: '#059669', label: 'Sanitation', icon: '🗑️' },
  Drainage: { color: '#22d3ee', bg: 'rgba(34, 211, 238, 0.2)', border: '#0891b2', label: 'Drainage', icon: '🌊' },
  Streetlights: { color: '#c084fc', bg: 'rgba(192, 132, 252, 0.2)', border: '#9333ea', label: 'Streetlights', icon: '💡' },
  'Public Safety': { color: '#f87171', bg: 'rgba(248, 113, 113, 0.2)', border: '#dc2626', label: 'Public Safety', icon: '🚨' },
  Other: { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.2)', border: '#64748b', label: 'General', icon: '🏛️' },
};

export const LiveComplaintMap: React.FC<LiveComplaintMapProps> = ({
  complaints,
  height = '500px',
  selectedComplaintId,
  onSelectComplaint,
  showFilters = true,
  interactive = true,
  centerCoordinates = [11.0168, 76.9558], // Coimbatore / Tamil Nadu default
  zoomLevel = 11,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<number, L.Marker>>({});

  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: centerCoordinates,
        zoom: zoomLevel,
        zoomControl: interactive,
        attributionControl: false,
        dragging: interactive,
        touchZoom: interactive,
        scrollWheelZoom: interactive,
      });

      // Dark theme OpenStreetMap tiles
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
      }).addTo(map);

      // Attribution
      L.control
        .attribution({ position: 'bottomright' })
        .addAttribution('&copy; <a href="https://openstreetmap.org">OSM</a> | Voxentra TN GIS')
        .addTo(map);

      mapInstanceRef.current = map;
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Filter complaints
  const filteredComplaints = complaints.filter((c) => {
    if (!c.latitude || !c.longitude) return false;
    const lat = parseFloat(c.latitude);
    const lng = parseFloat(c.longitude);
    if (isNaN(lat) || isNaN(lng)) return false;

    if (selectedCategory !== 'ALL' && c.category !== selectedCategory) return false;
    if (selectedStatus === 'RESOLVED' && c.status !== 'RESOLVED') return false;
    if (selectedStatus === 'ACTIVE' && c.status === 'RESOLVED') return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = c.title.toLowerCase().includes(q);
      const matchNum = c.complaint_number.toLowerCase().includes(q);
      const matchLoc = (c.location || '').toLowerCase().includes(q);
      if (!matchTitle && !matchNum && !matchLoc) return false;
    }

    return true;
  });

  // Render & Update Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear old markers
    Object.values(markersRef.current).forEach((marker) => marker.remove());
    markersRef.current = {};

    const bounds = L.latLngBounds([]);

    filteredComplaints.forEach((c) => {
      const lat = parseFloat(c.latitude!);
      const lng = parseFloat(c.longitude!);
      const config = CATEGORY_CONFIG[c.category] || CATEGORY_CONFIG['Other'];
      const isCritical = c.priority === 'CRITICAL';
      const isSelected = selectedComplaintId === c.id;

      // Custom pulsing HTML Pin Marker
      const customIcon = L.divIcon({
        className: 'custom-map-marker',
        html: `
          <div style="
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            width: ${isSelected ? '38px' : '32px'};
            height: ${isSelected ? '38px' : '32px'};
            background: ${config.color};
            color: #ffffff;
            border-radius: 50%;
            border: 2.5px solid #ffffff;
            box-shadow: 0 4px 14px rgba(0,0,0,0.5), 0 0 12px ${config.color};
            font-size: ${isSelected ? '16px' : '14px'};
            transform: translate(-50%, -50%);
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          ">
            ${config.icon}
            ${
              isCritical
                ? `<span style="
                    position: absolute;
                    inset: -6px;
                    border-radius: 50%;
                    border: 2px solid #ef4444;
                    animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
                  "></span>`
                : ''
            }
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      const marker = L.marker([lat, lng], { icon: customIcon }).addTo(map);

      // Popup Content
      const statusColor =
        c.status === 'RESOLVED'
          ? '#10b981'
          : c.status === 'IN_PROGRESS'
          ? '#f59e0b'
          : c.status === 'ASSIGNED'
          ? '#8b5cf6'
          : '#3b82f6';

      const priorityBg =
        c.priority === 'CRITICAL'
          ? '#ef4444'
          : c.priority === 'HIGH'
          ? '#f97316'
          : c.priority === 'MEDIUM'
          ? '#3b82f6'
          : '#64748b';

      const popupHtml = `
        <div style="font-family: inherit; font-size: 13px; color: #1e293b; min-width: 230px; padding: 4px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-weight: 700; font-size: 11px; background: #e2e8f0; padding: 2px 6px; border-radius: 4px; color: #334155;">
              ${c.complaint_number}
            </span>
            <span style="font-size: 10px; font-weight: 700; color: #ffffff; background: ${priorityBg}; padding: 2px 6px; border-radius: 10px; text-transform: uppercase;">
              ${c.priority}
            </span>
          </div>

          <h4 style="font-size: 14px; font-weight: 700; margin: 0 0 6px 0; line-height: 1.3; color: #0f172a;">
            ${c.title}
          </h4>

          <div style="font-size: 11.5px; color: #475569; margin-bottom: 8px; display: flex; align-items: center; gap: 4px;">
            <span>📍</span> <strong>${c.location || 'Tamil Nadu'}</strong>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-size: 11px;">
            <span style="color: ${config.border}; font-weight: 600;">
              ${c.department_name || config.label}
            </span>
            <span style="color: #ffffff; background: ${statusColor}; padding: 2px 8px; border-radius: 10px; font-weight: 600;">
              ${c.status.replace('_', ' ')}
            </span>
          </div>

          <div style="border-top: 1px solid #e2e8f0; padding-top: 6px; text-align: right;">
            <a href="/complaints/${c.complaint_number}" style="
              font-size: 11px;
              color: #2563eb;
              text-decoration: none;
              font-weight: 600;
              display: inline-flex;
              align-items: center;
              gap: 3px;
            ">
              View Tracking Details ➔
            </a>
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, { maxWidth: 280 });

      marker.on('click', () => {
        if (onSelectComplaint) onSelectComplaint(c);
      });

      markersRef.current[c.id] = marker;
      bounds.extend([lat, lng]);
    });

    // Auto fit bounds if markers exist
    if (filteredComplaints.length > 0 && mapInstanceRef.current && interactive) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [filteredComplaints, selectedComplaintId]);

  // Handle selected complaint zoom
  useEffect(() => {
    if (selectedComplaintId && markersRef.current[selectedComplaintId] && mapInstanceRef.current) {
      const marker = markersRef.current[selectedComplaintId];
      mapInstanceRef.current.setView(marker.getLatLng(), 15, { animate: true });
      marker.openPopup();
    }
  }, [selectedComplaintId]);

  const handleRecenter = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView(centerCoordinates, zoomLevel, { animate: true });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
      {showFilters && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.75rem',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
          }}
        >
          {/* Category Filter Badges */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
            <button
              onClick={() => setSelectedCategory('ALL')}
              style={{
                background: selectedCategory === 'ALL' ? 'var(--color-primary)' : 'var(--bg-input)',
                color: selectedCategory === 'ALL' ? '#ffffff' : 'var(--text-muted)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-full)',
                padding: '0.25rem 0.75rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              All Departments ({complaints.length})
            </button>

            {Object.keys(CATEGORY_CONFIG)
              .filter((k) => k !== 'Other')
              .map((catKey) => {
                const conf = CATEGORY_CONFIG[catKey];
                const count = complaints.filter((c) => c.category === catKey).length;
                const isSelected = selectedCategory === catKey;
                return (
                  <button
                    key={catKey}
                    onClick={() => setSelectedCategory(catKey)}
                    style={{
                      background: isSelected ? conf.color : 'var(--bg-input)',
                      color: isSelected ? '#ffffff' : 'var(--text-main)',
                      border: `1px solid ${isSelected ? conf.border : 'var(--border-color)'}`,
                      borderRadius: 'var(--radius-full)',
                      padding: '0.25rem 0.65rem',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                      transition: 'all 0.2s',
                    }}
                  >
                    <span>{conf.icon}</span>
                    <span>{conf.label}</span>
                    {count > 0 && (
                      <span
                        style={{
                          background: isSelected ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.1)',
                          padding: '0 0.35rem',
                          borderRadius: '10px',
                          fontSize: '0.7rem',
                        }}
                      >
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
          </div>

          {/* Search and Status Bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Search area / landmark..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.35rem 0.65rem 0.35rem 1.85rem',
                  fontSize: '0.8rem',
                  color: 'var(--text-main)',
                  width: '180px',
                }}
              />
              <Search
                size={13}
                style={{ position: 'absolute', left: '0.6rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
              />
            </div>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.35rem 0.65rem',
                fontSize: '0.8rem',
                color: 'var(--text-main)',
              }}
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active (Unresolved)</option>
              <option value="RESOLVED">Resolved Only</option>
            </select>

            <button
              onClick={handleRecenter}
              title="Recenter Map"
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.4rem 0.6rem',
                color: 'var(--text-main)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                fontSize: '0.8rem',
              }}
            >
              <RefreshCw size={13} /> Reset View
            </button>
          </div>
        </div>
      )}

      {/* Map Element Container */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: height,
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
          border: '1px solid var(--border-color)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.25)',
        }}
      >
        <div ref={mapContainerRef} style={{ width: '100%', height: '100%', zIndex: 1 }} />

        {/* Live Map Legend Overlay */}
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '12px',
            zIndex: 10,
            background: 'rgba(15, 23, 42, 0.88)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: 'var(--radius-md)',
            padding: '0.6rem 0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.85rem',
            fontSize: '0.75rem',
            color: '#e2e8f0',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 700 }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34d399', display: 'inline-block', boxShadow: '0 0 8px #34d399' }}></span>
            <span>Live Tamil Nadu GIS</span>
          </div>
          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span>Showing:</span>
            <strong style={{ color: '#60a5fa' }}>{filteredComplaints.length}</strong>
            <span>Active Pins</span>
          </div>
        </div>
      </div>
    </div>
  );
};
