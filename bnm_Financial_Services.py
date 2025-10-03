import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from bs4 import BeautifulSoup

URL = "https://www.bnm.gov.my/-/ea-pn-20230901"

async def scrape_table():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(URL)
        await page.wait_for_selector("table.standard-table")

        html = await page.inner_html("table.standard-table")
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")

    # Headers: only lower-level or standalone
    headers = ["No.", "Entities", "Compound (RM, million) under - S. 253 FSA", "Compound (RM, million) under - S. 92", "Total (RM, million)"]

    rows = []
    for tr in soup.find_all("tr")[2:]:  # skip header rows
        cells = tr.find_all("td")
        row = [td.get_text(strip=True) for td in cells]
        # Pad if necessary (for the Total row)
        if len(row) < len(headers):
            row = [""] * (len(headers) - len(row)) + row
        rows.append(row)

    df = pd.DataFrame(rows, columns=headers)
    return df

if __name__ == "__main__":
    df = asyncio.run(scrape_table())
    print(df)
    df.to_csv("bnm_Financial_Services.csv", index=False)