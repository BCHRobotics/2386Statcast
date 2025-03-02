from flask import Flask, render_template, request
import requests
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get API key from environment variable
TBA_API_KEY = os.getenv('TBA_API_KEY')
if not TBA_API_KEY:
    raise ValueError("No TBA_API_KEY found in environment variables")

headers = {
    'X-TBA-Auth-Key': TBA_API_KEY
}

@app.route('/', methods=['GET'])
def index():
    # Get initial events data
    team_key = "frc2386"
    year = 2025
    team_events_url = f"https://www.thebluealliance.com/api/v3/team/{team_key}/events/{year}"
    events_response = requests.get(team_events_url, headers=headers)
    events_data = events_response.json()
    
    return render_template('index.html', events=events_data)

@app.route('/matches', methods=['POST'])
def get_matches():
    event_key = request.form['event_key']
    team_key = "frc2386"
    
    # Get matches data
    team_matches_url = f"https://www.thebluealliance.com/api/v3/team/{team_key}/event/{event_key}/matches"
    matches_response = requests.get(team_matches_url, headers=headers)
    matches_data = matches_response.json()
    
    # Get OPR data for the event
    opr_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/oprs"
    opr_response = requests.get(opr_url, headers=headers)
    opr_data = opr_response.json() if opr_response.status_code == 200 else {'oprs': {}}
    
    # Get team list for the event
    event_teams_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams"
    teams_response = requests.get(event_teams_url, headers=headers)
    teams_data = teams_response.json()
    
    # Create team info dictionary
    team_info = {}
    for team in teams_data:
        team_info[team['key']] = {
            'team_number': team['team_number'],
            'nickname': team.get('nickname', 'Unknown Team')
        }
    
    # Process matches by type
    qual_matches = []
    quarter_matches = []
    semi_matches = []
    final_matches = []
    
    for match in matches_data:
        match_number = match['match_number']
        set_number = match.get('set_number', 1)
        
        if match['comp_level'] == 'qm':
            qual_matches.append((match_number, match))
        elif match['comp_level'] == 'qf':
            quarter_matches.append((set_number, match_number, match))
        elif match['comp_level'] == 'sf':
            semi_matches.append((set_number, match_number, match))
        elif match['comp_level'] == 'f':
            final_matches.append((match_number, match))
    
    # Sort matches
    qual_matches.sort(key=lambda x: x[0])
    quarter_matches.sort(key=lambda x: (x[0], x[1]))
    semi_matches.sort(key=lambda x: (x[0], x[1]))
    final_matches.sort(key=lambda x: x[0])
    
    return render_template('matches.html', 
                         qual_matches=qual_matches,
                         quarter_matches=quarter_matches,
                         semi_matches=semi_matches,
                         final_matches=final_matches,
                         event_key=event_key,
                         opr_data=opr_data,
                         team_info=team_info)

@app.route('/analysis', methods=['POST'])
def analyze_match():
    event_key = request.form['event_key']
    match_key = request.form['match_key']
    
    # Get match data
    match_url = f"https://www.thebluealliance.com/api/v3/match/{match_key}"
    match_response = requests.get(match_url, headers=headers)
    match_data = match_response.json()
    
    print("Match Data:", json.dumps(match_data, indent=2))
    
    # Check if we got valid match data
    if not match_data or 'Error' in match_data:
        return "Match data not found", 404
        
    # Extract event key from match key
    event_key = match_key.split('_')[0]
    
    # Initialize empty data structures for OPR and rankings
    opr_data = {'oprs': {}, 'dprs': {}, 'ccwms': {}}
    rankings_data = {'rankings': []}
    
    # Only try to get OPR and rankings if it's not a future event
    current_year = 2025  # You might want to calculate this dynamically
    event_year = int(event_key[:4])
    
    if event_year <= current_year:
        try:
            # Get OPR data
            opr_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/oprs"
            opr_response = requests.get(opr_url, headers=headers)
            if opr_response.status_code == 200:
                opr_data = opr_response.json()
            
            # Get rankings data
            rankings_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/rankings"
            rankings_response = requests.get(rankings_url, headers=headers)
            if rankings_response.status_code == 200:
                rankings_data = rankings_response.json()
        except Exception as e:
            print(f"Error fetching OPR/rankings data: {str(e)}")
    else:
        print(f"Future event ({event_year}), skipping OPR and rankings data")

    try:
        # Process team stats
        red_teams = match_data.get('alliances', {}).get('red', {}).get('team_keys', [])
        blue_teams = match_data.get('alliances', {}).get('blue', {}).get('team_keys', [])
        
        print("Red Teams:", red_teams)
        print("Blue Teams:", blue_teams)
        
        if not red_teams or not blue_teams:
            print("No teams found in match data")
            return "No teams found in match data", 404
        
        team_stats = {}
        red_opr_sum = 0
        blue_opr_sum = 0
        
        # Get team list for the event
        event_teams_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams"
        teams_response = requests.get(event_teams_url, headers=headers)
        teams_data = teams_response.json()
        
        # Create team info dictionary
        team_info = {}
        for team in teams_data:
            team_info[team['key']] = {
                'team_number': team['team_number'],
                'nickname': team.get('nickname', 'Unknown Team')
            }
        
        # Get ranking info for each team
        for team in red_teams + blue_teams:
            print(f"\nProcessing team: {team}")
            # Remove the 'frc' prefix if it exists in the OPR data
            team_no_prefix = team.replace('frc', '') if team.startswith('frc') else team
            team_with_prefix = f"frc{team_no_prefix}" if not team.startswith('frc') else team
            
            print(f"Looking up OPR data for {team_with_prefix}")
            opr = opr_data.get('oprs', {}).get(team_with_prefix, 0)
            dpr = opr_data.get('dprs', {}).get(team_with_prefix, 0)
            ccwm = opr_data.get('ccwms', {}).get(team_with_prefix, 0)
            print(f"Found OPR: {opr}, DPR: {dpr}, CCWM: {ccwm}")
            
            team_stats[team] = {
                'opr': round(opr, 2),
                'dpr': round(dpr, 2),
                'ccwm': round(ccwm, 2),
                'ranking': None,
                'record': None
            }
            
            # Find team's ranking info
            for rank in rankings_data.get('rankings', []):
                if rank.get('team_key') == team_with_prefix:
                    team_stats[team]['ranking'] = rank.get('rank')
                    record = rank.get('record', {})
                    team_stats[team]['record'] = f"{record.get('wins', 0)}-{record.get('losses', 0)}-{record.get('ties', 0)}"
                    print(f"Found ranking: {rank.get('rank')}, record: {team_stats[team]['record']}")
                    break
        
        # Calculate alliance OPR sums
        for team in red_teams:
            red_opr_sum += team_stats[team]['opr']
        for team in blue_teams:
            blue_opr_sum += team_stats[team]['opr']
        
        # print("\nFinal team_stats:", json.dumps(team_stats, indent=2))  # Commented out debug print
        
        return render_template('analysis.html', 
                             match_data={'alliances': {'red': {'team_keys': red_teams}, 
                                                     'blue': {'team_keys': blue_teams}}},
                             team_stats=team_stats,
                             red_opr_sum=round(red_opr_sum, 2),
                             blue_opr_sum=round(blue_opr_sum, 2),
                             opr_data=opr_data,
                             team_info=team_info)
    
    except Exception as e:
        print(f"Error processing match data: {str(e)}")
        return f"Error processing match data: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
