const fs = require('fs');
const zlib = require('zlib');

function findEndOfCentralDirectory(buffer) {
  const minimum = Math.max(0, buffer.length - 65557);
  for (let offset = buffer.length - 22; offset >= minimum; offset -= 1) {
    if (buffer.readUInt32LE(offset) === 0x06054b50) return offset;
  }
  throw new Error('ZIP 文件缺少中央目录');
}

function readZipEntries(filename) {
  const buffer = fs.readFileSync(filename);
  const eocd = findEndOfCentralDirectory(buffer);
  const count = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);
  const entries = [];
  for (let index = 0; index < count; index += 1) {
    if (buffer.readUInt32LE(offset) !== 0x02014b50) throw new Error('ZIP 中央目录损坏');
    const method = buffer.readUInt16LE(offset + 10);
    const compressedSize = buffer.readUInt32LE(offset + 20);
    const uncompressedSize = buffer.readUInt32LE(offset + 24);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const localOffset = buffer.readUInt32LE(offset + 42);
    const name = buffer.subarray(offset + 46, offset + 46 + nameLength).toString('utf8');
    entries.push({ name, method, compressedSize, uncompressedSize, localOffset });
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return { buffer, entries };
}

function extractEntry(zip, entry) {
  const { buffer } = zip;
  if (buffer.readUInt32LE(entry.localOffset) !== 0x04034b50) throw new Error('ZIP 本地文件头损坏');
  const nameLength = buffer.readUInt16LE(entry.localOffset + 26);
  const extraLength = buffer.readUInt16LE(entry.localOffset + 28);
  const start = entry.localOffset + 30 + nameLength + extraLength;
  const compressed = buffer.subarray(start, start + entry.compressedSize);
  if (entry.method === 0) return compressed;
  if (entry.method === 8) return zlib.inflateRawSync(compressed);
  throw new Error(`暂不支持 ZIP 压缩方法 ${entry.method}`);
}

function readLargestResultJson(filename) {
  const zip = readZipEntries(filename);
  const candidates = zip.entries.filter((entry) =>
    entry.name.toLowerCase().endsWith('.json') &&
    !entry.name.toLowerCase().endsWith('.meta.json') &&
    !entry.name.toLowerCase().includes('_config.json'));
  const entry = candidates.sort((a, b) => b.uncompressedSize - a.uncompressedSize)[0];
  if (!entry) throw new Error('回测 ZIP 中没有结果 JSON');
  return JSON.parse(extractEntry(zip, entry).toString('utf8'));
}

module.exports = { readZipEntries, extractEntry, readLargestResultJson };
