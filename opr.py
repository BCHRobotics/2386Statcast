from flask import Flask, render_template, request, redirect, url_for
import requests
import json
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables from .env file
# This allows secure storage of API keys and other sensitive information
load_dotenv()

# Initialize Flask application
app = Flask(__name__)

# Get The Blue Alliance API key from environment variables
# An API key is required to access The Blue Alliance's data
TBA_API_KEY = os.getenv('TBA_API_KEY')
if not TBA_API_KEY:
    raise ValueError("No TBA_API_KEY found in environment variables")

# Define headers for The Blue Alliance API requests
# X-TBA-Auth-Key is required for all TBA API requests
headers = {
    'X-TBA-Auth-Key': TBA_API_KEY
}

@app.route('/', methods=['GET'])
def index():
    """
    Main page route handler. Fetches initial data for the application:
    1. FRC Team 2386's events for the current year
    2. A list of all FRC teams for the autocomplete feature
    
    Returns:
        Rendered index.html template with event and team data
    """
    # Get initial events data for Team 2386 (Trojans)
    team_key = "frc2386"
    
    # Dynamically set the competition year to the current year
    year = datetime.now().year
    team_events_url = f"https://www.thebluealliance.com/api/v3/team/{team_key}/events/{year}"
    events_response = requests.get(team_events_url, headers=headers)
    events_data = events_response.json()
    
    # Get all teams data for autocomplete functionality
    # First check if teamsdata.json exists
    teams_data = []
    teamsdata_file = 'teamsdata.json'
    teams_data_date = None
    
    # Try to load data from the file if it exists
    if os.path.exists(teamsdata_file):
        try:
            # Get the modification time of the teamsdata file
            mod_time = os.path.getmtime(teamsdata_file)
            teams_data_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            
            with open(teamsdata_file, 'r') as f:
                teams_data = json.load(f)
        except Exception as e:
            print(f"Error loading teams data from file: {e}")
            teams_data = []
    
    # If we couldn't load data from file, fetch from API
    if not teams_data:
        # Start with the first page (page 0) of teams
        teams_url = f"https://www.thebluealliance.com/api/v3/teams/{year}/0"
        teams_response = requests.get(teams_url, headers=headers)
        
        # If the first page of teams is available, get more pages
        if teams_response.status_code == 200:
            teams_data.extend(teams_response.json())
            
            # TBA API returns data in pages of ~500 teams, so we need to get additional pages
            # Continue fetching pages until we get an empty or error response
            page = 1
            while True:
                next_page_url = f"https://www.thebluealliance.com/api/v3/teams/{year}/{page}"
                next_page_response = requests.get(next_page_url, headers=headers)
                
                if next_page_response.status_code == 200 and next_page_response.json():
                    teams_data.extend(next_page_response.json())
                    page += 1
                else:
                    break
            
            # Save the fetched data to a file for future use
            try:
                with open(teamsdata_file, 'w') as f:
                    json.dump(teams_data, f)
                    
                # Update the modification time after saving the file
                mod_time = os.path.getmtime(teamsdata_file)
                teams_data_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Error saving teams data to file: {e}")
    
    # Format team data for autocomplete by extracting just the needed fields
    autocomplete_teams = []
    for team in teams_data:
        team_number = team.get('team_number')
        team_name = team.get('nickname', 'Unknown Team')
        if team_number and team_name:
            autocomplete_teams.append({
                'team_number': team_number,
                'team_name': team_name
            })
    
    # If no teams were found (possibly due to API issues or future year data),
    # provide some example teams for testing purposes
    if not autocomplete_teams:
        # Add some well-known FRC teams as examples
        example_teams = [
            {'team_number': 2386, 'team_name': 'Trojans'},
            {'team_number': 254, 'team_name': 'The Cheesy Poofs'},
            {'team_number': 1114, 'team_name': 'Simbotics'},
            {'team_number': 118, 'team_name': 'Robonauts'},
            {'team_number': 33, 'team_name': 'Killer Bees'}
        ]
        autocomplete_teams = example_teams
    
    return render_template('index.html', events=events_data, teams=autocomplete_teams, teams_data_date=teams_data_date)

