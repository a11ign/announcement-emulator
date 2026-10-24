import { defineConfig } from "@playwright/test";
import { withAnnouncements } from "@a11ign/announcement-emulator";
import { config } from "./base.config";

// The one line: `withAnnouncements(...)` around the config. The tests do not change.
export default defineConfig(withAnnouncements(config));
