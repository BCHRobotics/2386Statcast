# 2386 FRC Match Analysis

This project is a Flask web application for analyzing FRC (FIRST Robotics Competition) matches using data from The Blue Alliance API. The application allows users to select events, view matches, and analyze match data including Offensive Power Rating (OPR), Defensive Power Rating (DPR), and Calculated Contribution to Winning Margin (CCWM).

## Features

- View events and matches for a specific FRC team.
- Analyze match data including OPR, DPR, and CCWM.
- Display team rankings and records for the selected event.

## Prerequisites

- Python 3.7+
- Virtual environment (optional but recommended)
- The Blue Alliance API key

## Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/your_username/2386Statcast.git
    cd 2386Statcast
    ```

2. Create and activate a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Create a `.env` file in the project root directory and add your The Blue Alliance API key:
    ```plaintext
    TBA_API_KEY=your_tba_api_key
    ```

5. Run the Flask application:
    ```bash
    flask run
    ```

## Deployment

### Using Gunicorn and Systemd

1. Create a `trojangamestats.service` file in `/etc/systemd/system/` with the following content:
    ```plaintext
    [Unit]
    Description=FRC Analysis Flask App
    After=network.target

    [Service]
    User=your_username
    Group=www-data
    WorkingDirectory=/path/to/2386Statcast
    Environment="PATH=/path/to/2386Statcast/venv/bin"
    ExecStart=/path/to/2386Statcast/venv/bin/gunicorn --workers 3 --bind unix:frc-analysis.sock -m 007 wsgi:app

    [Install]
    WantedBy=multi-user.target
    ```

2. Start and enable the service:
    ```bash
    sudo systemctl start trojangamestats
    sudo systemctl enable trojangamestats
    ```

### Using Nginx

1. Create a `trojangamestats.conf` file in `/etc/nginx/sites-available/` with the following content:
    ```properties
    server {
        listen 80;
        server_name your_domain.com;  # Replace with your domain

        location / {
            include proxy_params;
            proxy_pass http://unix:/path/to/2386Statcast/frc-analysis.sock;
        }

        location /static {
            alias /path/to/2386Statcast/static;
        }
    }
    ```

2. Enable the Nginx configuration:
    ```bash
    sudo ln -s /etc/nginx/sites-available/trojangamestats.conf /etc/nginx/sites-enabled
    sudo nginx -t
    sudo systemctl restart nginx
    ```

## Usage

1. Open your web browser and navigate to `http://localhost:5000` (or your domain if deployed).
2. Select an event from the dropdown menu and click "View Matches".
3. Select a match to analyze and click "Analyze Match".

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
