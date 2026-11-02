export interface LonLat {
  lon: number;
  lat: number;
}

const TILE = 256; // Google's world is 256 * 2^zoom px wide

/**
 * The Vega `mercator` projection settings that put `center` in the middle of a `width` x `height`
 * view at Google Maps `zoom`, so Vega marks line up with the Google basemap under them.
 */
export function mercatorView(center: LonLat, zoom: number, width: number, height: number) {
  const scale = (TILE * 2 ** zoom) / (2 * Math.PI); // px per radian of longitude
  const lam = (center.lon * Math.PI) / 180;
  const phi = (center.lat * Math.PI) / 180;
  const y = Math.log(Math.tan(Math.PI / 4 + phi / 2));
  return { scale, translate: [width / 2 - scale * lam, height / 2 + scale * y] as [number, number] };
}
