## Installing Emoji Connoisseur

I can think of two reasons you'd want to install this bot:
1. You have to test some changes you made.
2. You want to run a copy of the bot for yourself.
I'm more okay with you doing 1) than 2). If you do 2), please rename the bot and change the icon.

With that out of the way, here's how to install the bot.

-1) `sudo apt install libmagickwand-dev`
0) `pip3 install -r requirements.txt`
1) Make a new bot app at https://discordapp.com/developers/applications/me.
2) Run these sql commands in `sudo -u postgres psql`:
```sql
CREATE USER connoisseur;
\password connoisseur
-- enter and confirm a password
CREATE DATABASE connoisseur OWNER connoisseur;
```
3) Copy `data/config.example.py` to `data/config.py`,
and edit accordingly. Make sure you touch the database and tokens sections.
If you're testing changes to the bot, set `ignore_bots.default` to False, otherwise, to True.
4) Create a brand new Discord user account. This is to hold the guilds that will store the emotes.
Sign in to this account, and get the token for it.
Unfortunately, every time I make a new alt, discord requires me to verify it by phone.
If this happens to you, you must use an actual physical phone number, rather than a VoIP number,
and make sure it hasn't been used to verify any other Discord account.
5) Run `./backend_creator.py $token`.
It'll create the guilds, and once it's finished, give you an invite link.
Sign in to your new Discord backend account, and start filling out CAPTCHAs.
Once you fill out one, the bot will tell you which backend guild to add next.
6) Edit your timezone in postgresql.conf to UTC.
On my system, postgresql.conf is located in `/etc/postgresql/9.6/main`.
7) Run `./bot.py`.
8) *Optional step*: run an instance of the [list website](https://github.com/EmojiConnoisseur/website)
and set up the link in config.py.

If you need any help, DM @lambda#0987 or file a GitHub issue.
