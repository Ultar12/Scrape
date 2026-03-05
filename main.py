import os
import asyncio
import re
from fastapi import FastAPI
from playwright.async_api import async_playwright
import requests

app = FastAPI()

# Configuration
LOGIN_URL = "http://timesms.net/login"
REPORT_URL = "http://timesms.net/client/SMSCDRS"
USERNAME = "Whatsapp_Worker"
PASSWORD = "Whatsapp_Worker"
TELEGRAM_TOKEN = "8722377131:AAEr1SsPWXKy8m4WbTJBe7vrN03M2hZozhY"
CHAT_ID = "-1003644661262"

last_otp_cache = set()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})

async def solve_captcha(page):
    # Locate the math text (e.g., "What is 1 + 9 = ?")
    captcha_text = await page.locator("label[for='captcha'], .form-group:has(input[name='captcha'])").inner_text()
    # Use regex to find numbers
    numbers = re.findall(r'\d+', captcha_text)
    if len(numbers) >= 2:
        result = int(numbers[0]) + int(numbers[1])
        return str(result)
    return "0"

async def run_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. Login Phase
            await page.goto(LOGIN_URL)
            await page.fill("input[name='username']", USERNAME)
            await page.fill("input[name='password']", PASSWORD)
            
            captcha_result = await solve_captcha(page)
            await page.fill("input[name='captcha']", captcha_result) # Adjust selector if name is different
            await page.click("button[type='submit']")
            await page.wait_for_url("**/dashboard")

            while True:
                # 2. Navigation Phase
                # Open menu and click SMS Reports
                await page.click(".navbar-toggler, .three-line-nav-selector") # Adjust selector based on actual ID
                await page.click("text=SMS Reports")
                await page.wait_for_selector("button:has-text('Show Report')")
                
                # 3. Data Extraction
                await page.click("button:has-text('Show Report')")
                await asyncio.sleep(2) # Wait for table update
                
                rows = await page.locator("table tr").all()
                for row in rows[1:5]: # Check top 4 rows
                    cols = await row.locator("td").all_inner_texts()
                    if len(cols) > 4:
                        phone = cols[1]
                        sms_content = cols[3]
                        
                        unique_id = f"{phone}-{sms_content}"
                        if unique_id not in last_otp_cache:
                            send_telegram(f"📩 New OTP\nNum: {phone}\nMsg: {sms_content}")
                            last_otp_cache.add(unique_id)
                
                # Keep cache small
                if len(last_otp_cache) > 50:
                    last_otp_cache.clear()

                await asyncio.sleep(60) # Wait 1 minute before refreshing
                await page.reload()

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

@app.on_event("startup")
async def startup_event():
    # Start the scraper in the background
    asyncio.create_task(run_scraper())

@app.get("/")
def read_root():
    return {"status": "Bot is running"}
