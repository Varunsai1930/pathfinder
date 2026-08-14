import fs from "node:fs/promises";
import { Workbook } from "@oai/artifact-tool";

const inputPath = process.argv[2] ?? "submission.csv";
const csvText = await fs.readFile(inputPath, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "Submission" });
const check = await workbook.inspect({
  kind: "table",
  range: "Submission!A1:B6",
  include: "values",
  tableMaxRows: 6,
  tableMaxCols: 2,
});
console.log(check.ndjson);
const preview = await workbook.render({ sheetName: "Submission", range: "A1:B12", scale: 1.5 });
await fs.writeFile("submission_preview.png", new Uint8Array(await preview.arrayBuffer()));
