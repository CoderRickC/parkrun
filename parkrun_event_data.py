from pathlib import Path
import requests
from openpyxl import Workbook
from bs4 import BeautifulSoup
from datetime import datetime

# 🏃 parkrun event
event = "stretford"
url = f"https://www.parkrun.org.uk/{event}/results/latestresults/"

# 📖 Create workbook and sheet
wb = Workbook()
ws = wb.active

# 🌐 Request headers
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}

# 📥 Fetch the page
response = requests.get(url, headers=headers)

results_data = []

if response.status_code == 200:
    html = BeautifulSoup(response.content, "html.parser")
    table = html.find("table", class_="Results-table Results-table--compact js-ResultsTable")

    for row in table.find_all("tr"):  # type: ignore
        columns = row.find_all("td")
        if len(columns) >= 6:
            position = columns[0].text.strip()

            name_element = columns[1].find("a")
            name = name_element.text.strip() if name_element else "Unknown Runner"

            parkruns_elements = columns[1].find("div", class_="detailed")
            parkruns = parkruns_elements.text.strip() if parkruns_elements else "-"

            gender_element = columns[2].find("div", class_="compact")
            gender = gender_element.text.strip() if gender_element else "-"

            age_group_element = columns[3].find("div", class_="compact")
            age_group = age_group_element.text.strip() if age_group_element else "-"

            club_element = columns[4].find("a")
            club = club_element.text.strip() if club_element else "-"

            time_element = columns[5].find("div", class_="compact")
            time = time_element.text.strip() if time_element else "-"

            first_timer_element = columns[5].find("div", class_="detailed")
            first_timer = first_timer_element.text.strip() if first_timer_element else "-"

            result = {
                "Position": position,
                "Name": name,
                "Time": time,
                "Age Group": age_group,
                "Gender": gender,
                "Club": club,
                "First Timer & PB": first_timer
            }
            results_data.append(result)

# 🧩 Add Excel headers
xl_headers = ["Position", "Name", "Time", "Age Group", "Gender", "Club", "First Timers / PB"]
ws.append(xl_headers) #type: ignore

# 🪣 Add results data
for data in results_data:
    ws.append([ #type: ignore
        data["Position"],
        data["Name"],
        data["Time"],
        data["Age Group"],
        data["Gender"],
        data["Club"],
        data["First Timer & PB"]
    ])

# 💾 Set up smart save path
BASE_DIR = Path(__file__).resolve().parent
SAVE_DIR = BASE_DIR
SAVE_DIR.mkdir(parents=True, exist_ok=True)

save_path = SAVE_DIR / f"{event}_results.xlsx"

wb.save(save_path)
print(f"✅ Data saved successfully at: {save_path}")

