import requests
from bs4 import BeautifulSoup

# Send GET request to event URL
event_url = "https://www.thebluealliance.com/event/2025onnew#rankings"
response = requests.get(event_url)
soup = BeautifulSoup(response.content, 'html.parser')

# Find the rankings table
rankings_table = soup.find('table', {'class': 'table-striped'})

# Dictionary to store team OPR values
opr_values = {}

if rankings_table:
    # Process each row in the rankings table
    for row in rankings_table.find_all('tr')[1:]:  # Skip header row
        columns = row.find_all('td')
        if len(columns) >= 2:  # Ensure row has enough columns
            # Extract team number and average score
            team_link = columns[1].find('a')
            if team_link:
                team_number = team_link.text.strip()
                avg_score = float(columns[3].text.strip())  # Average match score column
                opr_values[team_number] = avg_score

# Print all teams and their OPR values
print("\nAll Teams at ONT District Newmarket 2025 Event:")
for team_number, opr in sorted(opr_values.items(), key=lambda x: x[1], reverse=True):
    print(f"Team {team_number} - OPR: {opr:.2f}")