@app.route('/matches', methods=['POST'])
def get_matches():
    """
    Handle POST request to fetch and display matches for a specific team at a specific event.
    Processes match data and categorizes them by competition level (qualification, quarterfinals, etc.)
    
    Form parameters:
        event_key: The event identifier (e.g., '2025nytr')
        team_number: The FRC team number to filter matches for
        
    Returns:
        Rendered matches.html template with organized match data
    """
    event_key = request.form['event_key']
    team_number = request.form['team_number']
    team_key = f"frc{team_number}"
    
    # Get all matches data for the specified event
    event_matches_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/matches"
    matches_response = requests.get(event_matches_url, headers=headers)
    matches_data = matches_response.json()
    
    # Get OPR (Offensive Power Rating) data for the event
    # OPR is a metric that estimates a team's offensive contribution to their alliance's score
    opr_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/oprs"
    opr_response = requests.get(opr_url, headers=headers)
    opr_data = opr_response.json() if opr_response.status_code == 200 else {'oprs': {}}
    
    # Get team list for the event to provide team names alongside team numbers
    event_teams_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams"
    teams_response = requests.get(event_teams_url, headers=headers)
    teams_data = teams_response.json()
    
    # Create a lookup dictionary for team information
    team_info = {}
    for team in teams_data:
        team_info[team['key']] = {
            'team_number': team['team_number'],
            'nickname': team.get('nickname', 'Unknown Team')
        }
    
    # Process matches by competition level
    # Initialize lists for each match type
    qual_matches = []          # Qualification matches
    quarter_matches = []       # Quarterfinal matches
    semi_matches = []          # Semifinal matches
    final_matches = []         # Final matches
    
    # Initialize lists for matches that include the specified team
    team_qual_matches = []
    team_quarter_matches = []
    team_semi_matches = []
    team_final_matches = []
    
    # Categorize each match by type and check if the specified team is participating
    for match in matches_data:
        match_number = match['match_number']
        set_number = match.get('set_number', 1)
        
        # Check if the specified team is in this match (either red or blue alliance)
        team_in_match = (
            team_key in match['alliances']['red']['team_keys'] or 
            team_key in match['alliances']['blue']['team_keys']
        )
        
        # Categorize based on competition level (qm=qualification, qf=quarterfinal, sf=semifinal, f=final)
        if match['comp_level'] == 'qm':
            qual_matches.append((match_number, match))
            if team_in_match:
                team_qual_matches.append((match_number, match))
        elif match['comp_level'] == 'qf':
            quarter_matches.append((set_number, match_number, match))
            if team_in_match:
                team_quarter_matches.append((set_number, match_number, match))
        elif match['comp_level'] == 'sf':
            semi_matches.append((set_number, match_number, match))
            if team_in_match:
                team_semi_matches.append((set_number, match_number, match))
        elif match['comp_level'] == 'f':
            final_matches.append((match_number, match))
            if team_in_match:
                team_final_matches.append((match_number, match))
    
    # Sort matches by match number and set number (for elimination matches)
    qual_matches.sort(key=lambda x: x[0])
    quarter_matches.sort(key=lambda x: (x[0], x[1]))
    semi_matches.sort(key=lambda x: (x[0], x[1]))
    final_matches.sort(key=lambda x: x[0])
    
    # Sort team-specific matches
    team_qual_matches.sort(key=lambda x: x[0])
    team_quarter_matches.sort(key=lambda x: (x[0], x[1]))
    team_semi_matches.sort(key=lambda x: (x[0], x[1]))
    team_final_matches.sort(key=lambda x: x[0])
    
    # Return the rendered template with all the match data
    return render_template('matches.html', 
                         qual_matches=qual_matches,
                         quarter_matches=quarter_matches,
                         semi_matches=semi_matches,
                         final_matches=final_matches,
                         team_qual_matches=team_qual_matches,
                         team_quarter_matches=team_quarter_matches,
                         team_semi_matches=team_semi_matches,
                         team_final_matches=team_final_matches,
                         event_key=event_key,
                         opr_data=opr_data,
                         team_info=team_info,
                         team_number=team_number,
                         team_key=team_key)

@app.route('/events', methods=['POST'])
def get_events():
    """
    Handle POST request to fetch and display events for a specific team.
    
    Form parameters:
        team_number: The FRC team number to fetch events for
        
    Returns:
        Rendered events.html template with all events the team is participating in
    """
    team_number = request.form['team_number']
    team_key = f"frc{team_number}"
    year = 2025  # Set competition year (update as needed)
    
    # Get all events data for the specified team in the specified year
    team_events_url = f"https://www.thebluealliance.com/api/v3/team/{team_key}/events/{year}"
    events_response = requests.get(team_events_url, headers=headers)
    events_data = events_response.json()
    
    return render_template('events.html', events=events_data, team_number=team_number)

