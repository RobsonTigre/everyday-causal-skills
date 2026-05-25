// Render assets/cover/index.html as a sequence of PNG frames using
// headless Chrome (via puppeteer-core) so the GIF is a literal recording
// of what the browser draws — not a re-implementation.
//
// This is a real-time capture: the page animation runs at its natural
// wall-clock speed and we screenshot as fast as Chrome can produce
// frames. The achieved fps is logged to .render/fps.txt; the encode
// step below uses that same fps so the GIF plays back at the exact
// same speed as the live HTML (typing cadence, cursor blink, ASCII
// fade — all matched).
//
// Frames are captured with omitBackground:true and clipped to the
// terminal's bounding box (60,60 to 1140,340 inside the 1200x400
// stage), so each PNG is 2160x560 with alpha=0 in the rounded-corner
// cutouts. The encode step composites them onto the page's #0f0f10
// background and runs ffmpeg's full-palette pipeline (which renders
// cleanly without the ASCII "ghost" artifact gifski's frame-diff
// optimization produces on this content).
//
// Run capture:
//   node assets/cover/render-gif.mjs
//
// Then encode:
//   cd assets/cover
//   FPS=$(cat .render/fps.txt | tr -d '[:space:]')
//   ffmpeg -y -framerate "$FPS" -i .render/frames/frame_%05d.png \
//     -filter_complex "color=c=0x0f0f10:s=1080x280:r=$FPS,format=rgba[bg];\
// [0:v]scale=1080:280:flags=lanczos[fg];\
// [bg][fg]overlay=shortest=1:format=rgb,split[a][b];\
// [a]palettegen=stats_mode=full:max_colors=256[p];\
// [b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle:new=0" \
//     -loop 0 cover.gif

import { mkdir, rm, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const renderRequire = createRequire(resolve(__dirname, '.render/package.json'));
const puppeteer = renderRequire('puppeteer-core');

const COVER_DIR  = __dirname;
const HTML_PATH  = resolve(COVER_DIR, 'index.html');
const RENDER_DIR = resolve(COVER_DIR, '.render');
const FRAMES_DIR = resolve(RENDER_DIR, 'frames');
const FPS_FILE   = resolve(RENDER_DIR, 'fps.txt');
const CHROME_BIN = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const MAX_SECONDS = 60;

async function run() {
  await rm(FRAMES_DIR, { recursive: true, force: true });
  await mkdir(FRAMES_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: CHROME_BIN,
    headless: true,
    defaultViewport: { width: 1200, height: 400, deviceScaleFactor: 2 },
    args: [
      '--hide-scrollbars',
      '--disable-features=PaintHolding',
      '--font-render-hinting=none',
    ],
  });

  try {
    const page = await browser.newPage();
    // Stop the animation from starting until fonts are ready and we're
    // about to capture, so the first frame isn't rendered with a
    // fallback font.
    await page.setJavaScriptEnabled(false);
    await page.goto(pathToFileURL(HTML_PATH).href, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.setJavaScriptEnabled(true);
    // Reload starts the JS now, with the font cache already populated.
    await page.reload({ waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);

    // Strip the page background and the window's drop shadow so that
    // screenshotting with omitBackground:true yields a PNG where the
    // terminal's rounded-corner cutouts are alpha=0. This lets the GIF
    // sit cleanly on any README background (light or dark) without a
    // surrounding margin.
    await page.addStyleTag({ content: `
      html, body, .stage { background: transparent !important; }
      .window { box-shadow: none !important; }
    ` });

    // Anchor on "ASCII at full opacity (mid-hold)" for both the start
    // and the end of the capture window. The 700ms fade-in finishes
    // before the 4500ms hold begins, so opacity === '1' identifies the
    // stable hold phase unambiguously. Using the same anchor for start
    // and end produces a seamlessly looping GIF — start and end frames
    // are visually identical.
    const asciiAtFullOpacity = () => {
      const el = document.getElementById('ascii');
      return el.classList.contains('show') &&
             getComputedStyle(el).opacity === '1';
    };

    await page.waitForFunction(asciiAtFullOpacity, {
      polling: 'raf',
      timeout: 30_000,
    });

    let frameIdx = 0;
    let sawAsciiHidden = false;
    const tStart = performance.now();
    const deadline = tStart + MAX_SECONDS * 1000;

    while (performance.now() < deadline) {
      const buf = await page.screenshot({
        type: 'png',
        optimizeForSpeed: true,
        omitBackground: true,
        // Crop to the .window element's bounding box inside the stage
        // (1080x280 centered in 1200x400). Rounded-corner pixels outside
        // the window's silhouette become alpha=0 in the PNG.
        clip: { x: 60, y: 60, width: 1080, height: 280 },
      });
      const name = `frame_${String(frameIdx).padStart(5, '0')}.png`;
      await writeFile(resolve(FRAMES_DIR, name), buf);
      frameIdx++;

      const state = await page.evaluate(() => {
        const el = document.getElementById('ascii');
        return {
          shown: el.classList.contains('show'),
          opacity: getComputedStyle(el).opacity,
        };
      });
      if (!state.shown) sawAsciiHidden = true;
      if (sawAsciiHidden && state.shown && state.opacity === '1') {
        // We've returned to "ASCII fully visible, in hold" — same
        // state as frame 0. Drop this last duplicate so the GIF loops
        // seamlessly when a player repeats it.
        break;
      }
    }

    const totalSec = (performance.now() - tStart) / 1000;
    const fps = frameIdx / totalSec;
    await writeFile(FPS_FILE, fps.toFixed(3) + '\n');
    console.log(
      `Captured ${frameIdx} frames in ${totalSec.toFixed(2)}s ` +
      `(${fps.toFixed(2)} fps). fps written to ${FPS_FILE}.`
    );
  } finally {
    await browser.close();
  }
}

run().catch(err => { console.error(err); process.exit(1); });
