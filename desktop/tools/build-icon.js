const { app, BrowserWindow, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');

function makeIco(images) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  const directory = Buffer.alloc(images.length * 16);
  let offset = header.length + directory.length;
  images.forEach(({ size, data }, index) => {
    const base = index * 16;
    directory[base] = size === 256 ? 0 : size;
    directory[base + 1] = size === 256 ? 0 : size;
    directory[base + 2] = 0;
    directory[base + 3] = 0;
    directory.writeUInt16LE(1, base + 4);
    directory.writeUInt16LE(32, base + 6);
    directory.writeUInt32LE(data.length, base + 8);
    directory.writeUInt32LE(offset, base + 12);
    offset += data.length;
  });
  return Buffer.concat([header, directory, ...images.map((item) => item.data)]);
}

app.whenReady().then(async () => {
  const source = process.argv[2];
  if (!source || !fs.existsSync(source)) throw new Error('请提供存在的 PNG 源文件路径');
  const sourceData = fs.readFileSync(source).toString('base64');
  const renderer = new BrowserWindow({ show: false, webPreferences: { sandbox: true } });
  await renderer.loadURL('data:text/html,<html><body></body></html>');
  const composedDataUrl = await renderer.webContents.executeJavaScript(`new Promise((resolve, reject) => {
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 512;
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.onload = () => {
      ctx.beginPath(); ctx.arc(256, 256, 256, 0, Math.PI * 2); ctx.clip();
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 512, 512);
      ctx.drawImage(img, 0, 0, 512, 512);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => reject(new Error('图标源加载失败'));
    img.src = 'data:image/png;base64,${sourceData}';
  })`);
  renderer.destroy();
  const image = nativeImage.createFromDataURL(composedDataUrl);
  if (image.isEmpty()) throw new Error('无法读取 PNG 图标');
  const buildDir = path.resolve(__dirname, '../build');
  fs.mkdirSync(buildDir, { recursive: true });
  fs.writeFileSync(path.join(buildDir, 'icon.png'), image.resize({ width: 512, height: 512, quality: 'best' }).toPNG());
  const images = [16, 32, 48, 64, 128, 256].map((size) => ({
    size,
    data: image.resize({ width: size, height: size, quality: 'best' }).toPNG(),
  }));
  fs.writeFileSync(path.join(buildDir, 'icon.ico'), makeIco(images));
  console.log('CK Quant PNG 与多尺寸 ICO 已生成');
  app.quit();
});
