# -*- coding: utf-8 -*-
import configparser
import asyncio
from typing import List, Optional
import traceback

import discord
from discord.ext import commands, tasks
from logzero import logfile, logger

from ProfileParser import ProfileParser, get_new_downloaded

# Configuration loading
config = configparser.ConfigParser()
config.read('config.ini')
logfile(config['bot']['logfile'])

# Bot setup with optimized intents
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix=config['bot']['bot_prefix'], intents=intents)

# Instagram parser initialization
insta = ProfileParser(profiles_filename=config['instagram']['profiles_filename'])

# Initialize Instagram session
async def init_instagram():
    """Initialize Instagram session with proper error handling"""
    try:
        if config['instagram']['LOGIN_MODE'] == '0':
            insta.login(config['instagram']['login'], config['instagram']['password'])
            if config['instagram']['make_session_file_on_login'] == 'True':
                insta.save_session_to_file(config['instagram']['session_filename'])
        else:
            insta.load_session_from_file(config['instagram']['login'], 
                                       filename=config['instagram']['session_filename'])
        logger.info("Instagram session initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Instagram session: {e}")


async def process_content(content_type: str, profile_name: str, downloader_func, channel_id: int):
    """Generic function to process both posts and stories"""
    try:
        profile = insta.profiles[profile_name]
        folder_path = f'./{profile_name}/' if content_type == 'posts' else f'./{profile_name} stories/'
        
        # Use asyncio to run the potentially blocking operation
        new_content = await asyncio.get_event_loop().run_in_executor(
            None, get_new_downloaded, folder_path, downloader_func, profile
        )
        
        if new_content:
            logger.info(f'Found {len(new_content)} new {content_type} for {profile_name}')
            
            guild = client.get_guild(int(config['bot']['server_id']))
            if not guild:
                logger.error(f"Guild {config['bot']['server_id']} not found")
                return
                
            channel = guild.get_channel(channel_id)
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                return
            
            # Send files with rate limiting
            for i, content_file in enumerate(new_content):
                try:
                    file_path = f'{folder_path}{content_file}'
                    await channel.send(file=discord.File(file_path))
                    logger.info(f'Sent {content_type}: {file_path}')
                    
                    # Add small delay between uploads to avoid rate limits
                    if i > 0 and i % 3 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f'Failed to send {content_type} {file_path}: {e}')
        else:
            logger.debug(f'No new {content_type} for {profile_name}')
            
    except Exception as e:
        logger.error(f'Error processing {content_type} for {profile_name}: {e}')
        logger.error(traceback.format_exc())


@tasks.loop(seconds=int(config['bot']['parse_post_delay']))
async def parse_profiles():
    """Parse and send new posts"""
    if not insta.profiles:
        logger.warning("No profiles to parse")
        return
    
    logger.info(f"Starting posts parsing for {len(insta.profiles)} profiles")
    
    # Process profiles concurrently (but limited to avoid overwhelming)
    semaphore = asyncio.Semaphore(3)  # Limit concurrent processing
    
    async def process_profile_posts(profile_name):
        async with semaphore:
            await process_content(
                'posts', 
                profile_name, 
                insta.download_all_posts_by_profile,
                int(config['bot']['posts_channel_id'])
            )
    
    tasks_list = [process_profile_posts(profile) for profile in insta.profiles]
    await asyncio.gather(*tasks_list, return_exceptions=True)


@tasks.loop(seconds=int(config['bot']['parse_stories_delay']))
async def parse_stories():
    """Parse and send new stories"""
    if not insta.profiles:
        logger.warning("No profiles to parse")
        return
    
    logger.info(f"Starting stories parsing for {len(insta.profiles)} profiles")
    
    # Process profiles concurrently (but limited to avoid overwhelming)
    semaphore = asyncio.Semaphore(3)  # Limit concurrent processing
    
    async def process_profile_stories(profile_name):
        async with semaphore:
            await process_content(
                'stories', 
                profile_name, 
                insta.download_all_stories_by_profile,
                int(config['bot']['stories_channel_id'])
            )
    
    tasks_list = [process_profile_stories(profile) for profile in insta.profiles]
    await asyncio.gather(*tasks_list, return_exceptions=True)


@client.command()
async def add_profile(ctx, username: str):
    """Add a profile to the parsing list"""
    try:
        success = await insta.add_profile(username)
        if success:
            await ctx.send(f'✅ {username} successfully added to list')
            logger.info(f'User {ctx.author} added profile: {username}')
        else:
            await ctx.send(f'❌ Failed to add profile: {username}')
    except Exception as e:
        logger.error(f'Error in add_profile command: {e}')
        await ctx.send(f'❌ Error adding profile: {str(e)}')


@client.command()
async def remove_profile(ctx, username: str):
    """Remove a profile from the parsing list"""
    try:
        success = insta.remove_profile(username)
        if success:
            await ctx.send(f'✅ {username} successfully removed')
            logger.info(f'User {ctx.author} removed profile: {username}')
        else:
            await ctx.send(f'❌ Profile {username} not found in the list')
    except Exception as e:
        logger.error(f'Error in remove_profile command: {e}')
        await ctx.send(f'❌ Error removing profile: {str(e)}')


