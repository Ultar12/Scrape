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
    print("🚀 Background scraper starting...") # This should show in logs
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            print(f"🔗 Navigating to {LOGIN_URL}...")
            await page.goto(LOGIN_URL)
            
            # Solve Captcha
            captcha_result = await solve_captcha(page)
            print(f"🤖 Captcha identified as: {captcha_result}")
            
            await page.fill("input[name='username']", USERNAME)
            await page.fill("input[name='password']", PASSWORD)
            await page.fill("input[name='captcha']", captcha_result)
            
            print("🔑 Attempting login click...")
            await page.click("button[type='submit']")
            
            # Wait to see if login worked
            await page.wait_for_url("**/dashboard", timeout=10000)
            print("✅ Login Successful!")

            while True:
                print("🔄 Refreshing SMS Reports...")
                # ... rest of your code ...
                await asyncio.sleep(60)
        except Exception as e:
            print(f"❌ Scraper Error: {e}")
        finally:
            await browser.close()


@app.on_event("startup")
async def startup_event():
    # Start the scraper in the background
    asyncio.create_task(run_scraper())

@app.get("/")
def read_root():
    return {"status": "Bot is running"}
