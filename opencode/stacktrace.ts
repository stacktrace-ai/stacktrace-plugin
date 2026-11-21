// Stacktrace for OpenCode: ask Stacktrace about each tool call before it runs.
//
// OpenCode has no command hooks, so this plugin is the hook. It runs
// Stacktrace's hook commands with one JSON object on stdin:
// - when OpenCode starts the plugin for a project: `register`, so the
//   project's policy scope is ready;
// - `chat.message`: `admit` for the person's message, before OpenCode saves it;
// - `tool.execute.before`: `admit` for the call, before it runs.
// An answer of `{"block": true, "reason": ...}` stops it: the plugin throws.
// OpenCode gives the model a stopped call's reason as the tool's error. A
// stopped message shows the person only OpenCode's own error, so the plugin
// shows the reason first. Empty output lets it go on. Like Stacktrace's other
// hooks, a failure to get an answer lets it go on, and says so on stderr.
//
// OpenCode reads every export of a plugin file as a plugin, so this file
// exports one function and nothing else.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

// `<command> admit --agent-kind opencode` and `<command> register --agent-kind opencode`.
// `stacktrace hydrant up` writes its command in place of the marker. The
// Stacktrace plugin ships this file as is, beside its `scripts/` folder, so an
// unreplaced marker means the plugin's wrapper, which finds the CLI and stays
// silent when it fails. The marker is built in two parts, so the installer's
// replacement cannot change it too.
const MARKER = "__STACKTRACE_" + "HOOKS__";
const WRITTEN: string = "__STACKTRACE_HOOKS__";
const HOOKS: string =
  process.env.STACKTRACE_OPENCODE_HOOKS ??
  (WRITTEN !== MARKER
    ? WRITTEN
    : `sh '${fileURLToPath(new URL("../scripts/policy_hook.sh", import.meta.url))}'`);
const TIMEOUT_MS = 40_000;

function run(verb: string, payload: object): Promise<string> {
  return new Promise((resolve, reject) => {
    const command = `${HOOKS} ${verb} --agent-kind opencode`;
    const child = spawn("/bin/sh", ["-c", command], { stdio: ["pipe", "pipe", "inherit"] });
    let out = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("timed out"));
    }, TIMEOUT_MS);
    child.stdout.on("data", (chunk) => (out += chunk));
    child.on("error", reject);
    child.on("close", (code) => {
      clearTimeout(timer);
      code === 0 ? resolve(out) : reject(new Error(`exit ${code}`));
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

// OpenCode names an MCP tool `<server>_<tool>`, each server and tool name with
// every character outside [A-Za-z0-9_-] replaced by `_` (its `mcp/catalog.ts`).
const sanitize = (value: string) => value.replace(/[^a-zA-Z0-9_-]/g, "_");

// The configured MCP server whose sanitized name starts `tool`, when exactly
// one does. Two that fit, or none, name no server.
function serverOf(tool: string, servers: string[]): string | undefined {
  const fits = servers.filter((name) => {
    const prefix = sanitize(name) + "_";
    return tool.startsWith(prefix) && tool.length > prefix.length;
  });
  return fits.length === 1 ? fits[0] : undefined;
}

// OpenCode's own MCP resource-read tool keeps this fixed name instead of
// `<server>_<tool>`; the server it reads is in the call's own arguments.
const MCP_RESOURCE_READ_TOOL = "read_mcp_resource";

function mcpServerOf(tool: string, args: any, servers: string[]): string | undefined {
  if (tool === MCP_RESOURCE_READ_TOOL) {
    const server = args?.server;
    return typeof server === "string" && servers.includes(server) ? server : undefined;
  }
  return serverOf(tool, servers);
}

// The block reason, when the answer is a block. Anything else lets it go on.
async function blocked(what: string, payload: object): Promise<string | undefined> {
  let out: string;
  try {
    out = (await run("admit", payload)).trim();
  } catch (error) {
    console.error(`stacktrace: no decision for ${what} (${error}); it goes on`);
    return undefined;
  }
  if (!out) return undefined;
  try {
    const answer = JSON.parse(out);
    if (answer && answer.block === true) {
      return String(answer.reason ?? "Stacktrace blocked this action.");
    }
  } catch {
    console.error("stacktrace: unreadable decision; it goes on");
  }
  return undefined;
}

export const StacktracePlugin = async ({ client, directory }: any) => {
  run("register", { hook_event_name: "session_start", cwd: directory }).catch((error) =>
    console.error(`stacktrace: project not registered (${error})`),
  );

  // OpenCode's own merged configuration names the MCP servers, read once.
  let servers: Promise<string[]> | undefined;
  const configured = () =>
    (servers ??= client.config
      .get()
      .then((reply: any) => Object.keys(reply?.data?.mcp ?? reply?.mcp ?? {}))
      .catch(() => []));

  return {
    "chat.message": async (input: any, output: any) => {
      // The person's own words: text parts OpenCode did not add itself.
      const prompt = (output.parts ?? [])
        .filter((part: any) => part?.type === "text" && !part.synthetic)
        .map((part: any) => String(part.text ?? ""))
        .join("\n");
      if (!prompt) return;
      const reason = await blocked("this message", {
        hook_event_name: "chat.message",
        session_id: input.sessionID,
        prompt,
        cwd: directory,
      });
      if (reason === undefined) return;
      console.error(reason);
      await client.tui
        ?.showToast?.({ body: { message: reason, variant: "error" } })
        ?.catch?.(() => undefined);
      throw new Error(reason);
    },
    "tool.execute.before": async (input: any, output: any) => {
      const payload: Record<string, unknown> = {
        hook_event_name: "tool.execute.before",
        session_id: input.sessionID,
        tool_call_id: input.callID,
        tool_name: input.tool,
        input: output.args,
        cwd: directory,
      };
      const server = mcpServerOf(String(input.tool), output.args, await configured());
      if (server !== undefined) payload.mcp_server = server;
      const reason = await blocked(String(input.tool), payload);
      if (reason !== undefined) throw new Error(reason);
    },
  };
};
