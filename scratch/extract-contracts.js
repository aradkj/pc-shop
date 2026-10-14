import fs from 'fs';
import path from 'path';

function getFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      getFiles(fullPath, fileList);
    } else if (file.endsWith('.html') || file.endsWith('.js')) {
      fileList.push(fullPath);
    }
  }
  return fileList;
}

const files = getFiles('frontend');
const ids = new Set();
const dataAttrs = new Set();
const names = new Set();

for (const f of files) {
  const content = fs.readFileSync(f, 'utf8');
  for (const match of content.matchAll(/id="([^"]+)"/g)) ids.add(match[1]);
  for (const match of content.matchAll(/data-([a-z0-9-]+)/g)) dataAttrs.add(`data-${match[1]}`);
  for (const match of content.matchAll(/name="([^"]+)"/g)) names.add(match[1]);
}

if (!fs.existsSync('scratch')) fs.mkdirSync('scratch', { recursive: true });
fs.writeFileSync('scratch/ids_before.txt', [...ids].sort().join('\n'));
fs.writeFileSync('scratch/data_before.txt', [...dataAttrs].sort().join('\n'));
fs.writeFileSync('scratch/names_before.txt', [...names].sort().join('\n'));
console.log(`Saved ${ids.size} IDs, ${dataAttrs.size} data attributes, ${names.size} names.`);
