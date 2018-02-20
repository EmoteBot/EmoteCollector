## Installing Emoji Connoisseur

I can think of two reasons you'd want to install this bot:
1. You have to test some changes you made.
2. You want to run a copy of the bot for yourself.
I'm more okay with you doing 1) than 2). If you do 2), please rename the bot and change the icon.

With that out of the way, here's how to install the bot.

0) `pip3 install -r requirements.txt`
1) Make a new bot app at https://discordapp.com/developers/applications/me.
2) Run `echo CREATE DATABASE connoisseur | sudo -u postgres psql`, then run these sql commands in
`sudo -u postgres psql connoisseur`:
```sql
CREATE ROLE connoisseur WITH LOGIN PASSWORD 'hunter2';
CREATE SCHEMA connoisseur; -- skip this if you want to use an existing schema
GRANT ALL PRIVILEGES ON SCHEMA connoisseur TO connoisseur;
GRANT ALL PRIVILEGES ON DATABASE connoisseur TO connoisseur;
```
3) Copy `data/config.example.json` to `data/config.json`,
and edit `client_id`, `tokens.discord`, and the database section.
4) Create a brand new Discord user account. This is to hold the guilds that will store the emotes.
Sign in to this account, and get the token for it.
Unfortunately, every time I make a new alt, discord requires me to verify it by phone.
If this happens to you, you must use an actual physical phone number, rather than a VoIP number,
and make sure it hasn't been used to verify any other Discord account.
5) Run `./backend_creator.py $token`.
It'll create the guilds, and once it's finished, open a Firefox window.
If you want it to create less than 100 guilds, edit `on_ready`. I recommend 5 for testing.
Sign in to your new Discord backend account, and start filling out CAPTCHAs.
6) Run `./bot.py`.

If you need any help, DM @null byte#8191 or file a GitHub issue.
