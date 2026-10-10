import fs from 'node:fs';
import path from 'node:path';

const product = 'hire';
const root = path.resolve('..');
const app = path.join(root, 'frontend', 'apps', product);
const serviceRoot = path.join(root, 'backend', 'services');
const rows = fs.readFileSync(path.join(root, 'backend', 'services.txt'), 'utf8')
  .split(/\r?\n/).map(line => line.trim()).filter(line => line && !line.startsWith('#'));
const entries = rows.map(line => line.split(/\s+/));
const names = entries.map(([name]) => name);
const forbidden = new Set(['institution','learner','curriculum','content','progress','assessment','gamification','certification','ai_tutor']);
if (!fs.existsSync(path.join(app, 'src', 'main.jsx'))) throw new Error('Hire app entry missing');
if (!names.includes('auth') || !names.includes('gateway')) throw new Error('auth and gateway are required');
if (names.some(name => forbidden.has(name))) throw new Error('LMS-only service found in Hire registry');
if (new Set(names).size !== names.length) throw new Error('duplicate registry entry');
for (const [, directory] of entries) if (!fs.existsSync(path.join(serviceRoot, directory, 'manage.py'))) throw new Error(`missing service: ${directory}`);
const actual = fs.readdirSync(serviceRoot).filter(name => fs.statSync(path.join(serviceRoot, name)).isDirectory());
if (actual.some(name => !entries.some(([, directory]) => directory === name))) throw new Error('unregistered service code found');
console.log(`Standalone Lityra Hire boundary OK (${entries.length} services)`);
