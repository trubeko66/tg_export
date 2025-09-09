# Installation and Setup

## Quick Installation

1. **Install Python 3.8+**
   ```bash
   # Windows
   # Download from https://python.org
   
   # Linux/macOS
   sudo apt install python3 python3-pip  # Ubuntu/Debian
   brew install python3                  # macOS
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get Telegram API credentials**
   - Go to https://my.telegram.org/auth
   - Log in to your Telegram account
   - Create an application in "API development tools"
   - Save API ID and API Hash

4. **Run the program**
   ```bash
   python telegram_exporter.py
   ```

## Initial Setup

On first run, the program will offer to configure:

- **Telegram API**: API ID, API Hash, phone number
- **Notifications** (optional): Bot Token and Chat ID
- **WebDAV** (optional): for data synchronization

## Creating a Bot for Notifications

1. Find @BotFather in Telegram
2. Send `/newbot`
3. Follow the instructions
4. Save the Bot Token
5. Find Chat ID (use @userinfobot)

## Settings Management

```bash
python config.py
```

## File Structure

- `.config.json` — program settings
- `.channels` — channel list
- `export.log` — work logs
- `exports/` — folder with exported data
