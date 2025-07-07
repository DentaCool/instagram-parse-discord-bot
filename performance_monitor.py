#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance monitoring script for Instagram Discord Bot
"""

import time
import psutil
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta

class PerformanceMonitor:
    """Monitor bot performance and resource usage"""
    
    def __init__(self):
        self.metrics = {
            'cpu_usage': [],
            'memory_usage': [],
            'disk_usage': [],
            'network_io': [],
            'download_times': [],
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0,
            'errors': 0
        }
        self.start_time = time.time()
        self.process = psutil.Process()
    
    def log_metric(self, metric_type: str, value: float):
        """Log a performance metric"""
        timestamp = time.time()
        
        if metric_type in self.metrics and isinstance(self.metrics[metric_type], list):
            self.metrics[metric_type].append({
                'timestamp': timestamp,
                'value': value
            })
            
            # Keep only last 1000 entries to prevent memory bloat
            if len(self.metrics[metric_type]) > 1000:
                self.metrics[metric_type] = self.metrics[metric_type][-1000:]
    
    def increment_counter(self, counter_name: str):
        """Increment a counter metric"""
        if counter_name in self.metrics:
            self.metrics[counter_name] += 1
    
    def get_system_metrics(self) -> Dict:
        """Get current system performance metrics"""
        try:
            return {
                'cpu_percent': self.process.cpu_percent(),
                'memory_mb': self.process.memory_info().rss / 1024 / 1024,
                'memory_percent': self.process.memory_percent(),
                'open_files': len(self.process.open_files()),
                'connections': len(self.process.connections()),
                'uptime_seconds': time.time() - self.start_time
            }
        except Exception as e:
            print(f"Error getting system metrics: {e}")
            return {}
    
    def get_cache_performance(self) -> Dict:
        """Calculate cache performance metrics"""
        total_requests = self.metrics['cache_hits'] + self.metrics['cache_misses']
        if total_requests == 0:
            return {'hit_rate': 0, 'total_requests': 0}
        
        hit_rate = (self.metrics['cache_hits'] / total_requests) * 100
        return {
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests,
            'hits': self.metrics['cache_hits'],
            'misses': self.metrics['cache_misses']
        }
    
    def get_download_performance(self) -> Dict:
        """Get download performance statistics"""
        if not self.metrics['download_times']:
            return {'avg_time': 0, 'total_downloads': 0}
        
        times = [item['value'] for item in self.metrics['download_times']]
        return {
            'avg_time': round(sum(times) / len(times), 2),
            'min_time': round(min(times), 2),
            'max_time': round(max(times), 2),
            'total_downloads': len(times)
        }
    
    def get_summary_report(self) -> Dict:
        """Generate comprehensive performance report"""
        system_metrics = self.get_system_metrics()
        cache_metrics = self.get_cache_performance()
        download_metrics = self.get_download_performance()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_hours': round(system_metrics.get('uptime_seconds', 0) / 3600, 2),
            'system': system_metrics,
            'cache': cache_metrics,
            'downloads': download_metrics,
            'api_calls': self.metrics['api_calls'],
            'errors': self.metrics['errors']
        }
    
    def save_report(self, filename: Optional[str] = None):
        """Save performance report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        report = self.get_summary_report()
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Performance report saved to {filename}")
            return filename
        except Exception as e:
            print(f"Error saving report: {e}")
            return None
    
    async def monitor_continuously(self, interval: int = 60):
        """Continuously monitor performance"""
        print(f"Starting continuous monitoring (interval: {interval}s)")
        
        while True:
            try:
                metrics = self.get_system_metrics()
                
                self.log_metric('cpu_usage', metrics.get('cpu_percent', 0))
                self.log_metric('memory_usage', metrics.get('memory_mb', 0))
                
                # Log summary every 10 minutes
                if int(time.time()) % 600 == 0:
                    report = self.get_summary_report()
                    print(f"Performance Summary: CPU: {report['system']['cpu_percent']:.1f}%, "
                          f"Memory: {report['system']['memory_mb']:.1f}MB, "
                          f"Cache Hit Rate: {report['cache']['hit_rate']:.1f}%")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"Error in continuous monitoring: {e}")
                await asyncio.sleep(interval)


def analyze_logs(log_file: str = "logs.log") -> Dict:
    """Analyze bot logs for performance insights"""
    if not Path(log_file).exists():
        return {"error": "Log file not found"}
    
    analysis: Dict[str, Any] = {
        'total_lines': 0,
        'errors': 0,
        'warnings': 0,
        'downloads': 0,
        'api_calls': 0,
        'avg_response_time': 0
    }
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                analysis['total_lines'] += 1
                
                if 'ERROR' in line:
                    analysis['errors'] += 1
                elif 'WARNING' in line:
                    analysis['warnings'] += 1
                elif 'Downloaded' in line:
                    analysis['downloads'] += 1
                elif 'API call' in line:
                    analysis['api_calls'] += 1
                    
    except Exception as e:
        analysis['error'] = str(e)
    
    return analysis


def cleanup_old_files(directory: str = ".", max_age_days: int = 7):
    """Clean up old files to prevent disk space issues"""
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    cleaned_files = 0
    freed_space = 0
    
    try:
        for file_path in Path(directory).rglob("*"):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                # Skip important files
                if file_path.name in ['bot.py', 'ProfileParser.py', 'config.ini', 'requirements.txt']:
                    continue
                
                if file_time < cutoff_date and file_path.suffix in ['.log', '.tmp', '.cache']:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    cleaned_files += 1
                    freed_space += file_size
                    
        print(f"Cleanup completed: {cleaned_files} files removed, {freed_space / 1024 / 1024:.2f}MB freed")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    monitor = PerformanceMonitor()
    
    # Generate and save current report
    monitor.save_report()
    
    # Analyze logs
    log_analysis = analyze_logs()
    print("Log Analysis:", json.dumps(log_analysis, indent=2))
    
    # Cleanup old files
    cleanup_old_files()
    
    # Start continuous monitoring (comment out if running as one-time script)
    # asyncio.run(monitor.monitor_continuously())