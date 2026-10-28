import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

// Tokens are minted by the same CLI and signing key the API verifies with.
export default function setup() {
  const env = { ...process.env, DESK_AUTH: "dev" };
  const mint = (role: string, customers: string) =>
    execFileSync("../.venv/bin/desk", ["token", "--role", role, "--customers", customers], { env }).toString().trim();
  writeFileSync(
    "e2e/.tokens.json",
    JSON.stringify({ architect: mint("architect", "lws,stmv,lechfeld,bafm"), customer: mint("customer", "lws") }),
  );
}
