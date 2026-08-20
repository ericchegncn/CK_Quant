# CK Quant Desktop

CK Quant Desktop is a Windows application for users who do not want to learn Linux, Docker commands or strategy code before managing a quantitative-trading server.

## Product boundaries

- License: one-time 10,000 USDT lifetime purchase, bound to the current machine code.
- Private signing key: manufacturer machine only; never packaged or committed.
- Private strategies: local application data only; never used as the one-click research template.
- Research template: a 15m adaptation of Freqtrade's public `SampleStrategy` in `resources/ckq_public_template.py`.
- AI credentials, SSH credentials and Telegram token: encrypted with Windows `safeStorage`.
- Backtests: serial Docker jobs with explicit fees, post-parse slippage and deterministic evidence gates.
- Deployment: paper deployment requires confirmation; enabling live capital is a separate manual step.

## Customer workflow

1. Open the installer and copy the displayed machine code.
2. Send that code to the CK Quant vendor and paste the returned registration code.
3. Add a server or use the local CK Quant Docker container.
4. Configure an optional OpenAI-compatible model provider and notifications.
5. Use the public-template one-click workflow, or import a private strategy for local manual work.
6. Review backtest evidence before confirming any paper deployment.

## Local development

```powershell
cd desktop
npm install
npm test
npm run dev
```

Build the Windows NSIS installer:

```powershell
npm run build
```

The installer is written to `desktop/dist/`. This directory, runtime `data/`, development specifications and all manufacturer private files are ignored by Git.

Initialize the manufacturer signing key and open the registration-code console only on the authorized vendor machine:

```powershell
npm run license:init
npm run license:admin
```

Never distribute `desktop/private/`.
