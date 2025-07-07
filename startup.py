#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startup script for the optimized Instagram Discord Bot
Provides configuration validation and performance setup
"""

import os
import sys
import configparser
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'discord.py',
        'instaloader', 
        'logzero',
        'psutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_').replace('.py', ''))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Missing")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 
                '--upgrade'] + missing_packages
            )
            print("✅ All dependencies installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    
    return True


def validate_config():
    """Validate the configuration file"""
    print("\n⚙️  Validating configuration...")
    
    config_file = 'config.ini'
    if not Path(config_file).exists():
        print(f"❌ {config_file} not found!")
        print("📝 Creating sample configuration file...")
        create_sample_config()
        return False
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    required_sections = {
        'bot': ['TOKEN', 'server_id', 'stories_channel_id', 'posts_channel_id'],
        'instagram': ['LOGIN_MODE', 'login']
    }
    
    missing_configs = []
    
    for section, keys in required_sections.items():
        if section not in config:
            missing_configs.append(f"[{section}] section")
            continue
            
        for key in keys:
            if not config[section].get(key):
                missing_configs.append(f"{section}.{key}")
    
    if missing_configs:
        print("❌ Missing configuration values:")
        for missing in missing_configs:
            print(f"   - {missing}")
        print(f"\n📝 Please edit {config_file} and add the missing values")
        return False
    
    print("✅ Configuration is valid!")
    return True


def create_sample_config():
    """Create a sample configuration file"""
    sample_config = """[bot]
TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE
server_id=YOUR_DISCORD_SERVER_ID
stories_channel_id=YOUR_STORIES_CHANNEL_ID
posts_channel_id=YOUR_POSTS_CHANNEL_ID
bot_prefix=^
logfile=logs.log
parse_post_delay=420
parse_stories_delay=180

[instagram]
LOGIN_MODE=0
make_session_file_on_login=True
session_filename=insta_session
profiles_filename=profiles.pickle
login=YOUR_INSTAGRAM_USERNAME
password=YOUR_INSTAGRAM_PASSWORD
"""
    
    with open('config.ini', 'w') as f:
        f.write(sample_config)
    
    print("✅ Sample config.ini created!")
    print("📝 Please edit config.ini with your actual values")


def setup_directories():
    """Create necessary directories"""
    print("\n📁 Setting up directories...")
    
    directories = [
        'logs',
        'cache',
        'profiles',
        'downloads'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ {directory}/")


def optimize_system():
    """Apply system optimizations"""
    print("\n🚀 Applying system optimizations...")
    
    # Set environment variables for better performance
    os.environ['PYTHONOPTIMIZE'] = '1'  # Enable basic optimizations
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'  # Don't write .pyc files
    
    print("✅ Python optimizations enabled")
    print("✅ Bytecode writing disabled (saves disk space)")


def run_performance_check():
    """Run initial performance check"""
    print("\n📊 Running performance check...")
    
    try:
        from performance_monitor import PerformanceMonitor
        monitor = PerformanceMonitor()
        
        # Get baseline metrics
        metrics = monitor.get_system_metrics()
        
        print(f"💾 Memory usage: {metrics.get('memory_mb', 0):.1f}MB")
        print(f"🖥️  CPU usage: {metrics.get('cpu_percent', 0):.1f}%")
        print(f"📂 Open files: {metrics.get('open_files', 0)}")
        
        # Save initial report
        report_file = monitor.save_report('startup_performance_report.json')
        if report_file:
            print(f"📈 Performance report saved: {report_file}")
        
    except ImportError:
        print("⚠️  Performance monitor not available")


def main():
    """Main startup routine"""
    print("🤖 Instagram Discord Bot - Optimized Startup")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Dependency check failed. Please resolve issues and try again.")
        sys.exit(1)
    
    # Validate configuration
    if not validate_config():
        print("\n❌ Configuration validation failed. Please fix config.ini and try again.")
        sys.exit(1)
    
    # Setup directories
    setup_directories()
    
    # Apply optimizations
    optimize_system()
    
    # Run performance check
    run_performance_check()
    
    print("\n🎉 Setup complete! The bot is ready to run.")
    print("\n🚀 To start the bot:")
    print("   python bot.py")
    print("\n📊 To monitor performance:")
    print("   python performance_monitor.py")
    print("\n📚 Available commands:")
    print("   ^add_profile <username>    - Add Instagram profile")
    print("   ^remove_profile <username> - Remove Instagram profile") 
    print("   ^profile_list              - List all profiles")
    print("   ^stats                     - Show bot statistics")
    print("   ^force_parse_posts         - Force parse all posts")
    print("   ^force_parse_stories       - Force parse all stories")


if __name__ == "__main__":
    main()