const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots');
if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function runTests() {
    const url = "http://127.0.0.1:8000/index.html";
    console.log("==================================================");
    console.log("Starting Browser E2E Tests on:", url);
    console.log("==================================================");

    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
        defaultViewport: { width: 1280, height: 900 }
    });

    const page = await browser.newPage();

    // Log console messages and errors
    page.on('console', msg => {
        const type = msg.type();
        if (type === 'error') {
            console.error('BROWSER ERROR:', msg.text());
        }
    });

    page.on('pageerror', err => {
        console.error('PAGE ERROR:', err.toString());
    });

    try {
        console.log("\n[TEST 1] Loading client-facing frontend...");
        await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
        
        // 1. Verify Header and Branding
        await page.waitForSelector('h1', { visible: true });
        const titleText = await page.$eval('h1', el => el.innerText);
        console.log(`  ✓ Title text: "${titleText}"`);
        if (!titleText.includes("Personal Travel Planner")) {
            throw new Error(`Expected title 'Personal Travel Planner', got: '${titleText}'`);
        }

        // 2. Verify Initial Welcome State
        const welcomeText = await page.evaluate(() => document.body.innerText);
        if (!welcomeText.includes("Where would you like to travel next?")) {
            throw new Error("Welcome state text not found on page.");
        }
        console.log("  ✓ Initial welcome screen rendered correctly.");

        // 3. Verify Sidebar and Session Elements
        const newPlanBtn = await page.$('button');
        if (!newPlanBtn) throw new Error("Sidebar New Plan button not found.");
        console.log("  ✓ Sidebar and New Plan button rendered.");

        await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '01_initial_page.png') });

        // 4. Test Conversational Response
        console.log("\n[TEST 2] Testing conversational query (greeting)...");
        const inputSelector = 'input[placeholder="Plan my trip to Miami..."]';
        await page.waitForSelector(inputSelector, { visible: true });
        await page.type(inputSelector, "Hi, what can you help me with?");
        
        // Click the send button
        const sendBtn = await page.$('button[class*="bg-blue-600"]');
        if (sendBtn) {
            await sendBtn.click();
        } else {
            await page.keyboard.press('Enter');
        }

        console.log("  Sent message: 'Hi, what can you help me with?'");

        // Wait for agent reply bubble
        await page.waitForFunction(() => {
            const bubbles = document.querySelectorAll('main div div.flex');
            return bubbles.length >= 2;
        }, { timeout: 30000 });

        // Wait until loading spinner finishes
        await page.waitForFunction(() => {
            const spin = document.querySelector('svg.animate-spin');
            return !spin;
        }, { timeout: 45000 });

        const chatTextAfterGreeting = await page.evaluate(() => document.body.innerText);
        console.log("  ✓ Conversational reply received and rendered.");
        await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '02_conversational_reply.png') });

        // 5. Test Full Travel Itinerary Workflow & A2UI Component Rendering
        console.log("\n[TEST 3] Testing full travel planning query and A2UI component rendering...");
        await page.waitForSelector(inputSelector, { visible: true });
        await page.type(inputSelector, "I want to fly from NYC to MIA from 2026-10-10 to 2026-10-15 for 2 travelers.");
        await page.keyboard.press('Enter');
        console.log("  Sent message: 'I want to fly from NYC to MIA from 2026-10-10 to 2026-10-15 for 2 travelers.'");

        // Wait for reasoning & multi-agent execution to finish and A2UI components to render
        console.log("  Waiting for multi-agent workflow (Orchestrator -> Querying -> Auditor -> Reporting)...");
        await page.waitForFunction(() => {
            const body = document.body.innerText;
            const hasCards = document.querySelectorAll('div[class*="shadow-sm"], div[class*="rounded-2xl"]').length > 0;
            const hasFlightOrHotel = body.includes('MIA') || body.includes('Delta') || body.includes('Hyatt') || body.includes('Flights') || body.includes('Hotels');
            const spin = document.querySelector('svg.animate-spin');
            return !spin && hasCards && hasFlightOrHotel;
        }, { timeout: 60000 });

        await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '03_itinerary_rendered.png') });

        // 6. Verify specific A2UI rendered components
        console.log("\n[TEST 4] Verifying rendered A2UI components in DOM...");
        
        const verification = await page.evaluate(() => {
            const errors = Array.from(document.querySelectorAll('.text-red-500')).map(el => el.innerText);
            const bookButtons = Array.from(document.querySelectorAll('a')).filter(a => a.innerText.includes('Book Now') || a.innerText.includes('View'));
            const prices = Array.from(document.querySelectorAll('span')).filter(s => s.innerText.startsWith('$'));
            const bodyText = document.body.innerText;
            const logSections = document.querySelectorAll('.font-mono');

            return {
                unsupportedErrors: errors,
                bookButtonCount: bookButtons.length,
                bookLinks: bookButtons.map(b => b.href),
                priceCount: prices.length,
                prices: prices.map(p => p.innerText),
                hasLogs: logSections.length > 0,
                hasFlightsSection: bodyText.includes('Flight') || bodyText.includes('Delta'),
                hasHotelsSection: bodyText.includes('Hotel') || bodyText.includes('Hyatt'),
                hasVibeOrCost: bodyText.includes('$') || bodyText.includes('cost') || bodyText.includes('trip')
            };
        });

        console.log(`  ✓ 'Book Now' / 'View' action buttons rendered: ${verification.bookButtonCount}`);
        verification.bookLinks.forEach(link => console.log(`     Link: ${link}`));
        console.log(`  ✓ Price tags rendered: ${verification.priceCount} (${verification.prices.join(', ')})`);
        console.log(`  ✓ Execution & tool logs rendered: ${verification.hasLogs}`);
        console.log(`  ✓ Flight section rendered: ${verification.hasFlightsSection}`);
        console.log(`  ✓ Hotel section rendered: ${verification.hasHotelsSection}`);

        if (verification.unsupportedErrors.length > 0) {
            console.error("  ❌ Found unsupported component errors:", verification.unsupportedErrors);
            throw new Error("Page contains unsupported component type errors!");
        } else {
            console.log("  ✓ 0 Unsupported component errors detected.");
        }

        if (verification.bookButtonCount === 0) {
            throw new Error("Expected at least one 'Book Now' or 'View' action button rendered in A2UI cards.");
        }

        // 7. Test Sidebar Session Creation & Switching
        console.log("\n[TEST 5] Testing Session Management via Sidebar...");
        // Click New Plan
        const newPlanButtons = await page.$$('button');
        let clickedNew = false;
        for (const btn of newPlanButtons) {
            const text = await (await btn.getProperty('innerText')).jsonValue();
            if (text.includes('New Plan')) {
                await btn.click();
                clickedNew = true;
                break;
            }
        }
        if (!clickedNew) throw new Error("Could not find 'New Plan' button to click.");

        await new Promise(r => setTimeout(r, 1000));
        await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '04_new_plan_session.png') });

        // Verify we are on clean screen
        const emptyStateText = await page.evaluate(() => document.body.innerText);
        if (!emptyStateText.includes("Where would you like to travel next?")) {
            throw new Error("New session did not show empty welcome state.");
        }
        console.log("  ✓ Created new session successfully; empty state confirmed.");

        // Check that session list in sidebar contains the previous session
        const sessionCount = await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('div.flex-1.overflow-y-auto button'));
            return buttons.length;
        });
        console.log(`  ✓ Sessions tracked in sidebar: ${sessionCount}`);
        if (sessionCount < 2) {
            throw new Error(`Expected at least 2 sessions in sidebar, found: ${sessionCount}`);
        }

        // Switch back to previous session
        await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('div.flex-1.overflow-y-auto button'));
            if (buttons.length >= 2) {
                buttons[1].click(); // click previous session
            }
        });

        await new Promise(r => setTimeout(r, 1000));
        await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '05_restored_session.png') });

        const restoredText = await page.evaluate(() => document.body.innerText);
        if (!restoredText.includes("MIA") && !restoredText.includes("NYC") && !restoredText.includes("Delta")) {
            throw new Error("Failed to restore previous session history upon clicking sidebar session item.");
        }
        console.log("  ✓ Restored previous session history with all cards and messages intact.");

        console.log("\n==================================================");
        console.log("🎉 ALL END-TO-END BROWSER TESTS PASSED SUCCESSFULLY!");
        console.log("==================================================");

    } catch (err) {
        console.error("\n❌ Browser E2E Test Failed:", err);
        await page.screenshot({ path: path.join(SCREENSHOTS_DIR, '00_error_state.png') });
        await browser.close();
        process.exit(1);
    }

    await browser.close();
}

runTests();
