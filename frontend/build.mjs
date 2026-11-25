// Build do frontend: TypeScript + React -> dist/ (servido pelo backend).
// Uso: npm install && npm run build
import { build } from "esbuild";
import { cpSync, mkdirSync, rmSync, copyFileSync } from "node:fs";

const watch = process.argv.includes("--watch");
rmSync("dist", { recursive: true, force: true });
mkdirSync("dist/assets", { recursive: true });
cpSync("public/fonts", "dist/assets/fonts", { recursive: true });
copyFileSync("index.html", "dist/index.html");

const options = {
  entryPoints: { app: "src/main.tsx" },
  bundle: true,
  minify: !watch,
  sourcemap: watch,
  outdir: "dist/assets",
  target: ["es2020"],
  jsx: "automatic",
  external: ["/assets/*"],
  define: { "process.env.NODE_ENV": JSON.stringify(watch ? "development" : "production") },
  nodePaths: process.env.NODE_PATH ? process.env.NODE_PATH.split(":") : [],
  logLevel: "info",
};

if (watch) {
  const { context } = await import("esbuild");
  const ctx = await context(options);
  await ctx.watch();
} else {
  await build(options);
}
