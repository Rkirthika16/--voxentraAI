import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Complaint } from '../types';
import {
  TN_38_DISTRICTS,
  TN_STATE_CENTER,
  TN_STATE_ZOOM,
  OSM_TILE_PROVIDERS,
  TNDistrict
} from '../data/tnDistricts';
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
  Clock,
  Compass,
  Building2,
  Navigation,
  Globe
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

// Map department/category to custom colors and icons
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
  height = '560px',
  selectedComplaintId,
  onSelectComplaint,
  showFilters = true,
  interactive = true,
  centerCoordinates = [11.0168, 76.9558], // Default Coimbatore
  zoomLevel = 11,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<Record<number, L.Marker>>({});
  const districtMarkersRef = useRef<L.Marker[]>([]);

  const [selectedDistrict, setSelectedDistrict] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeTileId, setActiveTileId] = useState<string>('carto-voyager');
  const [showDistrictHubs, setShowDistrictHubs] = useState<boolean>(false);

  // Initialize Leaflet Map with OpenStreetMap Layer
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

      const initialProvider = OSM_TILE_PROVIDERS.find((p) => p.id === activeTileId) || OSM_TILE_PROVIDERS[0];
      const tileLayer = L.tileLayer(initialProvider.url, {
        maxZoom: initialProvider.maxZoom,
        subdomains: 'abcd',
      }).addTo(map);

      tileLayerRef.current = tileLayer;

      // Attribution
      L.control
        .attribution({ position: 'bottomright' })
        .addAttribution('&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> | Tamil Nadu 38-District GIS')
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

  // Update Tile Provider when user switches style
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const provider = OSM_TILE_PROVIDERS.find((p) => p.id === activeTileId) || OSM_TILE_PROVIDERS[0];
    if (tileLayerRef.current) {
      tileLayerRef.current.remove();
    }

    const newLayer = L.tileLayer(provider.url, {
      maxZoom: provider.maxZoom,
      subdomains: 'abcd',
    }).addTo(map);

    tileLayerRef.current = newLayer;
  }, [activeTileId]);

  // Handle District Change & FlyTo
  const handleDistrictChange = (districtId: string) => {
    setSelectedDistrict(districtId);
    const map = mapInstanceRef.current;
    if (!map) return;

    if (districtId === 'ALL') {
      map.flyTo(TN_STATE_CENTER, TN_STATE_ZOOM, { duration: 1.2 });
    } else {
      const dist = TN_38_DISTRICTS.find((d) => d.id === districtId);
      if (dist) {
        map.flyTo(dist.center, dist.zoom, { duration: 1.2 });
      }
    }
  };

  // Render 38 District Hub Markers if toggled
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing district hubs
    districtMarkersRef.current.forEach((m) => m.remove());
    districtMarkersRef.current = [];

    if (showDistrictHubs) {
      TN_38_DISTRICTS.forEach((dist) => {
        const hubIcon = L.divIcon({
          className: 'custom-district-hub-marker',
          html: `
            <div style="
              display: inline-flex;
              align-items: center;
              gap: 4px;
              background: rgba(15, 23, 42, 0.92);
              color: #38bdf8;
              border: 1.5px solid #38bdf8;
              border-radius: 12px;
              padding: 2px 8px;
              font-size: 11px;
              font-weight: 700;
              box-shadow: 0 4px 12px rgba(0,0,0,0.5);
              white-space: nowrap;
              transform: translate(-50%, -50%);
              cursor: pointer;
            ">
              <span>🏛️</span>
              <span>${dist.name}</span>
            </div>
          `,
          iconSize: [80, 24],
          iconAnchor: [40, 12],
        });

        const marker = L.marker(dist.center, { icon: hubIcon }).addTo(map);
        marker.bindPopup(`
          <div style="font-family: inherit; font-size: 13px; padding: 4px; color: #0f172a;">
            <div style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Tamil Nadu District HQ</div>
            <h4 style="margin: 2px 0 6px 0; font-size: 15px; color: #0284c7;">${dist.name} (${dist.name_ta})</h4>
            <div style="font-size: 12px; color: #334155; margin-bottom: 6px;"><strong>Region:</strong> ${dist.region}</div>
            <div style="font-size: 12px; color: #334155; margin-bottom: 8px;"><strong>Headquarters:</strong> ${dist.headquarters}</div>
            <div style="font-size: 11px; color: #64748b;">GPS: ${dist.center[0].toFixed(4)}° N, ${dist.center[1].toFixed(4)}° E</div>
          </div>
        `);

        marker.on('click', () => {
          handleDistrictChange(dist.id);
        });

        districtMarkersRef.current.push(marker);
      });
    }
  }, [showDistrictHubs]);

  // Filter complaints
  const filteredComplaints = complaints.filter((c) => {
    if (!c.latitude || !c.longitude) return false;
    const lat = parseFloat(c.latitude);
    const lng = parseFloat(c.longitude);
    if (isNaN(lat) || isNaN(lng)) return false;

    // Filter by category
    if (selectedCategory !== 'ALL' && c.category !== selectedCategory) return false;
    // Filter by status
    if (selectedStatus === 'RESOLVED' && c.status !== 'RESOLVED') return false;
    if (selectedStatus === 'ACTIVE' && c.status === 'RESOLVED') return false;

    // Filter by district if selected
    if (selectedDistrict !== 'ALL') {
      const dist = TN_38_DISTRICTS.find((d) => d.id === selectedDistrict);
      if (dist) {
        const loc = (c.location || '').toLowerCase();
        const distName = dist.name.toLowerCase();
        const matchDistrict = loc.includes(distName);
        if (!matchDistrict) {
          // Check proximity to district center (< 45km)
          const distKm = Math.hypot(lat - dist.center[0], lng - dist.center[1]) * 111;
          if (distKm > 45) return false;
        }
      }
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = c.title.toLowerCase().includes(q);
      const matchNum = c.complaint_number.toLowerCase().includes(q);
      const matchLoc = (c.location || '').toLowerCase().includes(q);
      if (!matchTitle && !matchNum && !matchLoc) return false;
    }

    return true;
  });

  // Render & Update Complaint Pin Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear old markers
    Object.values(markersRef.current).forEach((marker) => marker.remove());
    markersRef.current = {};

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
        <div style="font-family: inherit; font-size: 13px; color: #1e293b; min-width: 240px; padding: 4px;">
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
    });
  }, [filteredComplaints, selectedComplaintId]);

  // Handle selected complaint zoom
  useEffect(() => {
    if (selectedComplaintId && markersRef.current[selectedComplaintId] && mapInstanceRef.current) {
      const marker = markersRef.current[selectedComplaintId];
      mapInstanceRef.current.setView(marker.getLatLng(), 15, { animate: true });
      marker.openPopup();
    }
  }, [selectedComplaintId]);

  const handleResetTamilNadu = () => {
    setSelectedDistrict('ALL');
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo(TN_STATE_CENTER, TN_STATE_ZOOM, { duration: 1.2 });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
      {showFilters && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            padding: '0.85rem 1.1rem',
            borderRadius: 'var(--radius-md)',
          }}
        >
          {/* Top Row: 38 Districts Selector & Map Layer Switcher */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            {/* 38 Districts Dropdown & Quick Hub Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 600, fontSize: '0.82rem', color: '#38bdf8' }}>
                <Compass size={15} /> Select District:
              </div>

              <select
                value={selectedDistrict}
                onChange={(e) => handleDistrictChange(e.target.value)}
                style={{
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  color: 'var(--text-main)',
                  cursor: 'pointer',
                  minWidth: '220px',
                }}
              >
                <option value="ALL">🌟 All 38 Tamil Nadu Districts (Statewide)</option>
                <optgroup label="Kongu / Western Tamil Nadu">
                  {TN_38_DISTRICTS.filter((d) => d.region === 'Kongu / West').map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.name_ta})
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Southern Tamil Nadu / Pandiya">
                  {TN_38_DISTRICTS.filter((d) => d.region === 'South / Pandiya').map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.name_ta})
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Northern Tamil Nadu / Chennai Metro">
                  {TN_38_DISTRICTS.filter((d) => d.region === 'North / Chennai').map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.name_ta})
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Central / Cauvery Delta">
                  {TN_38_DISTRICTS.filter((d) => d.region === 'Central / Delta').map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.name_ta})
                    </option>
                  ))}
                </optgroup>
              </select>

              <button
                onClick={() => setShowDistrictHubs(!showDistrictHubs)}
                style={{
                  background: showDistrictHubs ? 'rgba(56, 189, 248, 0.2)' : 'var(--bg-input)',
                  color: showDistrictHubs ? '#38bdf8' : 'var(--text-muted)',
                  border: `1px solid ${showDistrictHubs ? '#38bdf8' : 'var(--border-color)'}`,
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  transition: 'all 0.2s',
                }}
              >
                <Building2 size={13} /> {showDistrictHubs ? 'Hide District HQ' : 'Show 38 District HQ'}
              </button>

              <button
                onClick={handleResetTamilNadu}
                style={{
                  background: 'var(--bg-input)',
                  color: 'var(--text-main)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.35rem 0.65rem',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                <Globe size={13} /> Entire Tamil Nadu
              </button>
            </div>

            {/* Tile Layer Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Layers size={13} /> Layer:
              </div>
              <select
                value={activeTileId}
                onChange={(e) => setActiveTileId(e.target.value)}
                style={{
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.3rem 0.6rem',
                  fontSize: '0.78rem',
                  color: 'var(--text-main)',
                }}
              >
                {OSM_TILE_PROVIDERS.map((tp) => (
                  <option key={tp.id} value={tp.id}>
                    {tp.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Bottom Row: Category Pills & Status Filter */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.65rem' }}>
            {/* Category Filter Badges */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', alignItems: 'center' }}>
              <button
                onClick={() => setSelectedCategory('ALL')}
                style={{
                  background: selectedCategory === 'ALL' ? 'var(--color-primary)' : 'var(--bg-input)',
                  color: selectedCategory === 'ALL' ? '#ffffff' : 'var(--text-muted)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-full)',
                  padding: '0.25rem 0.7rem',
                  fontSize: '0.78rem',
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
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.76rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
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
                            fontSize: '0.68rem',
                          }}
                        >
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
            </div>

            {/* Search and Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  placeholder="Search village / area / complaint..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.35rem 0.65rem 0.35rem 1.85rem',
                    fontSize: '0.8rem',
                    color: 'var(--text-main)',
                    width: '200px',
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
            </div>
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
            background: 'rgba(15, 23, 42, 0.90)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: 'var(--radius-md)',
            padding: '0.55rem 0.85rem',
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
            <span>OpenStreetMap Tamil Nadu (38 Districts)</span>
          </div>
          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span>Active Pins:</span>
            <strong style={{ color: '#60a5fa' }}>{filteredComplaints.length}</strong>
          </div>
          {selectedDistrict !== 'ALL' && (
            <>
              <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                {TN_38_DISTRICTS.find((d) => d.id === selectedDistrict)?.name}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
