import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const input = "E:/download/CreatorPulse：达人粉丝增长分析与智能创作建议平台 (2).pptx";
const outDir = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/.codex_ppt_tmp/original-pages";

async function writeBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));
await fs.mkdir(outDir, { recursive: true });

for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(outDir, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
  await fs.writeFile(
    path.join(outDir, `${stem}.layout.json`),
    await (await slide.export({ format: "layout" })).text(),
    "utf8",
  );
}

console.log(`exported=${presentation.slides.items.length}`);
