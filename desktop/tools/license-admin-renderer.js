const $ = (selector) => document.querySelector(selector);
let lastRegistrationCode = '';

function showStatus(message, tone = '') {
  $('#status').className = `status ${tone}`.trim();
  $('#status').textContent = message;
}

$('#issue').addEventListener('click', async () => {
  $('#issue').disabled = true;
  showStatus('正在签发…');
  try {
    const result = await window.licenseAdmin.issue($('#machine').value, $('#customer').value);
    if (!result?.ok) {
      showStatus(result?.error || '签发失败，请检查机器码', 'err');
      return;
    }
    lastRegistrationCode = result.code;
    $('#code').value = result.code;
    $('#copy').disabled = false;
    showStatus(`签发成功 · 授权ID ${result.licenseId}`, 'ok');
  } catch (error) {
    showStatus(`签发工具发生错误：${error?.message || error}`, 'err');
  } finally {
    $('#issue').disabled = false;
  }
});

$('#copy').addEventListener('click', () => {
  window.licenseAdmin.copy(lastRegistrationCode);
  showStatus('注册码已复制', 'ok');
});

window.licenseAdmin.status()
  .then((result) => {
    if (!result?.ready) {
      showStatus('授权密钥未初始化，请先运行 npm run license:init', 'err');
      $('#issue').disabled = true;
    }
  })
  .catch((error) => {
    showStatus(`无法读取授权密钥状态：${error?.message || error}`, 'err');
    $('#issue').disabled = true;
  });
