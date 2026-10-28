// Optional local QA using an installed Chrome; no browser download is required.
import { spawn } from "node:child_process";
import { mkdir, writeFile, mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const base = process.env.QA_BASE_URL || "http://127.0.0.1:8787";
const chrome = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profile = await mkdtemp(path.join(tmpdir(), "regulatory-qa-"));
const browser = spawn(chrome, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=9224", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const errors = [];
let socket;
try {
  let targets;
  for (let i = 0; i < 80; i++) {
    try { targets = await (await fetch("http://127.0.0.1:9224/json/list")).json(); break; } catch { await sleep(250); }
  }
  assert.ok(targets, "Chrome started");
  socket = new WebSocket(targets.find((target) => target.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let nextId = 0;
  const pending = new Map();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject, timer } = pending.get(message.id); clearTimeout(timer); pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message)); else resolve(message.result);
    }
  };
  const command = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId; const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 20000);
    pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await command("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const waitFor = async (expression) => {
    for (let i = 0; i < 100; i++) { if (await evaluate(`Boolean(${expression})`)) return; await sleep(200); }
    throw new Error(`Timed out waiting for ${expression}`);
  };
  const clickText = (text) => evaluate(`Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes(${JSON.stringify(text)})).click()`);
  const screenshot = async (name) => {
    const image = await command("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
    await writeFile(`outputs/${name}.png`, Buffer.from(image.data, "base64"));
  };
  await mkdir("outputs", { recursive: true });
  await command("Runtime.enable"); await command("Page.enable");
  await command("Emulation.setDeviceMetricsOverride", { width: 1536, height: 1000, deviceScaleFactor: 1, mobile: false });
  await command("Page.navigate", { url: base });
  await waitFor("document.querySelectorAll('.source-card').length === 3");
  const activeCorpus = await (await fetch(`${base}/api/status`)).json();
  const activeEvaluation = await (await fetch(`${base}/api/evaluation`)).json();
  assert.ok(await evaluate("document.body.innerText.includes('Complex rules.')"));
  await screenshot("desktop");
  await clickText("Consumer guarantees");
  await waitFor("document.querySelectorAll('.evidence-passage').length > 0");
  assert.ok(await evaluate("document.querySelector('.evidence-passage').textContent.includes('acceptable quality')"));
  await screenshot("conversation");
  await evaluate("document.querySelector('.citation').click()");
  await waitFor("document.querySelector('[role=dialog]')");
  assert.ok(await evaluate("document.querySelector('[role=dialog]').innerText.includes('cchew/lex-au')"));
  await screenshot("answer");
  await command("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape" });
  await waitFor("!document.querySelector('[role=dialog]')");
  await clickText("Source library"); await waitFor(`document.querySelectorAll('.library-card').length === ${activeCorpus.section_count}`);
  await evaluate("document.querySelector('[aria-label=\"Search statutory sections\"]').focus()");
  await command("Input.insertText", { text: "spare parts" });
  await waitFor("document.querySelectorAll('.library-card').length === 1");
  assert.ok(await evaluate("document.querySelector('.library-card').textContent.includes('spare parts')"));
  await clickText("Evaluation"); await waitFor(`document.querySelectorAll('.evaluation-row').length === ${activeEvaluation.metrics.questions}`);
  assert.ok(await evaluate("document.body.innerText.includes('Needs review')"));
  await screenshot("evaluation");
  await clickText("New research");
  await evaluate("document.querySelector('textarea').focus()");
  await command("Input.insertText", { text: "What is the current NCAT application fee in Sydney?" });
  await evaluate("document.querySelector('[aria-label=\"Send question\"]').click()");
  await waitFor("document.querySelector('.abstention')");
  await screenshot("abstention");
  await clickText("New research");
  await command("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await sleep(300);
  assert.ok(await evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "No mobile horizontal overflow");
  await screenshot("mobile");
  assert.deepEqual(errors, [], "No browser runtime exceptions");
  console.log("Browser QA passed: desktop, cited answer, source dialog, library, evaluation, reset, unsupported question, mobile layout; screenshots in outputs/.");
} finally {
  socket?.close(); browser.kill("SIGTERM");
}
