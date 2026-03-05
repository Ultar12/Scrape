import os
import asyncio
import re
import requests
from fastapi import FastAPI
from playwright.async_api import async_playwright

app = FastAPI()

# Configuration
LOGIN_URL = "http://timesms.net/login"
USERNAME = "Whatsapp_Worker"
PASSWORD = "Whatsapp_Worker"
TELEGRAM_TOKEN = "8722377131:AAEr1SsPWXKy8m4WbTJBe7vrN03M2hZozhY"
CHAT_ID = "-1003644661262"

# Cache to prevent duplicate telegram messages
sent_otps = set()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}", flush=True)

async def solve_captcha(page):
    try:
        # Locate the text containing the math problem
        content = await page.content()
        # Regex to find 'number + number'
        match = re.search(r'(\d+)\s*\+\s*(\d+)', content)
        if match:
            num1, num2 = match.groups()
            result = int(num1) + int(num2)
            print(f"Solved Captcha: {num1} + {num2} = {result}", flush=True)
            return str(result)
    except Exception as e:
        print(f"Captcha Error: {e}", flush=True)
    return "0"

async def run_scraper():
    print("Background scraper starting...", flush=True)
    async with async_playwright() as p:
        # Launch with flags for Render's Linux environment
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print(f"Navigating to {LOGIN_URL}...", flush=True)
            await page.goto(LOGIN_URL, timeout=60000)

            # Login Process
            await page.fill("input[name='username']", USERNAME)
            await page.fill("input[name='password']", PASSWORD)
            
            captcha_val = await solve_captcha(page)
            # Selector based on common 'answer' input name
            await page.fill("input[name='captcha']", captcha_val)
            
            await page.click("button:has-text('LOGIN')")
            await page.wait_for_url("**/dashboard", timeout=20000)
            print("Login successful", flush=True)

            while True:
                # Navigation to SMS Reports
                print("Navigating to SMS Reports...", flush=True)
                await page.click("button.navbar-toggler") # The three-line menu
                await asyncio.sleep(1)
                await page.click("text=SMS Reports")
                
                # Extract Data
                await page.wait_for_selector("button:has-text('Show Report')")
                await page.click("button:has-text('Show Report')")
                await asyncio.sleep(3) # Wait for table to load

                rows = await page.locator("table tr").all()
                # Skip header, check first few rows
                for row in rows[1:6]:
                    cols = await row.locator("td").all_inner_texts()
                    if len(cols) >= 4:
                        number = cols[1]
                        sms_text = cols[3]
                        msg_id = f"{number}_{sms_text}"

                        if msg_id not in sent_otps:
                            print(f"New SMS found for {number}", flush=True)
                            send_telegram(f"New OTP\nNumber: {number}\nMessage: {sms_text}")
                            sent_otps.add(msg_id)

                # Keep cache from growing too large
                if len(sent_otps) > 100:
                    sent_otps.clear()

                print("Waiting 60 seconds...", flush=True)
                await asyncio.sleep(60)
                await page.reload()

        except Exception as e:
            print(f"Scraper encountered an error: {e}", flush=True)
        finally:
            await browser.close()

@app.on_event("startup")
async def startup_event():
    # Run the scraper loop in the background
    asyncio.create_task(run_scraper())

@app.get("/")
@app.head("/")
async def health_check():
    return {"status": "active"}
