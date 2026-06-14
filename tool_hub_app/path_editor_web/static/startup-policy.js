export function shouldAutoBrowseOnStartup(runtimeConfig) {
  return Boolean(runtimeConfig?.auto_browse_on_startup);
}

export function startupBrowseRoot(runtimeConfig, fallbackRoot = "/") {
  return runtimeConfig?.user_root || fallbackRoot;
}
