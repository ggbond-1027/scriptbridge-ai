import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source = readFileSync(resolve("apps/web/src/components/YamlEditor.tsx"), "utf8");

const requiredSnippets = [
  "issues",
  "yaml-line-numbers",
  "yaml-diagnostics",
  "activeIssue",
  "onValidate",
  "lineCount",
];

const missing = requiredSnippets.filter((snippet) => !source.includes(snippet));

if (missing.length) {
  console.error(`YamlEditor is missing enterprise editor affordances: ${missing.join(", ")}`);
  process.exit(1);
}

console.log("YamlEditor enterprise shell check passed.");
