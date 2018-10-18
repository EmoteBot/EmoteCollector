## Installing Emote Collector

I can think of two reasons you'd want to install this bot:
0. You have to test some changes you made.
1. You want to run a copy of the bot for yourself.
If you do 1), please rename the bot and change the icon.

With that out of the way, here's how to install the bot.

0) `sudo apt install libmagickwand-dev`
1)
```
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -e
```
2) Make a new bot app at https://discordapp.com/developers/applications/me.
3) Run these sql commands in `sudo -u postgres psql`:
```sql
CREATE USER connoisseur;
\password connoisseur
-- enter and confirm a password
CREATE DATABASE connoisseur OWNER connoisseur;
CREATE EXTENSION pg_trgm;
```
4) Copy `emote_collector/data/config.example.py` to `emote_collector/data/config.py`,
and edit accordingly. Make sure you touch the database and tokens sections.
5) Create a brand new Discord user account. This is to hold the guilds that will store the emotes.
Sign in to this account, and get the token for it.
Unfortunately, every time I make a new alt, discord requires me to verify it by phone.
If this happens to you, you must use an actual physical phone number, rather than a VoIP number,
and make sure it hasn't been used to verify any other Discord account.
6) Run `emote_collector/backend_creator.py $token`.
It'll create the guilds, and once it's finished, give you an invite link.
Sign in to your new Discord backend account, and start filling out CAPTCHAs.
Once you fill out one, the bot will tell you which backend guild to add next.
7) Run `./bot.py`.
8) *Optional*: run an instance of the [list website](https://github.com/EmoteCollector/website)
and set up the link in config.py.

If you need any help, DM @lambda#0987 or file a GitHub issue.
