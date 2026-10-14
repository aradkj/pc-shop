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
const currentIds = new Set();
const currentData = new Set();
const currentNames = new Set();

for (const f of files) {
  const content = fs.readFileSync(f, 'utf8');
  for (const match of content.matchAll(/id="([^"]+)"/g)) currentIds.add(match[1]);
  for (const match of content.matchAll(/data-([a-z0-9-]+)/g)) currentData.add(`data-${match[1]}`);
  for (const match of content.matchAll(/name="([^"]+)"/g)) currentNames.add(match[1]);
}

const beforeIds = new Set(fs.readFileSync('scratch/ids_before.txt', 'utf8').trim().split(/\r?\n/).filter(Boolean));
const beforeData = new Set(fs.readFileSync('scratch/data_before.txt', 'utf8').trim().split(/\r?\n/).filter(Boolean));
const beforeNames = new Set(fs.readFileSync('scratch/names_before.txt', 'utf8').trim().split(/\r?\n/).filter(Boolean));

const missingIds = [...beforeIds].filter(x => !currentIds.has(x));
const missingData = [...beforeData].filter(x => !currentData.has(x));
const missingNames = [...beforeNames].filter(x => !currentNames.has(x));

console.log('--- CONTRACT VERIFICATION REPORT ---');
console.log(`Current IDs: ${currentIds.size}, Baseline IDs: ${beforeIds.size}`);
console.log(`Missing IDs: ${missingIds.length ? missingIds.join(', ') : 'NONE (0 missing)'}`);

console.log(`Current Data Attrs: ${currentData.size}, Baseline Data Attrs: ${beforeData.size}`);
console.log(`Missing Data Attrs: ${missingData.length ? missingData.join(', ') : 'NONE (0 missing)'}`);

console.log(`Current Names: ${currentNames.size}, Baseline Names: ${beforeNames.size}`);
console.log(`Missing Names: ${missingNames.length ? missingNames.join(', ') : 'NONE (0 missing)'}`);
