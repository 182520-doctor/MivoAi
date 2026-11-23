import fs from "node:fs";
import path from "node:path";
import { parse } from "@babel/parser";

const root = process.cwd();
const errors = [];
const allowedFeatureDependencies = {
  chat: new Set(["models"]),
  drama: new Set(["assets", "media", "models"]),
  media: new Set(["models"]),
  models: new Set(["workflows"]),
};
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
    const segments = relative.split("/");
    const appFeature = segments[0] === "app" && segments[1] === "_features";
    const appShared = segments[0] === "app" && segments[1] === "_shared";
    const layer = appFeature
      ? "features"
      : appShared
        ? "shared"
        : segments[0];
    const feature = appFeature ? segments[2] : segments[1];
    const transport =
      relative.includes("/api/") ||
      /(?:^|\/)api\.tsx?$/i.test(relative) ||
      /Api\.tsx?$/.test(relative);
    const view =
      relative.startsWith("app/_components/") ||
      relative.includes("/components/") ||
      layer === "widgets" ||
      (layer === "app" && /\/page\.tsx$/.test(relative));
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
        const targetFeature = target.startsWith("app/_features/")
          ? target.split("/")[2]
          : target.startsWith("features/")
            ? target.split("/")[1]
            : null;
        if (
          layer === "features" &&
          ((/^(app|widgets)\//.test(target) &&
            !target.startsWith("app/_features/") &&
            !target.startsWith("app/_shared/")) ||
            (targetFeature &&
              targetFeature !== feature &&
              !allowedFeatureDependencies[feature]?.has(targetFeature)))
        ) {
          errors.push(
            `${relative}: feature dependency crosses ownership: ${target}`,
          );
        }
        if (view && target.includes("/api/"))
          errors.push(`${relative}: view imports API: ${target}`);
        if (transport && name === "react")
          errors.push(`${relative}: transport depends on React`);
      }
      if (
        ["CallExpression", "NewExpression"].includes(node.type) &&
        node.callee.type === "Identifier"
      ) {
        const name = node.callee.name;
        if (
          ["fetch", "WebSocket"].includes(name) &&
          !transport
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
