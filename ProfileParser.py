# -*- coding: utf-8 -*-
import os
import pickle
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set
import time

from instaloader import Instaloader, InstaloaderContext,\
                        InstaloaderException, Profile
from logzero import logger


class FileCache:
    """Efficient file cache to avoid repeated directory walks"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, float]] = {}  # path -> {filename: mtime}
        self._last_scan: Dict[str, float] = {}  # path -> last_scan_time
        self._cache_ttl = 30  # Cache TTL in seconds
    
    def get_files(self, path: str) -> Set[str]:
        """Get files with caching, only rescans if cache is stale"""
        current_time = time.time()
        
        # Check if cache is valid
        if (path in self._last_scan and 
            current_time - self._last_scan[path] < self._cache_ttl):
            return set(self._cache[path].keys())
        
        # Rescan directory
        self._cache[path] = {}
        if os.path.exists(path):
            for file_path in Path(path).rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in {'.jpg', '.mp4'}:
                    self._cache[path][file_path.name] = file_path.stat().st_mtime
        
        self._last_scan[path] = current_time
        return set(self._cache[path].keys())
    
    def invalidate(self, path: str):
        """Invalidate cache for a specific path"""
        if path in self._cache:
            del self._cache[path]
        if path in self._last_scan:
            del self._last_scan[path]


# Global file cache instance
_file_cache = FileCache()


def get_all_downloaded(path: str) -> List[str]:
    """
    Returns list of media files (optimized with caching)
    """
    return list(_file_cache.get_files(path))


def get_new_downloaded(path: str, downloader, profile) -> Optional[List[str]]:
    """
    Returns list of new downloaded files or None if no changes
    """
    before = set(_file_cache.get_files(path))
    
    try:
        downloader(profile)
        # Invalidate cache after download to force refresh
        _file_cache.invalidate(path)
        after = set(_file_cache.get_files(path))
        
        new_files = after - before
        return list(new_files) if new_files else None
        
    except Exception as e:
        logger.error(f"Error downloading content for {profile.username}: {e}")
        return None


class RateLimiter:
    """Simple rate limiter to prevent API abuse"""
    
    def __init__(self, calls_per_minute: int = 30):
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        # Remove calls older than 1 minute
        self.calls = [call_time for call_time in self.calls if now - call_time < 60]
        
        if len(self.calls) >= self.calls_per_minute:
            wait_time = 60 - (now - self.calls[0])
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
        
        self.calls.append(now)


class ProfileParser(Instaloader, InstaloaderContext, InstaloaderException):
    
    def __init__(self, profiles_filename: str):
        Instaloader.__init__(self,
                             download_geotags=False,
                             download_comments=False,
                             save_metadata=False,
                             compress_json=False)  # Disable JSON compression for speed
        
        self.profiles: Dict[str, Profile] = {}
        self.profiles_filename = profiles_filename
        self.rate_limiter = RateLimiter()
        
        try:
            self.load_profiles_from_file(profiles_filename)
            logger.info(f"Loaded {len(self.profiles)} profiles from {profiles_filename}")
        except EOFError:
            logger.error(f'EOFError: {profiles_filename} corrupted, creating new file')
            self.profiles = {}
            self.save_profiles_to_file(profiles_filename)
        except FileNotFoundError:
            logger.info(f'{profiles_filename} not found, will create on first save')
            self.profiles = {}

    def load_profiles_from_file(self, filename: str):
        """Load profiles with better error handling"""
        try:
            with open(filename, 'rb') as file:
                data = pickle.load(file)
                if isinstance(data, dict):
                    self.profiles = data
                else:
                    logger.error(f"Invalid data format in {filename}")
                    self.profiles = {}
        except (FileNotFoundError, EOFError, pickle.PickleError) as e:
            logger.error(f'Error loading profiles from {filename}: {e}')
            self.profiles = {}

    def save_profiles_to_file(self, filename: str):
        """Save profiles with atomic write operation"""
        temp_filename = f"{filename}.tmp"
        try:
            with open(temp_filename, 'wb') as file:
                pickle.dump(self.profiles, file, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Atomic move
            os.replace(temp_filename, filename)
            logger.info(f"Saved {len(self.profiles)} profiles to {filename}")
            
        except Exception as e:
            logger.error(f'Error saving profiles to {filename}: {e}')
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    async def download_all_stories_by_profile(self, profile: Profile):
        """Download stories with rate limiting"""
        await self.rate_limiter.wait_if_needed()
        
        try:
            story_count = 0
            for story in self.get_stories([profile.userid]):
                for item in story.get_items():
                    self.download_storyitem(item, f"{profile.username} stories")
                    story_count += 1
            
            logger.info(f"Downloaded {story_count} stories for {profile.username}")
            
        except Exception as e:
            logger.error(f"Error downloading stories for {profile.username}: {e}")

    async def download_all_posts_by_profile(self, profile: Profile):
        """Download posts with rate limiting"""
        await self.rate_limiter.wait_if_needed()
        
        try:
            post_count = 0
            for post in profile.get_posts():
                self.download_post(post, profile.username)
                post_count += 1
                
                # Add small delay between posts to be gentle on Instagram
                if post_count % 5 == 0:
                    await asyncio.sleep(1)
            
            logger.info(f"Downloaded {post_count} posts for {profile.username}")
            
        except Exception as e:
            logger.error(f"Error downloading posts for {profile.username}: {e}")

    async def add_profile(self, username: str) -> bool:
        """Add profile with async support and better error handling"""
        try:
            await self.rate_limiter.wait_if_needed()
            
            profile = Profile.from_username(self.context, username)
            self.profiles[username] = profile
            self.save_profiles_to_file(self.profiles_filename)
            
            logger.info(f"Added profile: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding profile {username}: {e}")
            return False

    def remove_profile(self, username: str) -> bool:
        """Remove profile with better error handling"""
        if username in self.profiles:
            del self.profiles[username]
            self.save_profiles_to_file(self.profiles_filename)
            logger.info(f"Removed profile: {username}")
            return True
        else:
            logger.warning(f"Profile {username} not found in list")
            return False

    async def get_profile_by_username(self, username: str) -> Optional[Profile]:
        """Get profile with caching and rate limiting"""
        # Check cache first
        if username in self.profiles:
            return self.profiles[username]
        
        # Fetch from Instagram
        try:
            await self.rate_limiter.wait_if_needed()
            profile = Profile.from_username(self.context, username)
            return profile
        except Exception as e:
            logger.error(f"Error fetching profile {username}: {e}")
            return None

    def get_stats(self) -> Dict[str, int]:
        """Get performance statistics"""
        return {
            'profiles_count': len(self.profiles),
            'cache_entries': len(_file_cache._cache),
            'rate_limit_calls': len(self.rate_limiter.calls)
        }


class Gg:

    @property
    def chto(self) -> str:
        return 'Ne budet'
