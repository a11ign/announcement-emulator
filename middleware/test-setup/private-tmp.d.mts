export const RUN_PREFIX: string;
export function privateBase(env?: Record<string, string | undefined>): string;
export function makeRunTmp(env?: Record<string, string | undefined>): string;
export function removeRunTmp(dir: string): void;
export function setup(): void;
export function teardown(): void;
