import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import re
from datetime import datetime

# ------------------------
# Date formatter
# ------------------------
def format_date(date_string: str) -> str:
    if not date_string or date_string.strip() == "":
        return "-"
    date_string = date_string.strip()
    date_formats = [
        '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y',
        '%d %b %Y', '%d %B %Y', '%Y-%m-%d',
        '%d.%m.%Y', '%d-%b-%y'
    ]
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_string, fmt)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_string

# ------------------------
# Extract all text and links in a <td>
# ------------------------
async def extract_cell_text(td):
    """Extracts all text content in a <td> efficiently."""
    html = await td.inner_html()
    # Get all links
    links = await td.query_selector_all("a")
    link_entries = [
        f"{(await link.inner_text()).strip()} {await link.get_attribute('href')}"
        if (await link.inner_text()).strip() else await link.get_attribute('href')
        for link in links
        if await link.get_attribute('href')
    ]
    # Get plain text
    text_content = (await td.inner_text()).strip()
    entries = [line.strip() for line in text_content.split("\n") if line.strip()]
    # Combine
    for le in link_entries:
        if le not in entries:
            entries.append(le)
    return " | ".join(entries) if entries else "-"

# ------------------------
# Main scraper
# ------------------------
async def scrape_bnm():
    url = "https://www.bnm.gov.my/financial-consumer-alert-list"
    all_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-images", "--disable-css"]
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.goto(url)
        await page.wait_for_selector("table")

        # Total pages
        info_text = await page.inner_text("div.dataTables_info")
        total_entries = int(re.search(r"of\s+(\d+)\s+entries", info_text).group(1))
        rows_per_page = 10
        total_pages = (total_entries + rows_per_page - 1) // rows_per_page

        print(f"🔎 Found {total_pages} pages ({total_entries} entries). Starting scrape...")

        for page_num in range(1, total_pages + 1):
            print(f"📄 Scraping page {page_num}/{total_pages}...")
            rows = await page.query_selector_all("table tbody tr")

            # Extract all rows concurrently
            tasks = []
            for row in rows:
                tasks.append(scrape_row(row))
            all_data.extend(await asyncio.gather(*tasks))

            # Click "Next"
            if page_num < total_pages:
                next_button = await page.query_selector("a.paginate_button.next")
                if next_button:
                    await next_button.click()
                    await page.wait_for_selector("table tbody tr")

        await browser.close()

    # Save to Excel
    df = pd.DataFrame(all_data)
    if not df.empty:
        df.to_excel("bnm_financial_alerts_playwright_fast.xlsx", index=False, engine="openpyxl")
        print(f"✅ Saved {len(df)} records from {total_pages} pages to Excel")
        print(df.head())
    else:
        print("❌ No data found")

# ------------------------
# Row scraper
# ------------------------
async def scrape_row(row):
    cols = await row.query_selector_all("td")
    if len(cols) < 3:
        return {}
    entity_name = (await cols[0].inner_text()).strip() or "-"
    website_url = await extract_cell_text(cols[1])
    date_added = format_date((await cols[2].inner_text()).strip())
    remarks = (await cols[3].inner_text()).strip() if len(cols) > 3 else "-"
    return {
                    "Group(sdn Type)":"Company",
                    "Entity Name": entity_name,
                    "Website/URL": website_url,
                    "Dataset": "Bank Negara Malaysia",
                    "Source URL": "https://www.bnm.gov.my/financial-consumer-alert-list",
                    "Topics": "Fraud",
                    "Source Name": "Bank Negara Malaysia",
                    "Country": "Malaysia",
                    "Date Added": date_added
    }

if __name__ == "__main__":
    asyncio.run(scrape_bnm())