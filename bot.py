# -*- coding: utf-8 -*-
import discord
import configparser
from discord.ext import commands, tasks
from logzero import logfile
from ProfileParser import *

config = configparser.ConfigParser()
config.read('config.ini')
logfile(config['bot']['logfile'])
client = commands.Bot(command_prefix=config['bot']['bot_prefix'])
insta = ProfileParser(profiles_filename=config['instagram']['profiles_filename'])

# insta login
if config['instagram']['LOGIN_MODE'] == '0':
    insta.login(config['instagram']['login'], config['instagram']['password'])
    if config['instagram']['make_session_file_on_login'] == 'True':
        insta.save_session_to_file(config['instagram']['session_filename'])
else:
    insta.load_session_from_file(config['instagram']['login'], filename=config['instagram']['session_filename'])


@tasks.loop(seconds=int(config['bot']['parse_post_delay']))
async def parse_profiles():
    for profile in insta.profiles:

        # функция get_new_downloaded возвращает список файлов либо False если нету изменений
        # в качестве аргументов принимает путь к папке с файлами, функцию и профиль человека
        new_posts = await client.loop.run_in_executor(None, get_new_downloaded,
                                                      f'./{profile}/', insta.download_all_posts_by_profile,
                                                      insta.profiles[profile])
        print(profile, new_posts)
        if new_posts != False:
            guild = client.get_guild(int(config['bot']['server_id']))
            channel = guild.get_channel(int(config['bot']['posts_channel_id']))
            for post in new_posts:
                await channel.send(file=discord.File(f'./{profile}/{post}'))
                logger.info(f'Bot send post success! ./{profile}/{post}')


@tasks.loop(seconds=int(config['bot']['parse_stories_delay']))
async def parse_stories():
    for profile in insta.profiles:

        # функция get_new_downloaded возвращает список файлов либо False если нету изменений
        # в качестве аргументов принимает путь к папке с файлами, функцию и профиль человека
        new_stories = await client.loop.run_in_executor(None, get_new_downloaded,
                                                        f'./{profile} stories/', insta.download_all_stories_by_profile,
                                                        insta.profiles[profile])
        print(profile, new_stories)
        if new_stories != False:
            guild = client.get_guild(int(config['bot']['server_id']))
            channel = guild.get_channel(int(config['bot']['stories_channel_id']))
            for story in new_stories:
                await channel.send(file=discord.File(f'./{profile} stories/{story}'))
                logger.info(f'Bot send stories success! ./{profile} stories/{story}')


@client.command()
async def add_profile(ctx, username):
    try:
        insta.add_profile(username)
        insta.save_profiles_to_file('profiles.pickle')
        await ctx.send(f'{username} successfully added to list')
    except:
        await ctx.send(f'Profile with username:"{username}" not found')


@client.command()
async def remove_profile(ctx, username):
    try:
        insta.remove_profile(username)
        insta.save_profiles_to_file('profiles.pickle')
        await ctx.send(f'{username} successfully deleted')
    except KeyError:
        await ctx.send(f'Profile with username:"{username}" not found in the list')


@client.command()
async def profile_list(ctx):
    for profile in insta.profiles:
        embed = discord.Embed(title="", colour=discord.Colour(0xb903c9))
        embed.set_author(name=profile, icon_url=insta.profiles[profile].profile_pic_url)
        await ctx.send(embed=embed)


@client.event
async def on_ready():
    parse_profiles.start()
    parse_stories.start()
    custom = discord.Game(name=f"Total profiles: {len(insta.profiles)}")
    await client.change_presence(status=discord.Status.online, activity=custom)


client.run(config['bot']['TOKEN'])