@client.command()
async def profile_list(ctx):
    """Display list of all tracked profiles"""
    try:
        if not insta.profiles:
            await ctx.send("📝 No profiles are currently being tracked")
            return
        
        embeds = []
        for profile_name, profile in insta.profiles.items():
            embed = discord.Embed(
                title=f"📊 Profile: {profile_name}", 
                colour=discord.Colour(0xb903c9)
            )
            
            try:
                embed.set_author(name=profile_name, icon_url=profile.profile_pic_url)
                embed.add_field(name="Followers", value=profile.followers, inline=True)
                embed.add_field(name="Following", value=profile.followees, inline=True)
                embed.add_field(name="Posts", value=profile.mediacount, inline=True)
            except Exception as e:
                logger.warning(f"Error getting profile info for {profile_name}: {e}")
                embed.add_field(name="Status", value="Profile data unavailable", inline=False)
            
            embeds.append(embed)
        
        # Send embeds in batches to avoid rate limits
        for embed in embeds:
            await ctx.send(embed=embed)
            await asyncio.sleep(0.5)  # Small delay between embeds
            
    except Exception as e:
        logger.error(f'Error in profile_list command: {e}')
        await ctx.send(f'❌ Error retrieving profile list: {str(e)}')


@client.command(aliases=['profile_pic', 'p_pic'])
async def get_profile_pic(ctx, username: str):
    """Get profile picture URL"""
    try:
        profile = await insta.get_profile_by_username(username)
        if profile:
            embed = discord.Embed(title=f"Profile Picture: {username}")
            embed.set_image(url=profile.profile_pic_url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f'❌ Profile "{username}" not found')
    except Exception as e:
        logger.error(f'Error in get_profile_pic command: {e}')
        await ctx.send(f'❌ Error retrieving profile picture: {str(e)}')


@client.command()
async def force_parse_posts(ctx):
    """Force parse posts for all profiles"""
    try:
        await ctx.send("🔄 Starting forced posts parsing...")
        
        for profile_name in insta.profiles:
            await process_content(
                'posts', 
                profile_name, 
                insta.download_all_posts_by_profile,
                int(config['bot']['posts_channel_id'])
            )
        
        await ctx.send("✅ Forced posts parsing completed")
        logger.info(f'User {ctx.author} triggered forced posts parsing')
        
    except Exception as e:
        logger.error(f'Error in force_parse_posts command: {e}')
        await ctx.send(f'❌ Error during forced parsing: {str(e)}')


@client.command()
async def force_parse_stories(ctx):
    """Force parse stories for all profiles"""
    try:
        await ctx.send("🔄 Starting forced stories parsing...")
        
        for profile_name in insta.profiles:
            await process_content(
                'stories', 
                profile_name, 
                insta.download_all_stories_by_profile,
                int(config['bot']['stories_channel_id'])
            )
        
        await ctx.send("✅ Forced stories parsing completed")
        logger.info(f'User {ctx.author} triggered forced stories parsing')
        
    except Exception as e:
        logger.error(f'Error in force_parse_stories command: {e}')
        await ctx.send(f'❌ Error during forced parsing: {str(e)}')


@client.command()
async def stats(ctx):
    """Show bot performance statistics"""
    try:
        stats = insta.get_stats()
        
        embed = discord.Embed(title="📊 Bot Statistics", colour=discord.Colour(0x00ff00))
        embed.add_field(name="Tracked Profiles", value=stats['profiles_count'], inline=True)
        embed.add_field(name="Cache Entries", value=stats['cache_entries'], inline=True)
        embed.add_field(name="Recent API Calls", value=stats['rate_limit_calls'], inline=True)
        
        # Add bot uptime and other info
        embed.add_field(name="Latency", value=f"{client.latency * 1000:.1f}ms", inline=True)
        embed.add_field(name="Guilds", value=len(client.guilds), inline=True)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f'Error in stats command: {e}')
        await ctx.send(f'❌ Error retrieving statistics: {str(e)}')


@client.event
async def on_ready():
    """Bot ready event handler"""
    try:
        await init_instagram()
        
        # Start background tasks
        if not parse_profiles.is_running():
            parse_profiles.start()
        if not parse_stories.is_running():
            parse_stories.start()
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(insta.profiles)} profiles"
        )
        await client.change_presence(status=discord.Status.online, activity=activity)
        
        logger.info(f'Bot ready! Logged in as {client.user} (ID: {client.user.id})')
        logger.info(f'Tracking {len(insta.profiles)} profiles')
        
    except Exception as e:
        logger.error(f'Error in on_ready: {e}')
        logger.error(traceback.format_exc())


@client.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    logger.error(f'Command error in {ctx.command}: {error}')
    await ctx.send(f'❌ An error occurred: {str(error)}')


# Start the bot
if __name__ == "__main__":
    try:
        client.run(config['bot']['TOKEN'])
    except Exception as e:
        logger.critical(f'Failed to start bot: {e}')
        logger.critical(traceback.format_exc())
