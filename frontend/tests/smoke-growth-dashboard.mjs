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

assert(await page.getByRole("heading", { name: "你的账号 增长健康度" }).isVisible(), "Overview should be visible after returning to tab");
assert(consoleErrors.length === 0, `Console errors found: ${consoleErrors.join(" | ")}`);

await mkdir(outputDir, { recursive: true });
await page.screenshot({ path: resolve(outputDir, "growth-dashboard-desktop.png"), fullPage: true });

await page.getByLabel("粉丝分析").click();
await page.waitForLoadState("networkidle");
await page.waitForTimeout(200);
bodyText = await page.locator("body").innerText();
assert(bodyText.includes("粉丝分析"), "Fans page should render template heading");
assert(!bodyText.includes("æ"), "Fans page should not contain mojibake marker æ");

for (const tab of ["转化来源", "粘性行为", "粉丝画像", "增长趋势"]) {
  await page.getByRole("tab", { name: tab }).click();
  await page.waitForTimeout(100);
}

assert(await page.getByText("粉丝分析").isVisible(), "Fans growth tab should be visible after returning");
await page.screenshot({ path: resolve(outputDir, "fans-analysis-desktop.png"), fullPage: true });

const pageChecks = [
  {
    nav: "视频分析",
    heading: "视频分析",
    tabs: ["涨粉贡献", "互动质量", "生命周期", "最新视频"],
    filename: "video-analysis-desktop.png"
  },
  {
    nav: "内容分布",
    heading: "内容分布",
    tabs: ["内容类型", "发布时间", "流量来源", "平台分布"],
    filename: "content-distribution-desktop.png"
  },
  {
    nav: "机会建议",
    heading: "机会建议",
    tabs: ["创作建议", "参考洞察", "热点机会"],
    filename: "creator-opportunities-desktop.png"
  },
  {
    nav: "个人中心",
    heading: "个人中心",
    tabs: ["平台绑定", "采集设置", "通知偏好", "数据报告"],
    filename: "creator-profile-desktop.png"
  }
];

for (const check of pageChecks) {
  await page.getByLabel(check.nav).click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(200);
  bodyText = await page.locator("body").innerText();
  assert(bodyText.includes(check.heading), `${check.nav} should render ${check.heading}`);
  assert(!bodyText.includes("æ"), `${check.nav} should not contain mojibake marker æ`);

  for (const tab of check.tabs) {
    await page.getByRole("tab", { name: tab }).click();
    await page.waitForTimeout(100);
  }

  assert(await page.getByText(check.heading).isVisible(), `${check.nav} should return to first tab`);
  await page.screenshot({ path: resolve(outputDir, check.filename), fullPage: true });
}

await page.getByLabel("增长总览").click();
await page.waitForTimeout(200);
assert(await page.getByRole("heading", { name: "你的账号 增长健康度" }).isVisible(), "Growth page should be visible after sidebar navigation");

await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(200);
await page.screenshot({ path: resolve(outputDir, "growth-dashboard-mobile.png"), fullPage: true });

await browser.close();
console.log("Growth dashboard browser smoke test passed");
