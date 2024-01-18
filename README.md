# RPi DHT-22 server

This project contains necessarry files and scripts to read temperature and 
humidity data from a DHT22 sensor, wired to a Raspberry Pi 4. It stores the 
results every 2 seconds in a local Sqlite database, and renders them on a bare 
simple frontend using ChartJS powered by Flask and web-sockets.

## Requirements

Get and build Python 3.12 from source

    sudo apt update
    sudo apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
        libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev
    wget https://python.org/ftp/python/3.12.1/Python-3.12.1.tgz
    tar -xf Python-3.12.1.tgz 
    cd Python-3.12.1
    ./configure --enable-optimizations
    sudo make altinstall

Install screen to run the commands in the background and keep them persistant

    sudo apt install screen

Create a Python virtual environment and install the Python dependencies 
(this is a one-off command)

    make venv deps
    
## Usage

Run the dht sensor polling service
    
    make polling

From another terminal window, run the flask server
    
    make server

Run the commands in screen in order to keep them persistant over the SSH
session
   
    screen -d -m make polling
    screen -d -m make server

You can then list the running screen sessions with
   
    screen -ls

More screen commands see

    screen --help
