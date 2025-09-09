# 🔧 Technical Details of Download System

## Intelligent Download Architecture

### Main Components

#### MediaDownloader
Main class for managing media file downloads with adaptive algorithms.

**Key Parameters:**
- `max_workers` (1-32): Maximum number of threads
- `current_workers` (1-16): Current number of active threads
- `adaptive_delay` (0.1-5.0s): Current delay between requests
- `consecutive_successes`: Counter of consecutive successful downloads

#### Adaptive Algorithms

```python
# On flood wait
if flood_wait_seconds > 10:
    multiplier = 2.0  # Aggressive delay increase
elif flood_wait_seconds > 5:
    multiplier = 1.8
else:
    multiplier = 1.5

adaptive_delay = min(max_delay, adaptive_delay * multiplier)
current_workers = max(1, current_workers - 1)
```

```python
# On successful downloads
if time_since_flood > 120 and consecutive_successes >= 15:
    adaptive_delay = max(min_delay, adaptive_delay * 0.95)
    if consecutive_successes % 20 == 0:
        current_workers = min(max_workers, current_workers + 1)
```

### Error Handling

#### FloodWaitError
- **Automatic wait time extraction** from exception
- **Adaptive delay increase** depending on blocking duration
- **Thread count reduction** to reduce API load

#### Network Errors
```python
if "connection" in error_msg or "network" in error_msg:
    wait_time = random.uniform(3, 8)  # Increased delay
    await asyncio.sleep(wait_time)
```

#### Access Errors
```python
if "permission" in error_msg or "access" in error_msg:
    return False  # Don't retry download
```

### Performance Optimizations

#### File Size Caching
```python
# Cache valid for 5 minutes
cache_key = f"media_size_{channel.title}"
if cache_key in cache and time.time() - cache[cache_key][0] < 300:
    return cache[cache_key][1]
```

#### Batch Processing
```python
batch_size = max(5, current_workers * 2)
batches = [queue[i:i + batch_size] for i in range(0, len(queue), batch_size)]
```

#### Jitter to Prevent Synchronization
```python
def _get_smart_delay(self) -> float:
    jitter = random.uniform(0.8, 1.2)
    return self.adaptive_delay * jitter
```

## Statistics and Monitoring

### Key Metrics

1. **success_rate**: Percentage of successful downloads
2. **flood_wait_rate**: Percentage of requests with flood wait
3. **downloads_per_minute**: Download speed
4. **time_since_last_flood**: Stable operation time

### Example Statistics
```python
{
    'total_attempts': 150,
    'successful_downloads': 142,
    'flood_waits': 3,
    'success_rate': 94.67,
    'flood_wait_rate': 2.0,
    'downloads_per_minute': 12.5,
    'current_workers': 4,
    'adaptive_delay': 0.8,
    'consecutive_successes': 25
}
```

## Configuration

### New Parameters in Config
```python
@dataclass
class StorageConfig:
    media_download_threads: int = 4
    adaptive_download: bool = True
    min_download_delay: float = 0.1
    max_download_delay: float = 3.0
```

### Settings Application
```python
media_downloader = MediaDownloader(channel_dir, max_workers=media_threads)
if adaptive_download:
    media_downloader.min_delay = min_delay
    media_downloader.max_delay = max_delay
```

## Solved Problems

### 1. Zero-Size Files
**Problem**: ThreadPoolExecutor created a new event loop in each thread
```python
# Was (incorrect)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(client.download_media(message, file_path))
```

**Solution**: Using asyncio.gather in one event loop
```python
# Now (correct)
download_results = await asyncio.gather(*download_tasks, return_exceptions=True)
```

### 2. Frequent Flood Wait
**Problem**: Too aggressive downloading without adaptation

**Solution**: Intelligent adaptation system
- Conservative start (2 threads, 0.5s delay)
- Automatic load reduction on blocking
- Gradual acceleration during stable operation

### 3. UI Performance
**Problem**: Recalculating file sizes on every update

**Solution**: Caching with TTL and size limit
```python
# Cache with timestamps
self._media_size_cache[cache_key] = (time.time(), size_mb)

# Auto-cleanup on limit exceed
if len(self._media_size_cache) > 100:
    oldest_keys = sorted(cache.keys(), key=lambda k: cache[k][0])[:50]
    for key in oldest_keys:
        del cache[key]
```

## Configuration Recommendations

### For Fast Connections
```python
media_download_threads = 8
min_download_delay = 0.1
max_download_delay = 2.0
```

### For Slow Connections
```python
media_download_threads = 2
min_download_delay = 0.5
max_download_delay = 5.0
```

### For Unstable Connections
```python
media_download_threads = 4
min_download_delay = 1.0
max_download_delay = 10.0
adaptive_download = True  # Required
```

## Debugging

### Enable Detailed Logging
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Monitor Statistics
```python
stats = media_downloader.get_download_stats()
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Flood waits: {stats['flood_waits']}")
print(f"Current settings: {stats['current_workers']} workers, {stats['adaptive_delay']:.1f}s delay")
```

### Log Analysis
Look for in logs:
- `🚫 Flood wait` - API blocking events
- `⚡ Gradual acceleration` - parameter adaptation
- `✓ File ... successfully downloaded` - successful downloads with size and speed
