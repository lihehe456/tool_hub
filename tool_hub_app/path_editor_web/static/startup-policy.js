export function shouldAutoBrowseOnStartup(runtimeConfig) {
  return runtimeConfig?.auto_browse_on_startup ?? true;
}

export function startupBrowseRoot(runtimeConfig, fallbackRoot = "/") {
  return runtimeConfig?.user_root || fallbackRoot;
}
