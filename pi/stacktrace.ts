// Stacktrace for Pi: ask Stacktrace about each prompt and tool call before it runs.
//
// Pi has no command hooks, so this extension is the hook. It runs Stacktrace's
// hook commands with one JSON object on stdin:
// - `session_start`: `register`, so the project's policy scope is ready;
// - `input`: `admit` for the person's message, before the model sees it;
// - `tool_call`: `admit` for the call, before it runs.
// An answer of `{"block": true, "reason": ...}` stops the prompt or the call.
// Empty output lets it go on. Like Stacktrace's other hooks, a failure to get
// an answer lets it go on, and says so on stderr.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

// `<command> admit --agent-kind pi` and `<command> register --agent-kind pi`.
// `stacktrace hydrant up` writes its command in place of the marker. The
// Stacktrace plugin ships this file as is, beside its `scripts/` folder, so an
// unreplaced marker means the plugin's wrapper, which finds the CLI and stays
// silent when it fails.
// Built in two parts, so the installer's replacement cannot change it too.
const MARKER = "__STACKTRACE_" + "HOOKS__";
const WRITTEN: string = "__STACKTRACE_HOOKS__";
const HOOKS: string =
  process.env.STACKTRACE_PI_HOOKS ??
  (WRITTEN !== MARKER
    ? WRITTEN
    : `sh '${fileURLToPath(new URL("../scripts/policy_hook.sh", import.meta.url))}'`);
const TIMEOUT_MS = 40_000;

function run(verb: string, payload: object): Promise<string> {
  return new Promise((resolve, reject) => {
    const command = `${HOOKS} ${verb} --agent-kind pi`;
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

export default function (pi: any) {
  pi.on("session_start", async (event: any, ctx: any) => {
    const payload = {
      hook_event_name: "session_start",
      session_id: ctx.sessionManager.getSessionId(),
      reason: event.reason,
      cwd: ctx.cwd,
    };
    // Registration starts its own work in the background, so the session
    // never waits for the daemon.
    run("register", payload).catch((error) =>
      console.error(`stacktrace: project not registered (${error})`),
    );
  });

  pi.on("input", async (event: any, ctx: any) => {
    const reason = await blocked("this message", {
      hook_event_name: "input",
      session_id: ctx.sessionManager.getSessionId(),
      prompt: event.text,
      source: event.source,
      cwd: ctx.cwd,
    });
    if (reason === undefined) return { action: "continue" };
    if (ctx.hasUI) ctx.ui.notify(reason, "error");
    else console.error(reason);
    return { action: "handled" };
  });

  pi.on("tool_call", async (event: any, ctx: any) => {
    const reason = await blocked(event.toolName, {
      hook_event_name: "tool_call",
      session_id: ctx.sessionManager.getSessionId(),
      tool_call_id: event.toolCallId,
      tool_name: event.toolName,
      input: event.input,
      cwd: ctx.cwd,
    });
    if (reason === undefined) return;
    // Pi writes a blocked call as an ordinary error result. This entry is
    // what tells OpenAIDR the call never ran (its ADR-0044), so the block
    // is not read later as a call that ran and failed.
    pi.appendEntry("openaidr.tool-call-blocked", { toolCallId: event.toolCallId });
    return { block: true, reason };
  });
}
