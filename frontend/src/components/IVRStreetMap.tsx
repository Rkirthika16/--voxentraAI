import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin, Navigation, Compass, Layers, CheckCircle2, Globe } from 'lucide-react';

interface IVRStreetMapProps {
  latitude?: string | number | null;
  longitude?: string | number | null;
  locationName?: string | null;
  districtArea?: string | null;
  streetName?: string | null;
  landmark?: string | null;
  exactLocation?: string | null;
  category?: string | null;
  height?: string;
}

export const IVRStreetMap: React.FC<IVRStreetMapProps> = ({
  latitude,
  longitude,
  locationName,
  districtArea,
  streetName,
  landmark,
  exactLocation,
  category = 'General Civic',
  height = '280px'
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const circleRef = useRef<L.Circle | null>(null);

  // Default coordinates: Coimbatore (11.0168, 76.9558) or Tamil Nadu center (11.1271, 78.6569)
  const parsedLat = latitude ? parseFloat(String(latitude)) : 11.0168;
  const parsedLon = longitude ? parseFloat(String(longitude)) : 76.9558;
  const hasValidCoords = Boolean(latitude && longitude && !isNaN(parsedLat) && !isNaN(parsedLon));

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [parsedLat, parsedLon],
        zoom: hasValidCoords ? 15 : 11,
        zoomControl: false,
        attributionControl: false,
        dragging: true,
        touchZoom: true,
        scrollWheelZoom: false
      });

      // OpenStreetMap Carto Voyager Tile Layer
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
      }).addTo(map);

      // Add custom zoom controls to top-right
      L.control.zoom({ position: 'topright' }).addTo(map);

      mapInstanceRef.current = map;
    } else {
      const map = mapInstanceRef.current;
      map.setView([parsedLat, parsedLon], hasValidCoords ? 15 : 11);
    }

    return () => {
      // Keep map instance alive across rerenders
    };
  }, []);

  // Update marker and map position whenever coordinates or location details change
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (hasValidCoords) {
      map.flyTo([parsedLat, parsedLon], 15, {
        animate: true,
        duration: 1.2
      });

      // Custom pulsing civic marker HTML icon
      const customIcon = L.divIcon({
        className: 'custom-osm-pin',
        html: `
          <div style="
            position: relative;
            width: 38px;
            height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
          ">
            <div style="
              position: absolute;
              width: 36px;
              height: 36px;
              border-radius: 50%;
              background: rgba(16, 185, 129, 0.35);
              animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
            "></div>
            <div style="
              width: 30px;
              height: 30px;
              border-radius: 50%;
              background: linear-gradient(135deg, #10b981, #059669);
              border: 2px solid #ffffff;
              box-shadow: 0 0 15px rgba(16, 185, 129, 0.8);
              display: flex;
              align-items: center;
              justify-content: center;
              color: white;
              font-weight: bold;
              font-size: 14px;
            ">
              📍
            </div>
          </div>
        `,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        popupAnchor: [0, -20]
      });

      if (markerRef.current) {
        markerRef.current.setLatLng([parsedLat, parsedLon]);
      } else {
        markerRef.current = L.marker([parsedLat, parsedLon], { icon: customIcon }).addTo(map);
      }

      if (circleRef.current) {
        circleRef.current.setLatLng([parsedLat, parsedLon]);
      } else {
        circleRef.current = L.circle([parsedLat, parsedLon], {
          color: '#10b981',
          fillColor: '#10b981',
          fillOpacity: 0.15,
          radius: 120
        }).addTo(map);
      }

      // Popup content
      const popupHtml = `
        <div style="font-family: system-ui, sans-serif; min-width: 180px; padding: 4px; color: #0f172a;">
          <div style="font-weight: 700; font-size: 13px; color: #059669; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
            <span>🗺️ Classified on OpenStreetMap</span>
          </div>
          <div style="font-size: 12px; font-weight: 600; color: #1e293b;">
            ${locationName || districtArea || 'Tamil Nadu'}
          </div>
          ${streetName ? `<div style="font-size: 11px; color: #475569; margin-top: 2px;">🛣️ Street: <b>${streetName}</b></div>` : ''}
          ${landmark ? `<div style="font-size: 11px; color: #475569;">🏛️ Landmark: <b>${landmark}</b></div>` : ''}
          ${exactLocation ? `<div style="font-size: 11px; color: #475569;">📍 Spot: <b>${exactLocation}</b></div>` : ''}
          <div style="font-size: 10px; color: #64748b; margin-top: 4px; border-top: 1px solid #e2e8f0; padding-top: 2px;">
            GPS: ${parsedLat.toFixed(4)}° N, ${parsedLon.toFixed(4)}° E
          </div>
        </div>
      `;
      markerRef.current.bindPopup(popupHtml).openPopup();
    }
  }, [parsedLat, parsedLon, hasValidCoords, locationName, districtArea, streetName, landmark, exactLocation]);

  return (
    <div
      style={{
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        background: 'rgba(15, 23, 42, 0.85)',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Street Map Classification Top Header */}
      <div
        style={{
          padding: '0.6rem 1rem',
          background: 'linear-gradient(90deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9))',
          borderBottom: '1px solid rgba(56, 189, 248, 0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.2)',
              border: '1px solid #10b981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#34d399',
            }}
          >
            <Compass size={14} className="animate-spin" style={{ animationDuration: '8s' }} />
          </div>
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff' }}>
              OpenStreetMap GIS Location Classifier
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
              • Tamil Nadu 38-District Street Map Integration
            </span>
          </div>
        </div>

        {hasValidCoords ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: '#34d399', fontWeight: 600 }}>
            <CheckCircle2 size={13} />
            <span>Classified: {parsedLat.toFixed(4)}° N, {parsedLon.toFixed(4)}° E</span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.25)', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: '#38bdf8' }}>
            <Navigation size={12} />
            <span>Listening for citizen location...</span>
          </div>
        )}
      </div>

      {/* Leaflet OpenStreetMap Container */}
      <div
        ref={mapContainerRef}
        style={{
          height: height,
          width: '100%',
          position: 'relative',
          zIndex: 1,
        }}
      />

      {/* Location Details Footer Bar */}
      <div
        style={{
          padding: '0.6rem 1rem',
          background: 'rgba(15, 23, 42, 0.95)',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          fontSize: '0.8rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1rem',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
          <span style={{ color: '#94a3b8' }}>
            🏙️ <strong style={{ color: '#e2e8f0' }}>District/Area:</strong> {districtArea || locationName || 'Recognizing from speech...'}
          </span>
          {streetName && (
            <span style={{ color: '#94a3b8' }}>
              🛣️ <strong style={{ color: '#e2e8f0' }}>Street:</strong> {streetName}
            </span>
          )}
          {landmark && (
            <span style={{ color: '#94a3b8' }}>
              🏛️ <strong style={{ color: '#e2e8f0' }}>Landmark:</strong> {landmark}
            </span>
          )}
        </div>
        <span style={{ color: '#64748b', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Globe size={11} /> OpenStreetMap © CartoDB
        </span>
      </div>
    </div>
  );
};
