import fs from "node:fs";
import path from "node:path";
import { parse } from "@babel/parser";

const root = process.cwd();
const errors = [];
function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      visit(file);
      continue;
    }
    if (!/\.tsx?$/.test(file)) continue;
    const relative = path.relative(root, file).replaceAll("\\", "/");
    const source = parse(fs.readFileSync(file, "utf8"), {
      sourceType: "module",
      plugins: ["typescript", "jsx"],
    });
    const layer = relative.split("/")[0];
    const feature = relative.split("/")[1];
    const view =
      relative.includes("/components/") ||
      layer === "widgets" ||
      layer === "app";
    function check(node) {
      if (node.type === "ImportDeclaration") {
        const name = node.source.value;
        const target = name.startsWith(".")
          ? path
              .relative(root, path.resolve(path.dirname(file), name))
              .replaceAll("\\", "/")
          : name;
        if (layer === "shared" && /^(app|widgets|features)\//.test(target)) {
          errors.push(`${relative}: shared cannot depend on ${target}`);
        }
        if (
          layer === "features" &&
          (/^(app|widgets)\//.test(target) ||
            (target.startsWith("features/") &&
              target.split("/")[1] !== feature))
        ) {
          errors.push(
            `${relative}: feature dependency crosses ownership: ${target}`,
          );
        }
        if (view && target.includes("/api/"))
          errors.push(`${relative}: view imports API: ${target}`);
        if (relative.includes("/api/") && name === "react")
          errors.push(`${relative}: transport depends on React`);
      }
      if (
        ["CallExpression", "NewExpression"].includes(node.type) &&
        node.callee.type === "Identifier"
      ) {
        const name = node.callee.name;
        if (
          ["fetch", "WebSocket"].includes(name) &&
          !relative.includes("/api/")
        ) {
          errors.push(`${relative}: ${name} must live in an API module`);
        }
      }
      for (const value of Object.values(node)) {
        if (Array.isArray(value))
          value.forEach((child) => {
            if (child?.type) check(child);
          });
        else if (value && typeof value === "object" && value.type) check(value);
      }
    }
    check(source);
  }
}
for (const directory of ["app", "widgets", "features", "shared"])
  visit(path.join(root, directory));
if (errors.length) {
  console.error(errors.join("\n"));
  process.exitCode = 1;
} else console.log("Architecture boundaries passed.");
