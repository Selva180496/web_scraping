from playwright.sync_api import sync_playwright, TimeoutError
import csv
import time
from datetime import datetime

def flatten_html(cell):
    """Flatten HTML into plain text for CSV."""
    text = cell.inner_text()
    return " ".join(text.split())  # remove extra spaces/newlines

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

def scrape_aob_sanctions():
    url = "https://www.sc.com.my/aob/aobs-sanctions"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        time.sleep(2)

        # Get all dropdowns for the years
        dropdowns = page.query_selector_all("a.st-header")

        with open("aob_sanctions_all_years.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                'Year', 'No.', 'Nature of Misconduct', 'Auditor',
                'Brief Description of Misconduct', 'Action Taken', "Date of AOB's Action",
                'Dataset', 'Topics', 'Source Name', 'Country', 'Source URL'
            ])

            for dropdown in dropdowns:
                year_text = dropdown.inner_text().split("Sanctions")[0].strip()
                print(f"Scraping: {year_text} Sanctions")

                try:
                    # Expand dropdown by clicking it
                    dropdown.click()
                    time.sleep(1)  # small wait for table to render

                    # The table is the next sibling of the dropdown
                    wrapper = dropdown.evaluate_handle("el => el.nextElementSibling")
                    table = wrapper.query_selector("table")
                    if not table:
                        print(f"No table found for {year_text}, skipping...")
                        continue

                    rows = table.query_selector_all("tr")
                    rowspan_tracker = {}

                    for row in rows:
                        cols = row.query_selector_all("td")
                        if not cols:
                            continue  # skip header or empty rows
                        row_data = []
                        col_idx = 0

                        while col_idx < 6:  # each table has 6 columns
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

                        if len(row_data) < 6:
                            row_data += [""] * (6 - len(row_data))

                        # Format the date column before writing
                        row_data[5] = format_date(row_data[5])

                        if any(cell.strip() for cell in row_data):  # only if at least one column has text
                            writer.writerow([
                                year_text + " Sanctions"
                            ] + row_data + [
                                "Suruhanjaya Sekuriti Securities commission malaysia",  # Dataset
                                "fraud",  # Topics
                                "Suruhanjaya Sekuriti Securities commission malaysia",  # Source Name
                                "Malaysia",  # Country
                                url  # Source URL
                            ])

                except Exception as e:
                    print(f"Error scraping {year_text}: {e}")

        browser.close()
        print("Scraping completed. Data saved to aob_sanctions_all_years.csv")

if __name__ == "__main__":
    scrape_aob_sanctions()