@app.route('/analysis', methods=['POST'])
def analyze_match():
    """
    Handle POST request to analyze a specific match.
    Fetches match data and computes various team statistics including OPR, DPR, and CCWM
    to provide insights about the match and the participating teams.
    
    Form parameters:
        event_key: The event identifier
        match_key: The match identifier
        
    Returns:
        Rendered analysis.html template with match analysis data, or error message
    """
    event_key = request.form['event_key']
    match_key = request.form['match_key']
    
    # Get detailed data for the specific match
    match_url = f"https://www.thebluealliance.com/api/v3/match/{match_key}"
    match_response = requests.get(match_url, headers=headers)
    match_data = match_response.json()
    
    print("Match Data:", json.dumps(match_data, indent=2))
    
    # Check if we got valid match data
    if not match_data or 'Error' in match_data:
        return "Match data not found", 404
        
    # Extract event key from match key (format: event_key_comp_level_match_number)
    event_key = match_key.split('_')[0]
    
    # Initialize empty data structures for OPR and rankings
    # OPR = Offensive Power Rating, DPR = Defensive Power Rating, CCWM = Calculated Contribution to Winning Margin
    opr_data = {'oprs': {}, 'dprs': {}, 'ccwms': {}}
    rankings_data = {'rankings': []}
    
    # Only try to get OPR and rankings if it's not a future event
    current_year = 2025  # Update dynamically if needed
    event_year = int(event_key[:4])
    
    if event_year <= current_year:
        try:
            # Get OPR data for all teams at the event
            opr_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/oprs"
            opr_response = requests.get(opr_url, headers=headers)
            if opr_response.status_code == 200:
                opr_data = opr_response.json()
            
            # Get rankings data for all teams at the event
            rankings_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/rankings"
            rankings_response = requests.get(rankings_url, headers=headers)
            if rankings_response.status_code == 200:
                rankings_data = rankings_response.json()
        except Exception as e:
            print(f"Error fetching OPR/rankings data: {str(e)}")
    else:
        print(f"Future event ({event_year}), skipping OPR and rankings data")

    try:
        # Extract team keys for red and blue alliances
        red_teams = match_data.get('alliances', {}).get('red', {}).get('team_keys', [])
        blue_teams = match_data.get('alliances', {}).get('blue', {}).get('team_keys', [])
        
        print("Red Teams:", red_teams)
        print("Blue Teams:", blue_teams)
        
        if not red_teams or not blue_teams:
            print("No teams found in match data")
            return "No teams found in match data", 404
        
        # Initialize team statistics dictionary and alliance OPR sums
        team_stats = {}
        red_opr_sum = 0
        blue_opr_sum = 0
        
        # Get team list for the event to provide team names
        event_teams_url = f"https://www.thebluealliance.com/api/v3/event/{event_key}/teams"
        teams_response = requests.get(event_teams_url, headers=headers)
        teams_data = teams_response.json()
        
        # Create team info dictionary for team name lookups
        team_info = {}
        for team in teams_data:
            team_info[team['key']] = {
                'team_number': team['team_number'],
                'nickname': team.get('nickname', 'Unknown Team')
            }
        
        # Process each team to collect their statistics
        for team in red_teams + blue_teams:
            print(f"\nProcessing team: {team}")
            # Handle API inconsistency with 'frc' prefix in team keys
            team_no_prefix = team.replace('frc', '') if team.startswith('frc') else team
            team_with_prefix = f"frc{team_no_prefix}" if not team.startswith('frc') else team
            
            print(f"Looking up OPR data for {team_with_prefix}")
            # Extract OPR metrics for this team
            opr = opr_data.get('oprs', {}).get(team_with_prefix, 0)   # Offensive Power Rating
            dpr = opr_data.get('dprs', {}).get(team_with_prefix, 0)   # Defensive Power Rating
            ccwm = opr_data.get('ccwms', {}).get(team_with_prefix, 0) # Calculated Contribution to Winning Margin
            print(f"Found OPR: {opr}, DPR: {dpr}, CCWM: {ccwm}")
            
            # Store the team's stats in the dictionary
            team_stats[team] = {
                'opr': round(opr, 2),
                'dpr': round(dpr, 2),
                'ccwm': round(ccwm, 2),
                'ranking': None,
                'record': None
            }
            
            # Find team's ranking information from the rankings data
            for rank in rankings_data.get('rankings', []):
                if rank.get('team_key') == team_with_prefix:
                    team_stats[team]['ranking'] = rank.get('rank')
                    # Format the team's win-loss-tie record
                    record = rank.get('record', {})
                    team_stats[team]['record'] = f"{record.get('wins', 0)}-{record.get('losses', 0)}-{record.get('ties', 0)}"
                    print(f"Found ranking: {rank.get('rank')}, record: {team_stats[team]['record']}")
                    break
        
        # Calculate total OPR sum for each alliance
        # This provides a rough prediction of alliance performance
        for team in red_teams:
            red_opr_sum += team_stats[team]['opr']
        for team in blue_teams:
            blue_opr_sum += team_stats[team]['opr']
        
        # Render the analysis template with all the collected data
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

@app.route('/refresh_teams_data', methods=['POST'])
def refresh_teams_data():
    """
    Handle request to refresh the teams data by deleting the cached file
    and redirecting to the index page to force a fresh API call
    
    Returns:
        Redirect to index page
    """
    teamsdata_file = 'teamsdata.json'
    
    # Delete the teams data file if it exists
    if os.path.exists(teamsdata_file):
        try:
            os.remove(teamsdata_file)
        except Exception as e:
            print(f"Error deleting teams data file: {e}")
    
    # Redirect to the index page, which will fetch fresh data
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Run the Flask application in debug mode when executing this file directly
    app.run(debug=True)
