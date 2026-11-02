let loading: Promise<typeof google.maps> | null = null;

/** Loads the Google Maps JavaScript API once. Rejects if the script can't be fetched. */
export function loadGoogleMaps(apiKey: string): Promise<typeof google.maps> {
  loading ??= new Promise((resolve, reject) => {
    // With loading=async, `importLibrary` only exists once Google calls the callback (not at script onload).
    const callback = "__onGoogleMapsLoaded";
    (window as unknown as Record<string, () => void>)[callback] = () =>
      google.maps.importLibrary("maps").then(() => resolve(google.maps), reject);
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&v=weekly&loading=async&callback=${callback}`;
    script.async = true;
    script.onerror = () => reject(new Error("Couldn’t load the Google Maps script"));
    document.head.append(script);
  });
  loading.catch(() => (loading = null)); // allow a retry on remount
  return loading;
}
