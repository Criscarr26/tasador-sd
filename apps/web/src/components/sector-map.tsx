'use client';

import { useEffect, useRef } from 'react';

import { formatDOP } from '@/lib/api';

// Approximate centroid of each sector the model knows. The domain has no
// per-listing geolocation, so this map is deliberately sector-level: one
// pin per sector carrying its REAL average rent. It never claims to show
// individual properties.
export const SECTOR_COORDS: Record<string, [number, number]> = {
  Piantini: [18.4719, -69.9312],
  Naco: [18.4736, -69.9385],
  'Serrallés': [18.4658, -69.9328],
  'Bella Vista': [18.459, -69.943],
  'Arroyo Hondo': [18.494, -69.956],
  'Los Prados': [18.482, -69.943],
  Gazcue: [18.465, -69.906],
  'Santo Domingo Este': [18.489, -69.857],
  'Villa Mella': [18.549, -69.92],
  'Los Alcarrizos': [18.512, -70.018],
};

export function SectorMap({
  averages,
  selected,
}: {
  averages: Record<string, number>;
  selected?: string;
}) {
  const holder = useRef<HTMLDivElement>(null);
  // Leaflet instances live outside React state: they are imperative and must
  // not trigger re-renders.
  const map = useRef<import('leaflet').Map | null>(null);
  const layer = useRef<import('leaflet').LayerGroup | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      // Leaflet touches `window` at import time, so it can only load in the
      // browser -- hence the dynamic import instead of a top-level one.
      const L = (await import('leaflet')).default;
      if (cancelled || !holder.current || map.current) return;

      map.current = L.map(holder.current, {
        center: [18.483, -69.93],
        zoom: 11,
        scrollWheelZoom: false,
        attributionControl: true,
      });

      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 17,
        attribution: '&copy; OpenStreetMap',
      }).addTo(map.current);

      layer.current = L.layerGroup().addTo(map.current);
      draw(L);
    })();

    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redraw pins whenever the averages arrive or the chosen sector changes.
  useEffect(() => {
    if (!map.current) return;
    (async () => {
      const L = (await import('leaflet')).default;
      draw(L);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [averages, selected]);

  function draw(L: typeof import('leaflet')) {
    if (!layer.current) return;
    layer.current.clearLayers();

    const values = Object.values(averages);
    if (!values.length) return;
    const max = Math.max(...values);

    for (const [name, avg] of Object.entries(averages)) {
      const coords = SECTOR_COORDS[name];
      if (!coords) continue;

      const isSelected = name === selected;
      // Radius encodes the average rent: the map reads as a price map, not
      // just a set of dots.
      const radius = 9 + (avg / max) * 13;

      L.circleMarker(coords, {
        radius,
        color: isSelected ? '#0f172a' : '#2170e4',
        weight: isSelected ? 3 : 1.5,
        fillColor: isSelected ? '#2170e4' : '#2170e4',
        fillOpacity: isSelected ? 0.75 : 0.32,
      })
        .bindTooltip(`<b>${name}</b><br/>${formatDOP(avg)} /mes`, {
          direction: 'top',
          offset: [0, -6],
        })
        .addTo(layer.current);
    }

    const target = selected ? SECTOR_COORDS[selected] : null;
    if (target) map.current?.panTo(target, { animate: true });
  }

  return (
    <div className="card map-card">
      <div className="card-title">Mapa del mercado</div>
      <div ref={holder} className="map-holder" role="img"
        aria-label="Mapa de sectores de Santo Domingo con el alquiler promedio de cada uno" />
      <p className="map-note">
        Un punto por sector: el tamaño refleja su alquiler promedio real y el sector
        elegido va resaltado. Las posiciones son aproximadas al centro del sector —
        el modelo trabaja por sector, no por dirección exacta.
      </p>
    </div>
  );
}
