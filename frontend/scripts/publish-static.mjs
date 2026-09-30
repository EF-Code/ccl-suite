import { copyFile, mkdir, readdir, rm } from "node:fs/promises"
import { resolve } from "node:path"

const frontendDirectory = resolve(import.meta.dirname, "..")
const repositoryDirectory = resolve(frontendDirectory, "..")
const builtAssetsDirectory = resolve(frontendDirectory, "dist/assets")
const staticDirectory = resolve(repositoryDirectory, "static")
const publishedAssetsDirectory = resolve(staticDirectory, "assets")
const generatedAssetName = /^[A-Za-z0-9._-]+-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$/

const builtEntries = await readdir(builtAssetsDirectory, { withFileTypes: true })
if (builtEntries.some((entry) => !entry.isFile() || !generatedAssetName.test(entry.name))) {
  throw new Error("Vite emitted an unexpected asset path; refusing to publish it.")
}

await mkdir(publishedAssetsDirectory, { recursive: true })
const newAssetNames = new Set(builtEntries.map((entry) => entry.name))
for (const entry of builtEntries) {
  await copyFile(
    resolve(builtAssetsDirectory, entry.name),
    resolve(publishedAssetsDirectory, entry.name),
  )
}
await copyFile(resolve(frontendDirectory, "dist/index.html"), resolve(staticDirectory, "index.html"))

const existingEntries = await readdir(publishedAssetsDirectory, { withFileTypes: true })
for (const entry of existingEntries) {
  if (entry.isFile() && generatedAssetName.test(entry.name) && !newAssetNames.has(entry.name)) {
    await rm(resolve(publishedAssetsDirectory, entry.name))
  }
}

console.log(`Published ${builtEntries.length} hashed frontend assets and the dashboard HTML.`)
