import fs from 'fs';
import path from 'path';

const files = fs.readdirSync('e2e').filter(f => f.endsWith('.js'));
const textPatterns = [];

for (const file of files) {
  const content = fs.readFileSync(path.join('e2e', file), 'utf8');
  const lines = content.split('\n');
  lines.forEach((line, idx) => {
    if (line.includes('toContainText') || line.includes('toHaveText') || line.includes('has-text')) {
      textPatterns.push(`${file}:${idx + 1}: ${line.trim()}`);
    }
  });
}

fs.writeFileSync('scratch/e2e_text_assertions.txt', textPatterns.join('\n'));
console.log(`Found ${textPatterns.length} text assertions in e2e.`);
