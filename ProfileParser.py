# -*- coding: utf-8 -*-
from instaloader import Instaloader, InstaloaderContext,InstaloaderException, Profile
import pickle
from logzero import logger
import os


def get_all_downloaded(path):
    """
    Returns list of files
    """
    downloaded = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        downloaded.extend(filter(lambda x: x[::-1][:3] in ['gpj', '4pm'], filenames))
    return downloaded


def get_new_downloaded(path, downloader, profile):
    """
    Returns list of new downloaded files or False
    """
    before = get_all_downloaded(path)
    downloader(profile)
    after = get_all_downloaded(path)
    if before == after:
        return False
    else:
        for i in before:
            if i in after:
                after.pop(after.index(i))
        return after


class ProfileParser(Instaloader, InstaloaderContext, InstaloaderException):
    profiles = {}

    def __init__(self, profiles_filename):
        Instaloader.__init__(self, download_geotags=False, download_comments=False, save_metadata=False)
        try:
            self.load_profiles_from_file(profiles_filename)
        except EOFError:
            logger.error(f'EOFError: {profiles_filename} not loaded, renew file plz')
        except FileNotFoundError:
            logger.error(f'FileNotFoundError: {profiles_filename} not found')

    def load_profiles_from_file(self, filename):
        try:
            with open(filename, 'rb') as file:
                self.profiles = pickle.load(file)
        except FileNotFoundError:
            logger.error(f'FileNotFoundError: {filename} not found')

    def save_profiles_to_file(self, filename):
        try:
            with open(filename, 'wb') as file:
                pickle.dump(self.profiles, file)
        except FileNotFoundError:
            logger.error(f'FileNotFoundError: {filename} not found')

    def download_all_stories_by_profile(self, profile: Profile):
        for story in self.get_stories([profile.userid]):
            for item in story.get_items():
                self.download_storyitem(item, profile.username + ' stories')

    def download_all_posts_by_profile(self, profile: Profile):
        for post in profile.get_posts():
            self.download_post(post, profile.username)

    def add_profile(self, username):
        self.profiles[username] = Profile.from_username(self.context, username)

    def remove_profile(self, username):
        if username in self.profiles:
            self.profiles.pop(username)
        else:
            logger.info(f'{username} not in list')
            raise KeyError
