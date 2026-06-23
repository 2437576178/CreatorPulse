import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const INPUT = "E:/download/CreatorPulse：达人粉丝增长分析与智能创作建议平台 (2).pptx";
const OUT = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/CreatorPulse_保留模板版.pptx";
const QA_DIR = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/.codex_ppt_tmp/template-preserved-qa";

const C = {
  bg: "#F2F2F2",
  ink: "#333333",
  muted: "#555555",
  pink: "#FF9AAD",
  line: "#D9D9D9",
  white: "#FFFFFF",
  blue: "#2F65D9",
  teal: "#149B9E",
  orange: "#F59E0B",
  green: "#20A66A",
};

function shape(slide, geometry, position, fill, line = { style: "solid", fill: "none", width: 0 }, extra = {}) {
  return slide.shapes.add({ geometry, position, fill, line, ...extra });
}

function text(slide, value, position, style = {}) {
  const s = shape(slide, "textbox", position, "none");
  s.text = value;
  s.text.style = {
    fontFace: "Microsoft YaHei",
    fontSize: 24,
    color: C.ink,
    ...style,
  };
  return s;
}

function setTitle(slide, value, sub) {
  text(slide, value, { left: 80, top: 66, width: 850, height: 54 }, { fontSize: 38, bold: true, color: C.pink });
  if (sub) {
    text(slide, sub, { left: 82, top: 128, width: 850, height: 36 }, { fontSize: 20, color: C.muted });
  }
}

function clearShapes(slide) {
  for (const item of [...(slide.shapes.items ?? [])]) {
    item.delete();
  }
}

function addBullets(slide, bullets, x = 110, y = 205, w = 980, fontSize = 24, gap = 58) {
  bullets.forEach((b, i) => {
    const top = y + i * gap;
    shape(slide, "ellipse", { left: x, top: top + 9, width: 15, height: 15 }, C.pink);
    text(slide, b, { left: x + 34, top, width: w, height: 42 }, { fontSize, color: C.ink });
  });
}

function addTwoColumn(slide, leftTitle, leftItems, rightTitle, rightItems) {
  const blocks = [
    [88, 210, leftTitle, leftItems, C.blue],
    [668, 210, rightTitle, rightItems, C.teal],
  ];
  blocks.forEach(([x, y, heading, items, color]) => {
    shape(slide, "roundRect", { left: x, top: y, width: 500, height: 360 }, C.white, {
      style: "solid",
      fill: C.line,
      width: 1,
    }, { borderRadius: 12 });
    text(slide, heading, { left: x + 34, top: y + 30, width: 430, height: 38 }, {
      fontSize: 28,
      bold: true,
      color,
    });
    items.forEach((item, i) => {
      shape(slide, "ellipse", { left: x + 40, top: y + 104 + i * 58, width: 12, height: 12 }, color);
      text(slide, item, { left: x + 66, top: y + 92 + i * 58, width: 390, height: 42 }, {
        fontSize: 21,
        color: C.ink,
      });
    });
  });
}

function addFlow(slide, nodes, y = 328) {
  const start = 76;
  const step = 190;
  nodes.forEach((n, i) => {
    const x = start + i * step;
    shape(slide, "roundRect", { left: x, top: y, width: 145, height: 88 }, C.white, {
      style: "solid",
      fill: C.line,
      width: 1,
    }, { borderRadius: 10 });
    text(slide, n[0], { left: x + 10, top: y + 18, width: 125, height: 26 }, {
      fontSize: 19,
      bold: true,
      color: n[2],
      alignment: "center",
    });
    text(slide, n[1], { left: x + 12, top: y + 50, width: 121, height: 26 }, {
      fontSize: 14,
      color: C.muted,
      alignment: "center",
    });
    if (i < nodes.length - 1) {
      shape(slide, "line", { left: x + 152, top: y + 44, width: 28, height: 0 }, "none", {
        style: "solid",
        fill: "#A8A8A8",
        width: 2.5,
        endArrowType: "triangle",
      });
    }
  });
}

