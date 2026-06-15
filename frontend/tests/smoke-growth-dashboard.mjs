import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const appUrl = process.env.APP_URL || "http://127.0.0.1:5173";
const outputDir = resolve("test-results");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const consoleErrors = [];

page.on("console", (message) => {
  if (message.type() === "error") {
    consoleErrors.push(message.text());
  }
});

await page.goto(appUrl, { waitUntil: "networkidle" });
await page.waitForSelector(".glass-board");

let bodyText = await page.locator("body").innerText();
assert(bodyText.includes("CreatorPulse"), "Page should render CreatorPulse brand");
assert(bodyText.includes("你的账号"), "Overview should render Chinese heading");
assert(bodyText.includes("转化诊断台") === false, "Conversion tab should not be visible before click");
assert(!bodyText.includes("æ"), "Rendered page should not contain mojibake marker æ");

for (const tab of ["粉丝转化", "粉丝粘性", "视频分布", "实时概览"]) {
  await page.getByRole("tab", { name: tab }).click();
  await page.waitForTimeout(100);
}

assert(await page.getByText("你的账号").isVisible(), "Overview should be visible after returning to tab");
assert(consoleErrors.length === 0, `Console errors found: ${consoleErrors.join(" | ")}`);

await mkdir(outputDir, { recursive: true });
await page.screenshot({ path: resolve(outputDir, "growth-dashboard-desktop.png"), fullPage: true });

await page.getByLabel("粉丝分析").click();
await page.waitForLoadState("networkidle");
await page.waitForTimeout(200);
bodyText = await page.locator("body").innerText();
assert(bodyText.includes("粉丝增长趋势"), "Fans page should render growth tab heading");
assert(!bodyText.includes("æ"), "Fans page should not contain mojibake marker æ");

for (const tab of ["转化来源", "粘性行为", "粉丝画像", "增长趋势"]) {
  await page.getByRole("tab", { name: tab }).click();
  await page.waitForTimeout(100);
}

assert(await page.getByText("粉丝增长趋势").isVisible(), "Fans growth tab should be visible after returning");
await page.screenshot({ path: resolve(outputDir, "fans-analysis-desktop.png"), fullPage: true });

await page.getByLabel("增长总览").click();
await page.waitForTimeout(200);
assert(await page.getByText("你的账号").isVisible(), "Growth page should be visible after sidebar navigation");

await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(200);
await page.screenshot({ path: resolve(outputDir, "growth-dashboard-mobile.png"), fullPage: true });

await browser.close();
console.log("Growth dashboard browser smoke test passed");
