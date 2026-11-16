import { installExtensionCompatibility } from "./lib/extension-compat";

// Next.js executes this synchronously before React hydration starts.
installExtensionCompatibility(document);
