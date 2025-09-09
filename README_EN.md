# Telegram Channel Exporter

A program for automatic monitoring and export of Telegram channels with intelligent media file download system.

## Key Features

- 🔍 **Automatic monitoring** — tracking new messages in Telegram channels
- 📊 **Multiple export formats** — JSON, HTML, Markdown with media file preservation
- 🚫 **Smart content filtering** — exclusion of ads and IT school promotional materials
- 🚀 **Intelligent media download** — adaptive system with Flood Wait protection
- ☁️ **WebDAV synchronization** — automatic synchronization of channel lists and archives
- 📧 **Telegram notifications** — bot sends notifications about new messages
- ⏰ **Scheduler** — daily channel check at 00:00
- 🎯 **User-friendly interface** — paginated channel selection, search, multi-select

## Requirements

- Python 3.8+
- Telegram API credentials (API ID and API Hash)
- Telegram Bot Token (optional, for notifications)

## Installation

1. Clone the repository or download the files
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Getting Telegram API credentials

1. Go to https://my.telegram.org/auth
2. Log in to your Telegram account
3. Go to "API development tools"
4. Create a new application and get:
   - API ID
   - API Hash

### 2. Creating a bot for notifications (optional)

1. Find @BotFather in Telegram
2. Send the `/newbot` command
3. Follow the instructions and get the Bot Token
4. Find your Chat ID (you can use @userinfobot)

## Quick Start

### 1. Run the program
```bash
python telegram_exporter.py
```

### 2. Initial setup
On first run, the program will offer to configure:
- **Telegram API**: API ID, API Hash, phone number
- **Notifications** (optional): Bot Token and Chat ID
- **WebDAV** (optional): for data synchronization

### 3. Channel selection
- Paginated display (10 channels per page)
- Navigation: `p` (previous), `n` (next), `s` (select), `q` (quit)
- Search: `f` + search string
- Multi-select: `1,3-6` (numbers), `sa`/`sd` (entire page)

### 4. Settings management
```bash
python config.py
```

## Project Structure

```
telegram_exporter.py     # Main program file
exporters.py            # Exporters module (JSON, HTML, Markdown)
config_manager.py       # Configuration management
content_filter.py       # Ad and IT school filtering
.channels              # Channel list (JSON)
.config.json           # Program settings
export.log             # Work logs
exports/               # Folder with exported data
└── [Channel]/
    ├── [Channel].json   # JSON export
    ├── [Channel].html   # HTML export  
    ├── [Channel].md     # Markdown export
    └── media/         # Media files
```

## Export Formats

- **JSON** — structured data with complete message information
- **HTML** — beautifully formatted web page with adaptive design
- **Markdown** — text format for GitHub, Notion and other platforms

## Key Features

### Intelligent media download
- Adaptive load management (1-16 threads)
- Automatic Flood Wait protection
- Smart delays with jitter
- Batch file processing

### Content filtering
- Ad exclusion (erid, #ad, sponsored)
- IT school promo filtering (Skillbox, Netology, GeekBrains, etc.)
- Configurable filtering rules

### WebDAV synchronization
- Automatic channel list synchronization
- ZIP archive upload for exports
- Synchronization notifications

## Troubleshooting

### Authorization errors
- Check the correctness of API ID and API Hash
- Make sure the phone number is correct
- Check internet connection

### Channel access errors
- Make sure you are subscribed to the channel
- Check if the channel is not private
- Some channels may restrict API access

### Bot issues
- Check the correctness of Bot Token
- Make sure Chat ID is correct
- Start a conversation with the bot in Telegram

## Additional Information

### Logging
All operations are recorded in the `export.log` file with detailed error and statistics information.

### Notifications
When the bot is configured, the program sends notifications about new messages, successful exports, and WebDAV synchronization.

### Scheduler
Automatic check of all channels every day at 00:00 local time.

## License

This program is provided "as is" for educational and personal purposes. Use in accordance with Telegram Terms of Service.

## Support

If you encounter problems, check the `export.log` file for detailed error information.
