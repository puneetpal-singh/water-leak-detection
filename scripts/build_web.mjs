// Copy the committed browser export into the hosting provider's supported path.
import { cpSync, existsSync, mkdirSync, realpathSync, lstatSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'dashboard', 'web', 'dist');
const output = path.join(root, 'dist');
if (!existsSync(path.join(source, 'index.html')) || !existsSync(path.join(source, 'manifest.json'))) {
  throw new Error('Run scripts/export_dashboard.py before packaging the website');
}
// Only the verified generated dist directory may be replaced; reject redirects.
if (path.dirname(output) !== realpathSync(root) || path.basename(output) !== 'dist' ||
    (existsSync(output) && (lstatSync(output).isSymbolicLink() || realpathSync(output) !== output))) {
  throw new Error('Refusing to replace an unexpected build output path');
}
rmSync(output, { recursive: true, force: true });
mkdirSync(output, { recursive: true });
cpSync(source, output, { recursive: true });
console.log('Prepared static dashboard in dist/');
