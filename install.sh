#!/bin/bash 

# If the install fails, then print an error and exit.
function install_fail() {
    echo "Installation failed" 
    exit 1 
} 

# This is the help fuction. It helps users withe the options
function Help(){ 
    echo "Usage: install.sh [option]" 
    echo "Options:" 
    echo "  -h: Show this help message and exit" 
    echo "  -d: Install only dependencies" 
    echo "  -p: Install only python dependencies"
    echo "  -b: Install just the bot"
    echo "  -l: Install the bot and the python dependencies"
} 

# Options
while getopts ":hydpbl" option; do
    case $option in
        # -h, prints help message
        h)
            Help exit 0;;
        # -y, assumes yes
        y)
            ASSUME_YES=1;;
        # -d install only dependencies
        d)
            DEPS_ONLY=1;;
        # -p install only python dependencies
        p)
            PYTHON_ONLY=1;;
        b)
            JUST_BOT=1;;
        l)
            BOT_AND_PYTHON=1;;
        # if a bad argument is given, then throw an error
        \?)
            echo "Invalid option: -$OPTARG" >&2 Help exit 1;;
        :)
            echo "Option -$OPTARG requires an argument." >&2 Help exit 1;;
    esac
done 

# Install dependencies for MacOS
function install_macos(){
    # Check if homebrew is installed
    if [ ! command -v brew &> /dev/null ]; then
        echo "Installing Homebrew"
        # if it's is not installed, then install it in a NONINTERACTIVE way
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)" 
        # Check for what arcitecture, so you can place path.
        if [[ "uname -m" == "x86_64" ]]; then
            echo "export PATH=/usr/local/bin:$PATH" >> ~/.bash_profile && source ~/.bash_profile
        fi
    # If not
    else
        # Print that it's already installed
        echo "Homebrew is already installed"
    fi
    # Install the required packages
    echo "Installing required Packages" 
    brew install python@3.10 tcl-tk python-tk
} 

# Function to install for arch (and other forks like manjaro)
function install_arch(){ 
    echo "Installing required packages"
    sudo pacman -S --needed python3 tk git && python3 -m ensurepip || install_fail
} 

# Function to install for debian (and ubuntu)
function install_deb(){ 
    echo "Installing required packages"
    sudo apt install python3 python3-dev python3-tk python3-pip git || install_fail
} 

# Function to install for fedora (and other forks)
function install_fedora(){ 
    echo "Installing required packages" 
    sudo dnf install python3 python3-tkinter python3-pip git python3-devel || install_fail
} 

# Function to install for centos (and other forks based on it)
function install_centos(){
    echo "Installing required packages"
    sudo yum install -y python3 || install_fail
    sudo yum install -y python3-tkinter epel-release python3-pip git || install_fail
} 

function get_the_bot(){ 
    echo "Downloading the bot" 
    git clone https://github.com/elebumm/RedditVideoMakerBot.git 
} 

#install python dependencies
function install_python_dep(){ 
    # tell the user that the script is going to install the python dependencies
    echo "Installing python dependencies" 
    # cd into the directory
    cd RedditVideoMakerBot 
    # install the dependencies
    pip3 install -r requirements.txt 
    # cd out
    cd ..
} 

# Install depndencies
function install_deps(){ 
    # if the platform is mac, install macos
    if [ "$(uname)" == "Darwin" ]; then
        install_macos || install_fail
    # if pacman is found
    elif [ -x "$(command -v pacman)" ]; then
        # install for arch
        install_arch || install_fail
    # if apt-get is found
    elif [ -x "$(command -v apt-get)" ]; then
        # install fro debian
        install_deb || install_fail
    # if dnf is found
    elif [ -x "$(command -v dnf)" ]; then
        # install for fedora
        install_fedora || install_fail
    # if yum is found
    elif [ -x "$(command -v yum)" ]; then
        # install for centos
        install_centos || install_fail
    # else
    else
        # print an error message and exit
        printf "Your OS is not supported\n Please install python3, pip3 and git manually\n After that, run the script again with the -pb option to install python and dependencies\n If you want to add support for your OS, please open a pull request on github\n
https://github.com/elebumm/RedditVideoMakerBot"
        exit 1
    fi
}

# Main function
function install_main(){ 
    # Print that are installing
    echo "Installing..." 
    # if -y (assume yes) continue 
    if [[ ASSUME_YES -eq 1 ]]; then
        echo "Assuming yes"
    # else, ask if they want to continue
    else
        echo "Continue? (y/n)" 
        read answer 
        # if the answer is not yes, then exit
        if [ "$answer" != "y" ]; then
            echo "Aborting" 
            exit 1
        fi
    fi 
    # if the -d (only dependencies) options is selected install just the dependencies
    if [[ DEPS_ONLY -eq 1 ]]; then
        echo "Installing only dependencies" 
        install_deps
    elif [[ PYTHON_ONLY -eq 1 ]]; then
    # if the -p (only python dependencies) options is selected install just the python dependencies
        echo "Installing only python dependencies" 
        install_python_dep 
    # if the -b (only the bot) options is selected install just the bot
    elif [[ JUST_BOT -eq 1 ]]; then
        echo "Installing only the bot"
        get_the_bot
    # if the -l (bot and python) options is selected install just the bot and python dependencies
    elif [[ BOT_AND_PYTHON -eq 1 ]]; then
        echo "Installing only the bot and python dependencies"
        get_the_bot
        install_python_dep
    # else, install everything
    else
        echo "Installing all" 
        install_deps 
        get_the_bot 
        install_python_dep
    fi

    DIR="./RedditVideoMakerBot"
    if [ -d "$DIR" ]; then
        printf "\nThe bot is already installed, want to run it?"
        # if -y (assume yes) continue 
        if [[ ASSUME_YES -eq 1 ]]; then
            echo "Assuming yes"
            # else, ask if they want to continue
        else
            echo "Continue? (y/n)" 
            read answer 
            # if the answer is not yes, then exit
            if [ "$answer" != "y" ]; then
                echo "Aborting" 
                exit 1
            fi
        fi
        cd RedditVideoMakerBot
        python3 main.py
    fi
}

# Run the main function
install_main
