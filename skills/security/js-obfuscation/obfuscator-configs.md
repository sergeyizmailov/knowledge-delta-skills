# javascript-obfuscator Configs & CLI

Install: `npm install javascript-obfuscator -g`

Pipeline: Terser first, then obfuscate — cleaner input = better output.

```bash
npx terser input.js --compress --mangle --output minified.js
javascript-obfuscator minified.js --output final.js [options]
```

## Balanced (production, good tradeoff)

~1.5x runtime slowdown, ~50-80% file size increase.

```javascript
{
    compact: true,
    controlFlowFlattening: true,
    controlFlowFlatteningThreshold: 0.75,
    deadCodeInjection: true,
    deadCodeInjectionThreshold: 0.4,
    identifierNamesGenerator: 'hexadecimal',
    numbersToExpressions: true,
    selfDefending: true,
    simplify: true,
    splitStrings: true,
    splitStringsChunkLength: 10,
    stringArray: true,
    stringArrayCallsTransform: true,
    stringArrayEncoding: ['base64'],
    stringArrayIndexShift: true,
    stringArrayRotate: true,
    stringArrayShuffle: true,
    stringArrayWrappersCount: 2,
    stringArrayWrappersType: 'function',
    stringArrayWrappersChainedCalls: true,
    stringArrayThreshold: 0.75,
    transformObjectKeys: true,
    unicodeEscapeSequence: false
}
```

CLI:
```bash
javascript-obfuscator input.js --output out.js \
  --compact true --self-defending true \
  --string-array true --string-array-encoding rc4 \
  --control-flow-flattening true --control-flow-flattening-threshold 0.75 \
  --dead-code-injection true --dead-code-injection-threshold 0.4 \
  --split-strings true --split-strings-chunk-length 10 \
  --transform-object-keys true
```

## Maximum (anti-reversing, anti-analysis)

~3-5x runtime slowdown, ~200% file size increase. `rc4` encoding: 30-50% slower than `base64`, much harder to reverse.

```javascript
{
    compact: true,
    controlFlowFlattening: true,
    controlFlowFlatteningThreshold: 1,
    deadCodeInjection: true,
    deadCodeInjectionThreshold: 1,
    debugProtection: true,
    debugProtectionInterval: 4000,
    disableConsoleOutput: true,
    domainLock: ['.yourdomain.com'],
    domainLockRedirectUrl: 'https://google.com',
    identifierNamesGenerator: 'hexadecimal',
    numbersToExpressions: true,
    renameGlobals: true,
    selfDefending: true,
    simplify: true,
    splitStrings: true,
    splitStringsChunkLength: 5,
    stringArray: true,
    stringArrayCallsTransform: true,
    stringArrayEncoding: ['rc4'],
    stringArrayIndexShift: true,
    stringArrayRotate: true,
    stringArrayShuffle: true,
    stringArrayWrappersCount: 5,
    stringArrayWrappersType: 'function',
    stringArrayWrappersChainedCalls: true,
    stringArrayThreshold: 1,
    transformObjectKeys: true,
    unicodeEscapeSequence: true
}
```

CLI:
```bash
javascript-obfuscator input.js --output out.js \
  --compact true --self-defending true \
  --string-array true --string-array-encoding rc4 --string-array-threshold 1 \
  --control-flow-flattening true --control-flow-flattening-threshold 1 \
  --dead-code-injection true --dead-code-injection-threshold 1 \
  --debug-protection true --debug-protection-interval 4000 \
  --disable-console-output true \
  --domain-lock .yourdomain.com \
  --domain-lock-redirect-url https://google.com \
  --rename-globals true --numbers-to-expressions true \
  --split-strings true --split-strings-chunk-length 5 \
  --transform-object-keys true --unicode-escape-sequence true
```

## Lightweight (performance-sensitive, mobile)

Minimal overhead.

```javascript
{
    compact: true,
    identifierNamesGenerator: 'hexadecimal',
    selfDefending: true,
    simplify: true,
    stringArray: true,
    stringArrayEncoding: [],
    stringArrayThreshold: 0.5
}
```

## Key Options Reference

| Option | Effect | Risk |
|--------|--------|------|
| `stringArrayEncoding: ['rc4']` | RC4 encrypts all strings | 30-50% slower |
| `selfDefending: true` | Breaks if code is beautified | Forces compact:true |
| `debugProtection: true` | Freezes browser when DevTools opens | Intentional |
| `debugProtectionInterval: 4000` | Repeats debug check every 4s | Persistent freeze |
| `domainLock: ['.domain.com']` | Code only runs on your domain | VirusTotal/sandbox → redirect |
| `controlFlowFlattening: true` | Switch-case state machine | Stack overflow on deep nesting at threshold 1 |
| `renameGlobals: true` | Renames global vars | **BREAKS** code referencing globals from external scripts |
| `deadCodeInjection: true` | Inserts junk code | File size +200% at threshold 1 |
| `disableConsoleOutput: true` | Overrides console methods | No console output |