function addFunctionGrid(slide, items) {
  items.forEach((it, i) => {
    const x = 92 + (i % 3) * 375;
    const y = 198 + Math.floor(i / 3) * 170;
    shape(slide, "roundRect", { left: x, top: y, width: 310, height: 128 }, C.white, {
      style: "solid",
      fill: C.line,
      width: 1,
    }, { borderRadius: 10 });
    shape(slide, "ellipse", { left: x + 24, top: y + 28, width: 36, height: 36 }, it[2]);
    text(slide, `${i + 1}`, { left: x + 24, top: y + 34, width: 36, height: 22 }, {
      fontSize: 16,
      bold: true,
      color: C.white,
      alignment: "center",
    });
    text(slide, it[0], { left: x + 78, top: y + 24, width: 210, height: 30 }, {
      fontSize: 23,
      bold: true,
      color: C.ink,
    });
    text(slide, it[1], { left: x + 78, top: y + 64, width: 205, height: 44 }, {
      fontSize: 17,
      color: C.muted,
    });
  });
}

async function writeBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  const p = await PresentationFile.importPptx(await FileBlob.load(INPUT));

  // Keep the original template chrome and the requested outline.
  // Retained original slide numbers: 1 cover, 3 team intro, 4 team members,
  // 5 project intro, 8 solution, 10 architecture divider, 11 architecture,
  // 16 platform overview, 17-21 function details, 25 summary, 26 thanks.
  const keep = new Set([1, 3, 4, 5, 8, 10, 11, 16, 17, 18, 19, 20, 21, 25, 26]);
  for (let i = p.slides.items.length - 1; i >= 0; i--) {
    if (!keep.has(i + 1)) p.slides.getItem(i).delete();
  }

  const slides = p.slides.items;

  // Slide 1 cover: keep template and logo, just make subtitle concise.
  if (slides[0].shapes.items[0]) {
    slides[0].shapes.items[0].text = "CreatorPulse：达人粉丝增长分析与智能创作建议平台";
  }
  if (slides[0].shapes.items[1]) {
    slides[0].shapes.items[1].text = "基于大数据的内容创作者增长分析与创作建议平台";
  }

  // Slides 2-3 are team pages: intentionally unchanged.

  // Project intro: user pain points.
  clearShapes(slides[3]);
  setTitle(slides[3], "项目介绍：用户痛点", "内容创作者面对多平台运营时，最难的是把数据变成下一步行动。");
  addBullets(slides[3], [
    "平台数据分散：抖音、B站、小红书等后台割裂，无法统一判断整体增长。",
    "播放量难解释增长：高播放不一定带来关注，需要看转粉率和互动质量。",
    "复盘缺少依据：不知道哪些视频真正带来粉丝，下一条内容仍依赖经验。",
    "创作建议不够具体：选题、发布时间、平台侧重缺少可解释的数据支撑。",
  ], 120, 218, 960, 24, 62);

  // What we did.
  clearShapes(slides[4]);
  setTitle(slides[4], "项目介绍：我们做了什么", "CreatorPulse 将跨平台数据聚合、增长分析和创作建议放到一个工作台。");
  addTwoColumn(
    slides[4],
    "核心思路",
    [
      "统一采集多平台数据",
      "用指标解释粉丝增长",
      "把分析结果转成创作建议",
      "前端页面直接展示结论",
    ],
    "当前实现",
    [
      "Vue + Flask 可运行 MVP",
      "mock / MySQL 双数据源",
      "Kafka / Spark dry-run 链路",
      "OpenAPI 与预检脚本",
    ],
  );

  // Architecture divider.
  if (slides[5].shapes.items[0]) slides[5].shapes.items[0].text = "项目架构";
  if (slides[5].shapes.items[1]) slides[5].shapes.items[1].text = "前端展示、后端接口、数据存储和大数据链路分层解耦";

  // Architecture detail.
  clearShapes(slides[6]);
  setTitle(slides[6], "项目架构：整体链路", "Flask 和 Vue 只读取 API / MySQL，大数据链路可以独立启动和排查。");
  addFlow(slides[6], [
    ["Vue 前端", "页面展示", C.blue],
    ["Flask API", "接口服务", C.teal],
    ["MySQL", "指标存储", C.green],
    ["Flume", "数据采集", C.orange],
    ["Kafka", "消息队列", C.orange],
    ["Spark", "聚合计算", C.green],
  ], 292);
  addBullets(slides[6], [
    "演示主线：Vue -> Flask API -> mock JSON / MySQL。",
    "大数据链路：mock_generator -> Flume -> Kafka -> Spark Streaming -> MySQL。",
    "好处：前端、后端、数据处理可以分开开发、验证和排查。",
  ], 130, 470, 960, 21, 44);

  // Platform overview.
  clearShapes(slides[7]);
  setTitle(slides[7], "详细介绍：平台有哪些功能", "平台围绕“看增长、找原因、给建议”设计 6 个核心页面。");
  addFunctionGrid(slides[7], [
    ["增长总览", "账号健康度、粉丝趋势、转化漏斗", C.blue],
    ["粉丝分析", "新增/掉粉、画像、粘性行为", C.teal],
    ["视频分析", "视频表现、转粉贡献、完播率", C.green],
    ["内容分布", "平台、类型、发布时间分布", C.orange],
    ["机会建议", "热点话题、选题和发布时间建议", C.pink],
    ["个人中心", "账号绑定、偏好设置、头像上传", "#7C3AED"],
  ]);

  // Function detail slides.
  clearShapes(slides[8]);
  setTitle(slides[8], "功能一：增长总览", "作用：快速判断账号整体增长状态。");
  addBullets(slides[8], [
    "展示账号健康度、总粉丝、今日新增、今日掉粉和净增趋势。",
    "通过播放 -> 互动 -> 主页访问 -> 关注，查看粉丝转化漏斗。",
    "汇总最近视频的涨粉表现，帮助发现增长来源。",
  ], 135, 230, 900, 25, 72);

  clearShapes(slides[9]);
  setTitle(slides[9], "功能二：粉丝分析", "作用：判断粉丝从哪里来，以及是否具有持续互动价值。");
  addBullets(slides[9], [
    "按平台查看新增粉丝、掉粉和净增粉丝变化。",
    "分析播放、互动、主页访问到关注的转化路径。",
    "结合评论、收藏、分享、弹幕等行为评估粉丝粘性。",
  ], 135, 230, 900, 25, 72);

  clearShapes(slides[10]);
  setTitle(slides[10], "功能三：视频分析", "作用：找出真正带来粉丝增长的视频。");
  addBullets(slides[10], [
    "查看单条视频播放、点赞、评论、分享、收藏和完播率。",
    "计算视频涨粉贡献，避免只看播放量判断内容价值。",
    "对比不同视频表现，辅助复盘爆款内容特征。",
  ], 135, 230, 900, 25, 72);

  clearShapes(slides[11]);
  setTitle(slides[11], "功能四：内容分布", "作用：帮助创作者优化平台投入和内容结构。");
  addBullets(slides[11], [
    "按平台查看内容数量、播放和互动表现。",
    "按内容类型分析哪类视频更容易涨粉。",
    "按发布时间观察效果，辅助调整发布节奏。",
  ], 135, 230, 900, 25, 72);

  clearShapes(slides[12]);
  setTitle(slides[12], "功能五：机会建议", "作用：把数据分析转成下一条内容的行动建议。");
  addBullets(slides[12], [
    "根据热点话题、历史表现和粉丝画像推荐选题。",
    "给出发布时间、平台侧重、标题封面等建议。",
    "每条建议保留证据指标，便于解释为什么推荐。",
  ], 135, 230, 900, 25, 72);

  // Summary.
  clearShapes(slides[13]);
  setTitle(slides[13], "项目总结与展望", "当前项目已形成可运行 MVP，后续重点是真实链路联调。");
  addTwoColumn(
    slides[13],
    "已完成",
    [
      "6 个 Vue 前端页面",
      "Flask API 与 OpenAPI",
      "mock / MySQL 数据源",
      "Kafka / Spark dry-run",
    ],
    "下一步",
    [
      "补齐真实 .env 配置",
      "按 preflight 分阶段验证",
      "联通 Kafka -> Spark -> MySQL",
      "完善更多真实数据场景",
    ],
  );

  await fs.mkdir(QA_DIR, { recursive: true });
  for (const [i, slide] of p.slides.items.entries()) {
    const stem = `slide-${String(i + 1).padStart(2, "0")}`;
    await writeBlob(path.join(QA_DIR, `${stem}.png`), await p.export({ slide, format: "png", scale: 1 }));
  }
  await writeBlob(path.join(QA_DIR, "montage.webp"), await p.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await p.inspect({ kind: "slide,textbox,shape,image", maxChars: 20000 });
  await fs.writeFile(path.join(QA_DIR, "inspect.ndjson"), inspect.ndjson, "utf8");

  const pptx = await PresentationFile.exportPptx(p);
  await pptx.save(OUT);
  console.log(OUT);
  console.log(`slides=${p.slides.items.length}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
