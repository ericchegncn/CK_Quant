const PROVIDERS = Object.freeze({
  deepseek: {
    id: 'deepseek', label: 'DeepSeek', protocol: 'openai', baseUrl: 'https://api.deepseek.com',
    models: ['deepseek-v4-flash', 'deepseek-v4-pro'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 DeepSeek 开放平台创建的 API Key，不是网页账号密码。',
  },
  openai: {
    id: 'openai', label: 'OpenAI', protocol: 'openai', baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4.1-mini', 'gpt-5.2', 'gpt-5-mini', 'gpt-4.1'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 OpenAI Platform API Key；ChatGPT 订阅不能直接代替 API Key。',
  },
  anthropic: {
    id: 'anthropic', label: 'Anthropic Claude', protocol: 'anthropic', baseUrl: 'https://api.anthropic.com/v1',
    models: ['claude-sonnet-5', 'claude-sonnet-4-6', 'claude-haiku-4-5'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 Claude Console API Key；Claude 网页订阅不能直接代替 API Key。',
  },
  openrouter: {
    id: 'openrouter', label: 'OpenRouter（聚合模型）', protocol: 'openai', baseUrl: 'https://openrouter.ai/api/v1',
    models: ['~openai/gpt-latest', 'anthropic/claude-sonnet-4.6', 'google/gemini-3.7-flash'], requiresKey: true, authMethods: ['api_key', 'oauth_pkce'],
    hint: '一个 OpenRouter Key 可选择多个厂商的模型，建议点击“获取模型列表”。',
  },
  gemini: {
    id: 'gemini', label: 'Google Gemini', protocol: 'openai', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    models: ['gemini-3.7-flash', 'gemini-3.1-pro-preview', 'gemini-2.5-flash'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 Google AI Studio 创建的 Gemini API Key。',
  },
  xai: {
    id: 'xai', label: 'xAI Grok', protocol: 'openai', baseUrl: 'https://api.x.ai/v1',
    models: ['grok-4.5', 'grok-4.3'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 xAI Console 创建的 API Key。',
  },
  qwen: {
    id: 'qwen', label: '阿里云百炼 / 通义千问', protocol: 'openai', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen3.5-plus', 'qwen-plus', 'qwen-turbo'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用百炼 API Key；业务空间专属地址可在 Base URL 中覆盖。',
  },
  moonshot: {
    id: 'moonshot', label: 'Moonshot / Kimi', protocol: 'openai', baseUrl: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2.5', 'moonshot-v1-32k'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 Moonshot 开放平台 API Key。',
  },
  zhipu: {
    id: 'zhipu', label: '智谱 GLM', protocol: 'openai', baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-5', 'glm-4.7', 'glm-4-flash'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用智谱开放平台 API Key。',
  },
  siliconflow: {
    id: 'siliconflow', label: '硅基流动 SiliconFlow', protocol: 'openai', baseUrl: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V4', 'Qwen/Qwen3.5-235B-A22B'], requiresKey: true, authMethods: ['api_key'],
    hint: '使用 SiliconFlow API Key，模型名称以控制台或模型列表为准。',
  },
  ollama: {
    id: 'ollama', label: 'Ollama（本机免费模型）', protocol: 'openai', baseUrl: 'http://127.0.0.1:11434/v1',
    models: ['gpt-oss:20b', 'qwen3:8b', 'llama3.2'], requiresKey: false, authMethods: ['none'],
    hint: '无需 API Key，但必须先在本机启动 Ollama 并下载模型。',
  },
  lmstudio: {
    id: 'lmstudio', label: 'LM Studio（本机模型）', protocol: 'openai', baseUrl: 'http://127.0.0.1:1234/v1',
    models: [], requiresKey: false, authMethods: ['none'],
    hint: '无需 API Key，但必须在 LM Studio 中启动 Local Server。',
  },
  custom: {
    id: 'custom', label: '自定义 OpenAI 兼容接口', protocol: 'openai', baseUrl: '',
    models: [], requiresKey: true, authMethods: ['api_key'],
    hint: '适用于 OpenClaw、LiteLLM、OneAPI/NewAPI 等 OpenAI 兼容网关。',
  },
});

function getProvider(id) {
  return PROVIDERS[id] || PROVIDERS.custom;
}

function publicProviders() {
  return Object.values(PROVIDERS).map(({ id, label, protocol, baseUrl, models, requiresKey, authMethods, hint }) => ({
    id, label, protocol, baseUrl, models: [...models], requiresKey, authMethods: [...authMethods], hint,
  }));
}

module.exports = { PROVIDERS, getProvider, publicProviders };
