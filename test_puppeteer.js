const puppeteer = require('puppeteer');

(async () => {
    const url = "http://127.0.0.1:8000/index.html";
    const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('request', request => {
      console.log('REQUEST:', request.url());
    });
    page.on('response', response => {
      console.log('RESPONSE:', response.url(), response.status());
    });
    
    console.log("Navigating to " + url);
    await page.goto(url, { waitUntil: 'networkidle2' });
    
    let successes = 0;
    for (let i = 0; i < 10; i++) {
        console.log(`Test iteration ${i+1}...`);
        
        await page.waitForSelector('input[placeholder="Plan my trip to Miami..."]', { visible: true });
        await page.type('input[placeholder="Plan my trip to Miami..."]', 'Search for flights to Tokyo for 1 adult from JFK leaving tomorrow returning next week');
        await page.keyboard.press('Enter');
        
        try {
            await page.waitForFunction(() => {
                const textNodes = document.body.innerText;
                const hasUiList = document.querySelectorAll('div').length > 0;
                return hasUiList && textNodes.includes('Tokyo');
            }, { timeout: 10000 });
            console.log(`Iteration ${i+1} SUCCESS`);
            successes++;
        } catch(err) {
            console.error(`Iteration ${i+1} FAILED`);
        }
        await page.reload({ waitUntil: 'networkidle2' });
    }
    
    console.log(`Finished 10 consecutive tests. Successes: ${successes}`);
    await browser.close();
    if (successes !== 10) process.exit(1);
})();
