// Copy the committed browser export into the hosting provider's supported path.
import { cpSync, existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'dashboard', 'web', 'dist');
const output = path.join(root, 'dist');
if (!existsSync(path.join(source, 'index.html')) || !existsSync(path.join(source, 'data.json'))) {
  throw new Error('Run scripts/export_dashboard.py before packaging the website');
}
mkdirSync(output, { recursive: true });
cpSync(source, output, { recursive: true });
console.log('Prepared static dashboard in dist/');
