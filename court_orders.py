import asyncio
import re
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

URL = "https://www.bnm.gov.my/enforcement-actions/court-orders"

# --- Date formatting ---
def format_date(date_text: str) -> str:
    if not date_text:
        return ""
    for fmt in ("%d %B %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(date_text.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_text

# --- Clean address ---
def clean_address(address_text: str) -> str:
    lines = [line.strip() for line in address_text.split("\n") if line.strip()]
    return "; ".join(lines)

# --- Split company info robustly ---
def split_company_info(raw_text: str):
    # Normalize spaces & remove invisible characters
    raw_text = re.sub(r"[\xa0\u200b]+", " ", raw_text)
    raw_text = re.sub(r"\s+", " ", raw_text).strip()
    
    # Match: Name (ID) Address
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*(.*)$", raw_text)
    if m:
        company_name = m.group(1).strip()
        company_id = f"({m.group(2).strip()})"
        address = clean_address(m.group(3).strip())
    else:
        company_name = raw_text.strip()
        company_id = ""
        address = ""
    return company_name, company_id, address

# --- Split owners robustly ---
def parse_owners(raw_text: str):
    # Normalize spaces & remove invisible chars
    raw_text = re.sub(r"[\xa0\u200b]+", " ", raw_text)
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    owners = []
    for line in lines:
        m_owner = re.match(r"^(.*?)\s*\(([^)]+)\)$", line)
        if m_owner:
            owner_name = m_owner.group(1).strip()
            owner_id = m_owner.group(2).strip()
        else:
            owner_name = line
            owner_id = ""
        owners.append({"Owner_Name": owner_name, "Owner_ID": owner_id})
    return owners

async def main():
    all_csv_data = []
    serial_no = 1

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle")

        while True:
            await page.wait_for_selector("table tbody tr")
            rows = await page.query_selector_all("table tbody tr")

            for row in rows:
                cols = await row.query_selector_all("td")
                if not cols:
                    continue

                # --- Company Name + Address ---
                td_html = await cols[1].inner_html()
                td_text = re.sub(r"<br\s*/?>", "\n", td_html, flags=re.I)
                td_text = re.sub(r"<.*?>", "", td_text).strip()
                td_text = re.sub(r"[\xa0\u200b]+", " ", td_text)  # invisible chars

                # Merge all lines
                combined = " ".join([line.strip() for line in td_text.split("\n") if line.strip()])
                company_name, company_id, address = split_company_info(combined)

                # --- Owners ---
                owner_text = (await cols[2].inner_text()).strip() if len(cols) > 2 else ""
                owners = parse_owners(owner_text)
                owner_names = "; ".join([o["Owner_Name"] for o in owners])
                owner_ids = "; ".join([o["Owner_ID"] for o in owners])

                # --- Dates ---
                raw_date_of_court_order = (await cols[3].inner_text()).strip() if len(cols) > 3 else ""
                raw_date_received = (await cols[4].inner_text()).strip() if len(cols) > 4 else ""
                date_of_court_order = format_date(raw_date_of_court_order)
                date_received = format_date(raw_date_received)

                # --- CSV row ---
                all_csv_data.append({
                    "No.": serial_no,
                    "Company_Name": company_name,
                    "Company_ID": company_id,
                    "Address": address,
                    "Company_Owner_Name": owner_names,
                    "Company_Owner_ID": owner_ids,
                    "Date of Court Order": date_of_court_order,
                    "Date Received": date_received
                })
                serial_no += 1

            # --- Pagination ---
            next_button = await page.query_selector("a:has-text('Next')")
            if not next_button:
                break
            next_class = await next_button.get_attribute("class") or ""
            if "disabled" in next_class or not await next_button.is_enabled():
                break

            first_row_text = await rows[0].inner_text()
            await next_button.click()
            await page.wait_for_function(
                """firstRow => {
                    const firstRowEl = document.querySelector('table tbody tr');
                    return firstRowEl && firstRowEl.innerText !== firstRow;
                }""",
                arg=first_row_text
            )

        await browser.close()

    # --- Save CSV ---
    df = pd.DataFrame(all_csv_data)
    df.to_csv("bnm_court_orders_cleaned.csv", index=False, encoding="utf-8-sig")
    print(f"CSV saved with {len(df)} records as bnm_court_orders_cleaned.csv")

if __name__ == "__main__":
    asyncio.run(main())