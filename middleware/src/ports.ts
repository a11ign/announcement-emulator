import { createServer } from "node:net";

/** `count` free TCP ports on the loopback, found by asking the system for each in turn. */
export async function freePorts(count: number): Promise<number[]> {
  const servers = [];
  const ports: number[] = [];
  for (let i = 0; i < count; i += 1) {
    const server = createServer();
    await new Promise<void>((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); });
    ports.push((server.address() as { port: number }).port);
    servers.push(server);
  }
  await Promise.all(servers.map((s) => new Promise((resolve) => s.close(resolve))));
  return ports;
}
