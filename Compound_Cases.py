from playwright.sync_api import sync_playwright, TimeoutError
import csv
import time

def flatten_html(cell):
    """Flatten HTML into plain text for CSV."""
    text = cell.inner_text()
    return " ".join(text.split())  # remove extra spaces/newlines

def scrape_cases_compounded():
    main_url = "https://www.sc.com.my/regulation/enforcement/actions"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(main_url)
        time.sleep(2)

        # Scroll to bottom to ensure all content is loaded
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # Get all anchor tags and filter "Cases Compounded" links
        all_links = page.query_selector_all("a")
        year_links = []
        seen_texts = set()
        for link in all_links:
            text = link.inner_text().strip()
            if text.startswith("Cases Compounded In") and text not in seen_texts:
                seen_texts.add(text)
                href = link.get_attribute("href")
                if not href:
                    continue
                full_url = href if href.startswith("http") else "https://www.sc.com.my" + href
                year_links.append({"year": text, "url": full_url})

        year_links.sort(key=lambda x: x["year"], reverse=True)

        with open("sc_cases_compounded_all_years.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Columns fixed for this page
            writer.writerow([
                'Year', 'No.', 'Nature of Offence', 'Offender(s)',
                'Facts of Case', 'Date Charged',
                'Dataset', 'Topics', 'Source Name', 'Country', 'Source URL'
            ])

            for link_info in year_links:
                year = link_info["year"]
                url = link_info["url"]
                print(f"Scraping: {year} -> {url}")

                try:
                    page.goto(url, timeout=30000)
                    try:
                        page.wait_for_selector("table", timeout=10000)
                    except TimeoutError:
                        print(f"No table found for {year}, skipping...")
                        continue

                    table = page.query_selector("table")
                    rows = table.query_selector_all("tr")
                    rowspan_tracker = {}

                    for row in rows:
                        cols = row.query_selector_all("td")
                        row_data = []
                        col_idx = 0

                        while col_idx < 5:  # 5 columns for this page
                            if col_idx in rowspan_tracker and rowspan_tracker[col_idx]['rows_left'] > 0:
                                row_data.append(rowspan_tracker[col_idx]['text'])
                                rowspan_tracker[col_idx]['rows_left'] -= 1
                                col_idx += 1
                                continue

                            if cols:
                                cell = cols.pop(0)
                                text = flatten_html(cell)
                                colspan = int(cell.get_attribute("colspan") or 1)
                                rowspan = int(cell.get_attribute("rowspan") or 1)

                                for _ in range(colspan):
                                    row_data.append(text)
                                    if rowspan > 1:
                                        rowspan_tracker[col_idx] = {'text': text, 'rows_left': rowspan-1}
                                    col_idx += 1
                            else:
                                row_data.append("")
                                col_idx += 1

                        # Pad row_data to exactly 5 columns
                        if len(row_data) < 5:
                            row_data += [""] * (5 - len(row_data))

                        # Only write rows that have at least one non-empty cell
                        if any(cell.strip() for cell in row_data):
                            writer.writerow([
                                year
                            ] + row_data + [
                                "Suruhanjaya Sekuriti Securities commission malaysia",  # Dataset
                                "fraud",  # Topics
                                "Suruhanjaya Sekuriti Securities commission malaysia",  # Source Name
                                "Malaysia",  # Country
                                url  # Source URL
                            ])

                except Exception as e:
                    print(f"Error scraping {year}: {e}")

        browser.close()
        print("Scraping completed. Data saved to sc_cases_compounded_all_years.csv")


if __name__ == "__main__":
    scrape_cases_compounded()