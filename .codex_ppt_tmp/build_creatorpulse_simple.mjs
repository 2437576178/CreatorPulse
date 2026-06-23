import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/CreatorPulse_项目简洁版.pptx";
const QA_DIR = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/.codex_ppt_tmp/qa";
const ASSET_DIR = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/.codex_ppt_tmp/unzipped/ppt/media";
const heroPath = path.join(ASSET_DIR, "image5.png");

async function writeBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function readBytes(filePath) {
  const bytes = await fs.readFile(filePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

const W = 1280;
const H = 720;
const page = { left: 70, top: 56, width: 1140, height: 608 };
const C = {
  ink: "#172033",
  muted: "#5F6B7A",
  pale: "#EEF4F8",
  blue: "#246BFE",
  teal: "#16A3A6",
  green: "#20A66A",
  amber: "#F59E0B",
  red: "#E45757",
  dark: "#0B1220",
  soft: "#F7FAFC",
  line: "#D7E2EA",
  white: "#FFFFFF",
};

const pres = Presentation.create({ slideSize: { width: W, height: H } });
pres.author = "CreatorPulse";
pres.title = "CreatorPulse 项目简洁版";
pres.theme.colorScheme = {
  name: "CreatorPulse",
  themeColors: {
    accent1: C.blue,
    accent2: C.teal,
    accent3: C.amber,
    accent4: C.green,
    accent5: C.red,
    accent6: "#7C3AED",
    bg1: C.white,
    bg2: C.soft,
    tx1: C.ink,
    tx2: C.muted,
    dk1: "#000000",
    dk2: C.dark,
    lt1: C.white,
    lt2: C.pale,
    hlink: C.blue,
    folHlink: "#7C3AED",
  },
};

function shape(slide, geometry, position, fill, line = { style: "solid", fill: "none", width: 0 }, extra = {}) {
  return slide.shapes.add({ geometry, position, fill, line, ...extra });
}

function text(slide, value, position, style = {}) {
  const box = shape(slide, "textbox", position, "none");
  box.text = value;
  box.text.style = {
    fontFace: "Microsoft YaHei",
    fontSize: 24,
    color: C.ink,
    ...style,
  };
  return box;
}

function title(slide, value, sub) {
  text(slide, "CREATORPULSE", { left: page.left, top: 38, width: 220, height: 26 }, {
    fontSize: 13,
    bold: true,
    color: C.teal,
    charSpacing: 1.8,
  });
  text(slide, value, { left: page.left, top: 76, width: 850, height: 58 }, {
    fontSize: 40,
    bold: true,
    color: C.ink,
  });
  if (sub) {
    text(slide, sub, { left: page.left, top: 136, width: 820, height: 34 }, {
      fontSize: 18,
      color: C.muted,
    });
  }
}

function footer(slide, index) {
  shape(slide, "rect", { left: 70, top: 672, width: 1040, height: 1.5 }, C.line);
  text(slide, `CreatorPulse 项目汇报  /  ${String(index).padStart(2, "0")}`, {
    left: 70,
    top: 684,
    width: 320,
    height: 20,
  }, { fontSize: 12, color: "#8A96A6" });
}

function card(slide, x, y, w, h, label, value, color = C.blue) {
  shape(slide, "roundRect", { left: x, top: y, width: w, height: h }, C.white, {
    style: "solid",
    fill: C.line,
    width: 1,
  }, { borderRadius: "rounded-xl", shadow: "shadow-sm" });
  shape(slide, "rect", { left: x, top: y, width: 6, height: h }, color);
  text(slide, value, { left: x + 28, top: y + 26, width: w - 50, height: 54 }, {
    fontSize: 42,
    bold: true,
    color,
  });
  text(slide, label, { left: x + 30, top: y + 92, width: w - 55, height: 50 }, {
    fontSize: 18,
    color: C.muted,
  });
}

function chip(slide, x, y, label, color = C.blue, w = 140) {
  shape(slide, "roundRect", { left: x, top: y, width: w, height: 38 }, `${color}18`, {
    style: "solid",
    fill: `${color}55`,
    width: 1,
  }, { borderRadius: "rounded-full" });
  text(slide, label, { left: x + 14, top: y + 8, width: w - 28, height: 22 }, {
    fontSize: 15,
    bold: true,
    color,
    alignment: "center",
  });
}

function step(slide, x, y, w, h, n, heading, body, color) {
  shape(slide, "roundRect", { left: x, top: y, width: w, height: h }, C.white, {
    style: "solid",
    fill: C.line,
    width: 1,
  }, { borderRadius: "rounded-xl", shadow: "shadow-sm" });
  shape(slide, "ellipse", { left: x + 24, top: y + 24, width: 48, height: 48 }, color);
  text(slide, n, { left: x + 24, top: y + 31, width: 48, height: 28 }, {
    fontSize: 20,
    bold: true,
    color: C.white,
    alignment: "center",
  });
  text(slide, heading, { left: x + 88, top: y + 24, width: w - 116, height: 30 }, {
    fontSize: 22,
    bold: true,
    color: C.ink,
  });
  text(slide, body, { left: x + 88, top: y + 66, width: w - 116, height: h - 88 }, {
    fontSize: 17,
    color: C.muted,
  });
}

function arrow(slide, x, y, w, color = C.line) {
  shape(slide, "line", { left: x, top: y, width: w, height: 0 }, "none", {
    style: "solid",
    fill: color,
    width: 3,
    beginArrowType: "none",
    endArrowType: "triangle",
  });
}

async function build() {
  const hero = await readBytes(heroPath);

  // 1. Cover
  {
    const slide = pres.slides.add();
    slide.background.fill = C.dark;
    slide.images.add({
      blob: hero,
      contentType: "image/png",
      alt: "数据分析工作台",
      fit: "cover",
      position: { left: 700, top: 0, width: 580, height: 720 },
      crop: { left: 0.12, top: 0.05, right: 0.08, bottom: 0.02 },
    });
    shape(slide, "rect", { left: 640, top: 0, width: 640, height: 720 }, "#0B1220AA");
    shape(slide, "rect", { left: 0, top: 0, width: 760, height: 720 }, C.dark);
    text(slide, "CreatorPulse", { left: 76, top: 110, width: 600, height: 72 }, {
      fontSize: 58,
      bold: true,
      color: C.white,
    });
    text(slide, "达人粉丝增长分析与智能创作建议平台", {
      left: 80,
      top: 200,
      width: 620,
      height: 58,
    }, { fontSize: 30, color: "#DCE7F1" });
    text(slide, "用统一数据视图回答三个问题：谁在涨粉、为什么涨粉、下一条内容怎么做。", {
      left: 82,
      top: 300,
      width: 560,
      height: 78,
    }, { fontSize: 24, color: "#B9C7D6" });
    chip(slide, 82, 430, "Vue + Flask", C.teal, 145);
    chip(slide, 246, 430, "MySQL", C.green, 110);
    chip(slide, 376, 430, "Kafka + Spark", C.amber, 170);
    text(slide, "项目简洁版汇报", { left: 82, top: 620, width: 360, height: 24 }, {
      fontSize: 16,
      color: "#94A3B8",
    });
  }

  // 2. Pain points
  {
    const slide = pres.slides.add();
    slide.background.fill = C.soft;
    title(slide, "项目要解决什么问题", "内容创作者不是缺数据，而是缺一个能解释增长的统一视图。");
    const items = [
      ["数据分散", "多平台后台割裂，整体表现难以快速判断", C.blue],
      ["播放不等于涨粉", "高播放未必带来关注，需要看转粉效率", C.teal],
      ["复盘依赖经验", "选题、发布时间和平台侧重缺少数据依据", C.amber],
    ];
    items.forEach((it, i) => step(slide, 90 + i * 385, 245, 335, 210, `0${i + 1}`, it[0], it[1], it[2]));
    text(slide, "核心链路", { left: 110, top: 535, width: 120, height: 28 }, {
      fontSize: 18,
      bold: true,
      color: C.muted,
    });
    const flow = ["曝光播放", "互动行为", "粉丝转化", "内容复盘", "创作建议"];
    flow.forEach((f, i) => {
      const x = 250 + i * 170;
      shape(slide, "roundRect", { left: x, top: 520, width: 125, height: 48 }, C.white, {
        style: "solid",
        fill: C.line,
        width: 1,
      }, { borderRadius: "rounded-full" });
      text(slide, f, { left: x + 12, top: 533, width: 101, height: 22 }, {
        fontSize: 16,
        bold: true,
        color: C.ink,
        alignment: "center",
      });
      if (i < flow.length - 1) arrow(slide, x + 132, 545, 30, "#B8C5D1");
    });
    footer(slide, 2);
  }

  // 3. Solution
  {
    const slide = pres.slides.add();
    slide.background.fill = C.white;
    title(slide, "CreatorPulse 的解决方案", "把跨平台数据统一成可看、可解释、可行动的增长工作台。");
    card(slide, 86, 230, 250, 160, "跨平台聚合", "统一", C.blue);
    card(slide, 380, 230, 250, 160, "粉丝增长分析", "解释", C.teal);
    card(slide, 674, 230, 250, 160, "机会与建议", "行动", C.amber);
    card(slide, 968, 230, 220, 160, "MVP 可运行", "闭环", C.green);
    const points = [
      "一个页面查看账号健康度、粉丝趋势和视频表现。",
      "用转粉率、互动率、内容效率解释增长质量。",
      "根据热点、粉丝画像和历史表现给出创作建议。",
    ];
    points.forEach((p, i) => {
      shape(slide, "ellipse", { left: 116, top: 470 + i * 46, width: 18, height: 18 }, [C.blue, C.teal, C.amber][i]);
      text(slide, p, { left: 150, top: 462 + i * 46, width: 760, height: 34 }, {
        fontSize: 22,
        color: C.ink,
      });
    });
    footer(slide, 3);
  }

  // 4. Features
  {
    const slide = pres.slides.add();
    slide.background.fill = C.soft;
    title(slide, "前端做了哪些页面", "MVP 已完成 6 个一级页面，覆盖从总览到建议的主要使用路径。");
    const features = [
      ["增长总览", "账号健康度、粉丝趋势、转化漏斗", C.blue],
      ["粉丝分析", "新增/掉粉、画像、粘性行为", C.teal],
      ["视频分析", "单视频表现、转粉贡献、完播率", C.green],
      ["内容分布", "平台、类型、发布时间分布", C.amber],
      ["机会建议", "热点话题、选题、发布时间建议", C.red],
      ["个人中心", "账号绑定、偏好配置、头像上传", "#7C3AED"],
    ];
    features.forEach((f, i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const x = 92 + col * 380;
      const y = 220 + row * 170;
      shape(slide, "roundRect", { left: x, top: y, width: 320, height: 128 }, C.white, {
        style: "solid",
        fill: C.line,
        width: 1,
      }, { borderRadius: "rounded-xl", shadow: "shadow-sm" });
      shape(slide, "ellipse", { left: x + 24, top: y + 24, width: 44, height: 44 }, f[2]);
      text(slide, String(i + 1), { left: x + 24, top: y + 31, width: 44, height: 24 }, {
        fontSize: 18,
        bold: true,
        color: C.white,
        alignment: "center",
      });
      text(slide, f[0], { left: x + 86, top: y + 24, width: 210, height: 28 }, {
        fontSize: 22,
        bold: true,
        color: C.ink,
      });
      text(slide, f[1], { left: x + 86, top: y + 66, width: 205, height: 42 }, {
        fontSize: 16,
        color: C.muted,
      });
    });
    footer(slide, 4);
  }

  // 5. Architecture
  {
    const slide = pres.slides.add();
    slide.background.fill = C.white;
    title(slide, "系统架构：前后端与数据链路解耦", "Vue 和 Flask 只读 API/MySQL，大数据链路可以独立启动和排查。");
    const boxes = [
      ["Vue 前端", "6 个页面\n可视化展示", 88, 270, C.blue],
      ["Flask API", "ViewModel 合同\nOpenAPI", 338, 270, C.teal],
      ["数据源", "mock JSON\n或 MySQL", 588, 270, C.green],
      ["大数据链路", "Flume / Kafka\nSpark Streaming", 838, 270, C.amber],
    ];
    boxes.forEach(([h, b, x, y, color]) => {
      shape(slide, "roundRect", { left: x, top: y, width: 190, height: 150 }, C.soft, {
        style: "solid",
        fill: color,
        width: 2,
      }, { borderRadius: "rounded-xl" });
      text(slide, h, { left: x + 20, top: y + 24, width: 150, height: 30 }, {
        fontSize: 22,
        bold: true,
        color,
        alignment: "center",
      });
      text(slide, b, { left: x + 22, top: y + 72, width: 146, height: 58 }, {
        fontSize: 17,
        color: C.muted,
        alignment: "center",
      });
    });
    arrow(slide, 286, 345, 38, "#94A3B8");
    arrow(slide, 536, 345, 38, "#94A3B8");
    arrow(slide, 786, 345, 38, "#94A3B8");
    text(slide, "演示主线：Vue -> Flask API -> mock JSON / MySQL", {
      left: 120,
      top: 500,
      width: 980,
      height: 36,
    }, { fontSize: 24, bold: true, color: C.ink, alignment: "center" });
    text(slide, "真实流式链路作为独立能力接入，不影响前端和 API 的日常演示。", {
      left: 200,
      top: 552,
      width: 820,
      height: 30,
    }, { fontSize: 19, color: C.muted, alignment: "center" });
    footer(slide, 5);
  }

  // 6. Data pipeline
  {
    const slide = pres.slides.add();
    slide.background.fill = C.soft;
    title(slide, "大数据演示链路", "从模拟事件到聚合结果，形成可验证的数据处理闭环。");
    const nodes = [
      ["mock_generator", "生成视频/粉丝事件", C.blue],
      ["Flume", "采集 JSON 文件", C.teal],
      ["Kafka", "消息队列缓冲", C.amber],
      ["Spark Streaming", "实时聚合计算", C.green],
      ["MySQL", "保存指标结果", C.red],
      ["Flask + Vue", "展示到页面", "#7C3AED"],
    ];
    nodes.forEach((n, i) => {
      const x = 72 + i * 196;
      shape(slide, "roundRect", { left: x, top: 290, width: 160, height: 116 }, C.white, {
        style: "solid",
        fill: C.line,
        width: 1,
      }, { borderRadius: "rounded-xl", shadow: "shadow-sm" });
      shape(slide, "rect", { left: x, top: 290, width: 160, height: 8 }, n[2]);
      text(slide, n[0], { left: x + 10, top: 318, width: 140, height: 28 }, {
        fontSize: 17,
        bold: true,
        color: C.ink,
        alignment: "center",
      });
      text(slide, n[1], { left: x + 14, top: 360, width: 132, height: 32 }, {
        fontSize: 14,
        color: C.muted,
        alignment: "center",
      });
      if (i < nodes.length - 1) arrow(slide, x + 168, 350, 22, "#9AA8B7");
    });
    text(slide, "当前状态：已完成 Kafka/Spark dry-run、离线聚合和 VM 一键脚本；真实写入按 preflight 分阶段开启。", {
      left: 110,
      top: 500,
      width: 1030,
      height: 58,
    }, { fontSize: 22, color: C.ink, alignment: "center" });
    footer(slide, 6);
  }

  // 7. Technical implementation
  {
    const slide = pres.slides.add();
    slide.background.fill = C.white;
    title(slide, "技术实现重点", "不是只做页面，而是把数据合同、存储、计算和验证都串起来。");
    const groups = [
      ["前端", ["Vue/Vite 工程化", "6 个页面接入 API", "深色数据看板风格"], C.blue],
      ["后端", ["Flask API", "ViewModel 合同", "mock/MySQL 双 Repository"], C.teal],
      ["数据", ["MySQL schema", "mock 导入脚本", "OpenAPI 输出"], C.green],
      ["计算", ["Kafka 事件闭环", "Spark 聚合 dry-run", "日报/周报/月报脚本"], C.amber],
    ];
    groups.forEach((g, i) => {
      const x = 92 + (i % 2) * 560;
      const y = 220 + Math.floor(i / 2) * 190;
      shape(slide, "roundRect", { left: x, top: y, width: 500, height: 145 }, C.soft, {
        style: "solid",
        fill: C.line,
        width: 1,
      }, { borderRadius: "rounded-xl" });
      text(slide, g[0], { left: x + 28, top: y + 22, width: 110, height: 30 }, {
        fontSize: 24,
        bold: true,
        color: g[2],
      });
      g[1].forEach((p, j) => {
        shape(slide, "ellipse", { left: x + 32, top: y + 72 + j * 26, width: 9, height: 9 }, g[2]);
        text(slide, p, { left: x + 54, top: y + 63 + j * 26, width: 390, height: 22 }, {
          fontSize: 16,
          color: C.ink,
        });
      });
    });
    footer(slide, 7);
  }

  // 8. Progress
  {
    const slide = pres.slides.add();
    slide.background.fill = C.soft;
    title(slide, "当前完成情况", "项目已经从静态原型推进到可运行 MVP 和 dry-run 数据链路。");
    card(slide, 110, 230, 230, 150, "一级页面", "6", C.blue);
    card(slide, 385, 230, 230, 150, "平台 mock", "3", C.teal);
    card(slide, 660, 230, 230, 150, "Insight 建议", "20+", C.amber);
    card(slide, 935, 230, 230, 150, "API 页面合同", "6", C.green);
    const done = [
      "登录、注册、平台绑定、头像上传和个人中心配置已完成。",
      "MySQL schema、mock 导入、Repository 工厂已完成。",
      "Kafka 风格事件生成、消费校验、Spark dry-run 已完成。",
      "提供真实服务接入前的 preflight 和报告脚本。",
    ];
    done.forEach((d, i) => {
      shape(slide, "ellipse", { left: 168, top: 454 + i * 38, width: 15, height: 15 }, C.green);
      text(slide, d, { left: 196, top: 446 + i * 38, width: 880, height: 28 }, {
        fontSize: 19,
        color: C.ink,
      });
    });
    footer(slide, 8);
  }

  // 9. Next
  {
    const slide = pres.slides.add();
    slide.background.fill = C.dark;
    text(slide, "下一步计划", { left: 80, top: 84, width: 520, height: 62 }, {
      fontSize: 48,
      bold: true,
      color: C.white,
    });
    text(slide, "按“先验证、再接入、最后联调”的节奏推进真实服务。", {
      left: 82,
      top: 160,
      width: 700,
      height: 36,
    }, { fontSize: 22, color: "#CBD5E1" });
    const next = [
      ["1", "补齐 .env", "填写 MySQL、Spark JDBC、Kafka 地址和账号配置。", C.blue],
      ["2", "分阶段 preflight", "先 MySQL，再 Spark JDBC，再 Kafka，最后 full-pipeline。", C.teal],
      ["3", "真实链路联调", "完成 Kafka -> Spark -> MySQL -> API -> Vue 的演示闭环。", C.amber],
    ];
    next.forEach((n, i) => step(slide, 96 + i * 370, 290, 315, 190, n[0], n[1], n[2], n[3]));
    text(slide, "目标：让达人用一个工作台看懂增长，并得到下一次创作建议。", {
      left: 110,
      top: 570,
      width: 980,
      height: 42,
    }, { fontSize: 26, bold: true, color: C.white, alignment: "center" });
  }

  await fs.mkdir(QA_DIR, { recursive: true });
  for (const [idx, slide] of pres.slides.items.entries()) {
    const stem = `slide-${String(idx + 1).padStart(2, "0")}`;
    await writeBlob(path.join(QA_DIR, `${stem}.png`), await pres.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(QA_DIR, `${stem}.layout.json`), await layout.text(), "utf8");
  }
  await writeBlob(path.join(QA_DIR, "montage.webp"), await pres.export({ format: "webp", montage: true, scale: 1 }));
  const snapshot = await pres.inspect({ kind: "slide,textbox,shape,image,chart,table", maxChars: 20000 });
  await fs.writeFile(path.join(QA_DIR, "inspect.ndjson"), snapshot.ndjson, "utf8");

  const pptx = await PresentationFile.exportPptx(pres);
  await pptx.save(OUT);
  console.log(OUT);
}

build().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
