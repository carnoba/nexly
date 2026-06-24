import asyncio
import re
import random
import os
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from nexly_utils import log_activity, save_lead

# ==========================================
# REGEX & CONFIG (From Elite Scraper)
# ==========================================
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+(?:\s*@\s*|\s*\[at\]\s*|\s*\(at\)\s*)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)
LINKEDIN_REGEX = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?", re.IGNORECASE)
PHONE_REGEX = re.compile(r"(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")

CRAWL_KEYWORDS = ["contact", "about", "team", "staff", "meet", "owner", "leadership", "founder", "bio"]
JUNK_DOMAINS = {"example.com", "sentry.io", "wix.com", "google.com", "facebook.com", "instagram.com"}

class NexlyHunter:
    def __init__(self, headless=True, config=None):
        self.headless = headless
        self.config = config or {}
        self.playwright = None
        self.browser = None
        self.context = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

    async def start(self):
        log_activity("Hunter", "Engine", "Initializing Stealth Engine...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=random.choice(self.user_agents)
        )
        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    async def stop(self):
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        log_activity("Hunter", "Engine", "Shutdown.")

    async def recursive_web_crawler(self, start_url):
        results = {"emails": [], "linkedin": [], "phones": []}
        visited = set()
        base_domain = urlparse(start_url).netloc
        if not base_domain: return results

        pages_to_visit = [start_url]
        # Look for contact/about links on main page first
        try:
            page = await self.context.new_page()
            await page.goto(start_url, wait_until="domcontentloaded", timeout=15000)
            links = await page.locator("a").all()
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    full_url = urljoin(start_url, href)
                    if any(kw in full_url.lower() for kw in CRAWL_KEYWORDS) and urlparse(full_url).netloc == base_domain:
                        pages_to_visit.append(full_url)
            await page.close()
        except: pass

        pages_to_visit = list(set(pages_to_visit))[:5] # Limit to 5 sub-pages

        for url in pages_to_visit:
            if url in visited: continue
            visited.add(url)
            try:
                p = await self.context.new_page()
                log_activity("Hunter", "Crawl", f"Scanning: {url}")
                await p.goto(url, wait_until="domcontentloaded", timeout=10000)
                content = await p.content()
                
                # Emails
                raw_emails = EMAIL_REGEX.findall(content)
                for e in raw_emails:
                    e_clean = e.replace(" ", "").lower()
                    if not any(d in e_clean for d in JUNK_DOMAINS):
                        results["emails"].append(e_clean)
                
                # LinkedIn
                results["linkedin"].extend(LINKEDIN_REGEX.findall(content))
                # Phones
                results["phones"].extend(PHONE_REGEX.findall(content))
                
                await p.close()
                if results["emails"] and results["linkedin"]: break
            except:
                continue
        
        results["emails"] = list(set(results["emails"]))
        results["linkedin"] = list(set(results["linkedin"]))
        results["phones"] = list(set(results["phones"]))
        return results

    async def hunt(self, niche, city, limit=10, campaign_id=None, progress_callback=None):
        """Ultra-Performance Hunt (Inspired by Elite Scraper)"""
        page = await self.context.new_page()
        query = f"{niche} in {city}"
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        
        req_email = self.config.get('emails', True)
        req_phone = self.config.get('phones', False)
        req_li = self.config.get('linkedin', False)

        log_activity("Hunter", "Maps", f"Seeding Search: {query}")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(5)

        # Scroll results feed
        for i in range(5):
            try:
                feed = page.locator('div[role="feed"]')
                await feed.evaluate("el => el.scrollTop += 3000")
                await asyncio.sleep(2)
            except: break

        links = await page.locator("a.hfpxzc").all()
        log_activity("Hunter", "Radar", f"Acquired {len(links)} targets. Filtering...")

        found_leads = 0
        processed_names = set()

        for i in range(min(len(links), limit * 3)): # Look at more than limit to satisfy filters
            if found_leads >= limit: break
            
            try:
                link = links[i]
                name = await link.get_attribute("aria-label")
                if not name or name in processed_names: continue
                processed_names.add(name)

                log_activity("Hunter", "Target", f"Opening Case: {name}")
                await link.click()
                await asyncio.sleep(3)

                # Extract Basic Panel Data
                phone = "N/A"
                try:
                    p_btn = page.locator('button[aria-label^="Phone:"]')
                    if await p_btn.count() > 0:
                        phone = (await p_btn.first.get_attribute("aria-label")).replace("Phone: ", "").strip()
                except: pass

                website = "N/A"
                try:
                    w_link = page.locator('a[aria-label^="Website:"]')
                    if await w_link.count() > 0:
                        website = await w_link.first.get_attribute("href")
                except: pass

                # Deep Intelligence (Crawler)
                intel = {"emails": [], "linkedin": [], "phones": [phone] if phone != "N/A" else []}
                if website != "N/A":
                    log_activity("Hunter", "DeepScan", f"Running recursive crawl on {website}")
                    deep_data = await self.recursive_web_crawler(website)
                    intel["emails"].extend(deep_data["emails"])
                    intel["linkedin"].extend(deep_data["linkedin"])
                    intel["phones"].extend(deep_data["phones"])

                # Filter Logic
                has_email = len(intel["emails"]) > 0
                has_phone = len(intel["phones"]) > 0
                has_li = len(intel["linkedin"]) > 0

                meets = True
                if req_email and not has_email: meets = False
                if req_phone and not has_phone: meets = False
                if req_li and not has_li: meets = False

                if meets:
                    lead_data = {
                        "campaign_id": campaign_id,
                        "business_name": name,
                        "email": intel["emails"][0] if has_email else "N/A",
                        "phone": intel["phones"][0] if has_phone else "N/A",
                        "website": website,
                        "linkedin_url": intel["linkedin"][0] if has_li else "N/A",
                        "niche": niche, "city": city, "status": "Found"
                    }
                    if save_lead(lead_data):
                        found_leads += 1
                        log_activity("Hunter", "Success", f"Lead Saved: {name}")
                        if progress_callback:
                            progress_callback(found_leads / limit)
                else:
                    log_activity("Hunter", "Skip", f"{name} (Missing required data)")

            except Exception as e:
                continue

        await page.close()
        log_activity("Hunter", "Mission", f"Mission Complete. {found_leads} leads captured.")
