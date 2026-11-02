import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import embed, { type Result } from "vega-embed";
import { loadGoogleMaps } from "../lib/googleMaps";
import type { Point } from "../lib/frames";
import { mercatorView } from "../lib/mercator";
import { VehicleSync } from "../lib/vegaSync";
import { MAP_SIGNALS, mapSpec } from "../specs";

export interface MapHandle {
  setPoints(points: Point[]): void;
}

interface Props {
  /** A Google Maps JavaScript API key. Without one (or if Google fails to load) the map has no basemap. */
  googleMapsApiKey?: string | null;
}

const escapeHtml = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

// Metra reaches Kenosha, Joliet and Elburn, so start wider than the city itself.
const START_CENTER = { lat: 41.95, lng: -87.9 };
const START_ZOOM = 9;

const MAP_STYLES: google.maps.MapTypeStyle[] = [{ featureType: "poi", stylers: [{ visibility: "off" }] }];

/** The animated map. Frames are pushed imperatively (60 fps) rather than through React state. */
export const MapView = forwardRef<MapHandle, Props>(function MapView({ googleMapsApiKey }, ref) {
  const wrap = useRef<HTMLDivElement>(null);
  const base = useRef<HTMLDivElement>(null);
  const el = useRef<HTMLDivElement>(null);
  const sync = useRef<VehicleSync | null>(null);
  const pending = useRef<Point[]>([]);
  const [basemap, setBasemap] = useState(false);

  useImperativeHandle(ref, () => ({
    setPoints(points) {
      pending.current = points;
      sync.current?.apply(points);
    },
  }));

  useEffect(() => {
    let cancelled = false;
    let result: Result | undefined;
    let teardown: (() => void) | undefined;

    (async () => {
      let maps: typeof google.maps | undefined;
      if (googleMapsApiKey) {
        try {
          maps = await loadGoogleMaps(googleMapsApiKey);
        } catch (err) {
          console.warn("Google Maps unavailable; drawing the map without a basemap.", err);
        }
      }
      if (cancelled) return;
      setBasemap(!!maps);

      const r = await embed(el.current!, mapSpec(!!maps), {
        actions: false,
        renderer: "canvas",
        tooltip: {
          formatTooltip: (value) => {
            const v = value as { label?: string; detail?: string };
            return `<strong>${escapeHtml(v.label)}</strong><br>${escapeHtml(v.detail)}`;
          },
        },
      });
      if (cancelled) return r.finalize();
      result = r;
      sync.current = new VehicleSync(r.view);
      sync.current.apply(pending.current); // frames that arrived before the view was ready
      if (maps) teardown = overlayOn(maps, base.current!, wrap.current!, el.current!, r);
    })().catch((err) => console.error("Map failed to render", err));

    return () => {
      cancelled = true;
      teardown?.();
      sync.current = null;
      result?.finalize();
    };
  }, [googleMapsApiKey]);

  return (
    <div ref={wrap} className="map-wrap">
      {googleMapsApiKey && <div ref={base} className="map-base" hidden={!basemap} />}
      <div
        ref={el}
        className={basemap ? "map over-basemap" : "map"}
        role="img"
        aria-label="Live map of CTA and Metra vehicles in Chicago"
      />
    </div>
  );
});

/**
 * Creates the Google map in `baseEl` and keeps the Vega view (which sits on top, click-through)
 * in step with its pan and zoom. Returns a cleanup function.
 */
function overlayOn(
  maps: typeof google.maps,
  baseEl: HTMLElement,
  wrapEl: HTMLElement,
  overlayEl: HTMLElement,
  { view }: Result,
): () => void {
  const map = new maps.Map(baseEl, {
    center: START_CENTER,
    zoom: START_ZOOM,
    styles: MAP_STYLES,
    zoomControl: true,
    gestureHandling: "greedy", // wheel zooms and one finger pans, as the map isn't a scrolling page
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
    rotateControl: false,
    clickableIcons: false,
  });

  const follow = () => {
    const center = map.getCenter();
    const zoom = map.getZoom();
    if (!center || zoom === undefined) return;
    const { scale, translate } = mercatorView({ lon: center.lng(), lat: center.lat() }, zoom, wrapEl.clientWidth, wrapEl.clientHeight);
    view
      .width(wrapEl.clientWidth)
      .height(wrapEl.clientHeight)
      .signal(MAP_SIGNALS.scale, scale)
      .signal(MAP_SIGNALS.tx, translate[0])
      .signal(MAP_SIGNALS.ty, translate[1])
      .run();
  };
  const listener = map.addListener("bounds_changed", follow);
  const resize = new ResizeObserver(follow);
  resize.observe(wrapEl);
  follow();

  // The Vega canvas can't take pointer events (it would block panning), so hand it the pointer
  // position itself: that's what makes hovering a vehicle show its tooltip.
  const canvas = () => overlayEl.querySelector("canvas");
  const forward = (type: string) => (e: MouseEvent) =>
    canvas()?.dispatchEvent(new MouseEvent(type, { clientX: e.clientX, clientY: e.clientY, bubbles: true }));
  const move = forward("mousemove");
  const leave = forward("mouseout");
  wrapEl.addEventListener("mousemove", move);
  wrapEl.addEventListener("mouseleave", leave);
  const dragStart = map.addListener("dragstart", () => canvas()?.dispatchEvent(new MouseEvent("mouseout", { bubbles: true })));

  return () => {
    listener.remove();
    dragStart.remove();
    resize.disconnect();
    wrapEl.removeEventListener("mousemove", move);
    wrapEl.removeEventListener("mouseleave", leave);
    baseEl.replaceChildren(); // drop the map's DOM; the Map object itself has no destroy
  };
}
