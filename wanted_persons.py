import csv
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from deep_translator import GoogleTranslator

# ----------------------------
# Setup Google Translator
# ----------------------------
translator = GoogleTranslator(source='ms', target='en')

def is_numeric_field(value: str) -> bool:
    """Skip translation for numeric or mostly numeric fields"""
    clean = re.sub(r"[^\w]", "", value)
    return clean.isdigit() or re.match(r"^\d{2,4}[-/]\d{1,2}[-/]\d{1,4}$", value)

def translate_text(text: str):
    """Translate Malay text to English using Google Translator"""
    if not text.strip() or is_numeric_field(text):
        return text, 0.0

    start = time.time()
    try:
        translated = translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        translated = text
    end = time.time()
    return translated, end - start

# ----------------------------
# HTML Flattening
# ----------------------------
def flatten_html(cell):
    text = cell.inner_text()
    return " ".join(text.split())

# ----------------------------
# Scraper
# ----------------------------
def scrape_rmp_wanted():
    url = "https://www.rmp.gov.my/orang-dikehendaki"

    headers = ['Name', 'Alias', 'ID Number', 'Gender', 'Ethnicity',
               'Date of Birth', 'Address', 'Report No', 'Offense', 'Notes']

    label_map = {
        "Nama": "Name",
        "Nama Gelaran": "Alias",
        "No. KP": "ID Number",
        "Jantina": "Gender",
        "Bangsa": "Ethnicity",
        "Tarikh lahir": "Date of Birth",
        "Alamat": "Address",
        "Repot No": "Report No",
        "Kesalahan": "Offense",
        "Catatan": "Notes"
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(2000)

        # Click "Expand All"
        page.click("#ctl00_Contentplaceholder2_C068_ctl00_ctl00_ctl00_listsControl_listExpandAllLnk")
        page.wait_for_selector(
            "#ctl00_Contentplaceholder2_C068_ctl00_ctl00_ctl00_listsControl_listCollapseAllLnk",
            state="visible",
            timeout=15000
        )

        tables = page.query_selector_all("table")
        tables = [t for t in tables if t.query_selector("strong")]

        with open("rmp_wanted_deeptrans.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            total_translation_time = 0
            translation_count = 0

            for table in tables:
                rows = table.query_selector_all("tr")
                row_dict = {header: "" for header in headers}

                for row in rows:
                    cells = row.query_selector_all("td")
                    i = 0
                    while i < len(cells):
                        label_el = cells[i].query_selector("strong")
                        if label_el:
                            label = flatten_html(label_el).replace(":", "").strip()
                            value = flatten_html(cells[i+1]) if i+1 < len(cells) else ""
                            header = label_map.get(label, label)

                            if value.strip():
                                value_en, latency = translate_text(value)
                                total_translation_time += latency
                                if latency > 0:
                                    translation_count += 1
                            else:
                                value_en = ""

                            # Convert Date of Birth to yyyy-mm-dd
                            if header == "Date of Birth" and value_en.strip():
                                try:
                                    dob = datetime.strptime(value_en.strip(), "%d/%m/%Y")
                                    value_en = dob.strftime("%Y-%m-%d")
                                except ValueError:
                                    pass

                            row_dict[header] = value_en
                            i += 2
                        else:
                            i += 1

                writer.writerow([row_dict[h] for h in headers])

        browser.close()

        print(f"✅ Scraping completed. Data saved to rmp_wanted_deeptrans.csv")
        if translation_count > 0:
            print(f"Average translation latency per field: {total_translation_time/translation_count:.3f} sec")
            print(f"Total translation time for all fields: {total_translation_time:.2f} sec")

if __name__ == "__main__":
    start_total = time.time()
    scrape_rmp_wanted()
    print(f"Total execution time: {time.time() - start_total:.2f} sec")