#!/usr/bin/env node
/**
 * puppeteer_runner.js — Browser automation runner for Hope AI agent.
 *
 * Commands:
 *   navigate <url>
 *   screenshot <url> <output_path> [fullPage]
 *   interact <url> <actions_json>
 *   pdf <url> <output_path>
 *   capture_api <url> <pattern>
 *   test
 */

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const HEADLESS_ENV = (process.env.PUPPETEER_HEADLESS || 'true').toLowerCase();

async function launchBrowser() {
  return puppeteer.launch({
    headless: HEADLESS_ENV === 'true' ? 'shell' : false,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
}

function output(data) {
  console.log(JSON.stringify(data));
}

// ── navigate ───────────────────────────────────────────────────────────
async function navigate(url) {
  const browser = await launchBrowser();
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    let text = await page.evaluate(() => document.body.innerText);
    if (text.length > 8000) text = text.substring(0, 8000) + '\n…[truncated]';
    output({ ok: true, url, title: await page.title(), text });
  } catch (err) {
    output({ ok: false, error: err.message });
  } finally {
    await browser.close();
  }
}

// ── screenshot ─────────────────────────────────────────────────────────
async function screenshot(url, outputPath, fullPage) {
  const browser = await launchBrowser();
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    const resolved = path.resolve(outputPath);
    fs.mkdirSync(path.dirname(resolved), { recursive: true });
    await page.screenshot({ path: resolved, fullPage: !!fullPage });
    output({ ok: true, path: resolved });
  } catch (err) {
    output({ ok: false, error: err.message });
  } finally {
    await browser.close();
  }
}

// ── interact ───────────────────────────────────────────────────────────
async function interact(url, actionsJson) {
  const browser = await launchBrowser();
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

    const actions = JSON.parse(actionsJson);
    const extractions = [];

    for (const step of actions) {
      switch (step.action) {
        case 'click':
          await page.waitForSelector(step.selector, { timeout: 10000 });
          await page.click(step.selector);
          break;
        case 'type':
          await page.waitForSelector(step.selector, { timeout: 10000 });
          await page.type(step.selector, step.text || '');
          break;
        case 'wait':
          await page.waitForSelector(step.selector, { timeout: 15000 });
          break;
        case 'extract': {
          await page.waitForSelector(step.selector, { timeout: 10000 });
          const extracted = await page.$eval(step.selector, el => el.innerText);
          extractions.push({ selector: step.selector, text: extracted });
          break;
        }
        default:
          extractions.push({ warning: `Unknown action: ${step.action}` });
      }
    }

    let finalText = await page.evaluate(() => document.body.innerText);
    if (finalText.length > 8000) finalText = finalText.substring(0, 8000) + '\n…[truncated]';
    output({ ok: true, extractions, finalText });
  } catch (err) {
    output({ ok: false, error: err.message });
  } finally {
    await browser.close();
  }
}

// ── pdf ────────────────────────────────────────────────────────────────
async function pdf(url, outputPath) {
  const browser = await launchBrowser();
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    const resolved = path.resolve(outputPath);
    fs.mkdirSync(path.dirname(resolved), { recursive: true });
    await page.pdf({ path: resolved, format: 'A4', printBackground: true });
    output({ ok: true, path: resolved });
  } catch (err) {
    output({ ok: false, error: err.message });
  } finally {
    await browser.close();
  }
}

// ── capture_api ────────────────────────────────────────────────────────
async function captureApi(url, pattern) {
  const browser = await launchBrowser();
  try {
    const page = await browser.newPage();
    const captured = [];

    await page.setRequestInterception(true);
    page.on('request', (req) => {
      req.continue();
    });
    page.on('response', async (res) => {
      if (res.url().includes(pattern)) {
        let body = '';
        try {
          body = await res.text();
          if (body.length > 4000) body = body.substring(0, 4000) + '…[truncated]';
        } catch (_) {
          body = '[could not read body]';
        }
        captured.push({
          url: res.url(),
          method: res.request().method(),
          status: res.status(),
          body,
        });
      }
    });

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    // Give a little extra time for late responses
    await new Promise(r => setTimeout(r, 2000));
    output({ ok: true, captured });
  } catch (err) {
    output({ ok: false, error: err.message });
  } finally {
    await browser.close();
  }
}

// ── test ───────────────────────────────────────────────────────────────
async function test() {
  const browser = await launchBrowser();
  try {
    const page = await browser.newPage();
    await page.goto('https://example.com', { waitUntil: 'networkidle2', timeout: 30000 });
    const title = await page.title();
    const testScreenshot = path.resolve(__dirname, 'test_screenshot.png');
    await page.screenshot({ path: testScreenshot });
    output({ ok: true, title, screenshot: testScreenshot });
  } catch (err) {
    output({ ok: false, error: err.message });
  } finally {
    await browser.close();
  }
}

// ── main ───────────────────────────────────────────────────────────────
(async () => {
  const [,, command, ...args] = process.argv;
  try {
    switch (command) {
      case 'navigate':
        await navigate(args[0]);
        break;
      case 'screenshot':
        await screenshot(args[0], args[1], args[2] === 'fullPage');
        break;
      case 'interact':
        await interact(args[0], args[1]);
        break;
      case 'pdf':
        await pdf(args[0], args[1]);
        break;
      case 'capture_api':
        await captureApi(args[0], args[1]);
        break;
      case 'test':
        await test();
        break;
      default:
        output({ ok: false, error: `Unknown command: ${command}. Available: navigate, screenshot, interact, pdf, capture_api, test` });
    }
  } catch (err) {
    output({ ok: false, error: err.message });
  }
})();
