import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const input = "E:/download/CreatorPulse：达人粉丝增长分析与智能创作建议平台 (2).pptx";
const outDir = "E:/desktop/Vibecoding/bigdata_work/CreatorPulse/.codex_ppt_tmp/original-inspect";

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(input));
await fs.mkdir(outDir, { recursive: true });

const snapshot = await presentation.inspect({
  kind: "slide,textbox,shape,image,chart,table",
  maxChars: 12000,
});
await fs.writeFile(`${outDir}/inspect.ndjson`, snapshot.ndjson, "utf8");

const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
await writeBlob(`${outDir}/montage.webp`, montage);

console.log(`slides=${presentation.slides.items.length}`);
console.log(`${outDir}/inspect.ndjson`);
console.log(`${outDir}/montage.webp`);
