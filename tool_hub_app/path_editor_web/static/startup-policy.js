export function shouldAutoBrowseOnStartup(runtimeConfig) {
  return Boolean(runtimeConfig?.auto_browse_on_startup);
}
