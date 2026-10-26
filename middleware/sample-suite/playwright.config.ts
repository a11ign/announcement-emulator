import { defineConfig } from "@playwright/test";
import { withAnnouncements } from "@a11ign/announcement-emulator";
import { config } from "./base.config";

// The one line: `withAnnouncements(...)` around the config. The tests do not change.
// ANNOUNCEMENT_EMULATOR_VERIFY=1: the runtime reads each page's tree from scratch after every incremental read of it and records where the two differ (A11-229)
export default defineConfig(withAnnouncements(config, { verify: process.env.ANNOUNCEMENT_EMULATOR_VERIFY === "1" }));
