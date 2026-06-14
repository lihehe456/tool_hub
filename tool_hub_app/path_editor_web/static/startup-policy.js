export function startupBrowseRoot(runtimeConfig, fallbackRoot = "/") {
  return runtimeConfig?.user_root || fallbackRoot;
}
