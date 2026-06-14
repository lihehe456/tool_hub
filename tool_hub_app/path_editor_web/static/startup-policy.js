export function shouldAutoBrowseOnStartup(runtimeConfig) {
  return runtimeConfig?.auto_browse_on_startup ?? true;
}
