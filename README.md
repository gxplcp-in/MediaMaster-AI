# MediaMaster AI (@MediaMaster_AIBot) — Setup & Deployment

Video-based social media growth bot: user video bhejta hai -> Gemini 2.5 Flash analyse karta hai ->
Hinglish me viral report (Instagram, Facebook, YouTube Shorts, Snapchat/Moj/LinkedIn, best posting time).

## Folder structure
```
bot.py              entry point (polling / webhook)
config.py           settings + environment variables
database.py         Supabase (PostgreSQL) layer
schema.sql          Supabase me ek baar run karne wala SQL (tables + atomic functions)
gemini_service.py   Gemini video analysis (upload -> report -> remote file delete)
handlers.py         commands, buttons, force-subscribe gate, video flow
messages.py         saare Hinglish texts
keyboards.py        inline buttons
health.py           health-check server
Procfile / Dockerfile / requirements.txt / .env.example / .gitignore
```

## User flow
1. `/start` -> 3 tasks: (1) Telegram channel join, (2) YouTube subscribe, (3) Sponsor link dekho
2. Teeno complete + Verify -> **3 free credits** (ek hi baar)
3. Video bhejo -> 1 credit kata -> report. Fail ho to **1 credit auto-refund**
4. Credits 0 -> video block; `/bonus` (sponsor link, roz max 3) ya `/refer` (+2 har dost) se credits

## Step 1 — Accounts / keys
| Cheez | Kahan se |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram me @BotFather -> `/mybots` -> tumhara bot -> API Token |
| `GEMINI_API_KEY` | aistudio.google.com -> Get API key |
| `SUPABASE_URL`, `SUPABASE_KEY` | supabase.com -> New project -> Project Settings -> API (URL + **service_role / secret** key) |
| `ADMIN_IDS` | @userinfobot se apna numeric user ID |

## Step 2 — Supabase database
1. Supabase Dashboard -> **SQL Editor** -> New query
2. `schema.sql` ka poora content paste karo -> **Run**
3. Table Editor me `users` table dikhni chahiye.

`SUPABASE_KEY` me **service_role (secret)** key daalo, anon key nahi. Ye key sirf server par rakho, GitHub par kabhi nahi.

## Step 3 — Bot ko channel ka Admin banao (zaroori)
@MediaAIOfficial -> Manage channel -> Administrators -> Add Admin -> `@MediaMaster_AIBot`.
Iske bina `getChatMember` kaam nahi karega aur koi user verify nahi hoga. (Agar check fail hota hai to `ADMIN_IDS` waale admin ko DM alert aata hai.)

## Step 4 — Local test (optional)
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # values bharo, phir:
set -a && source .env && set +a
python bot.py
```
Python 3.10+ chahiye.

## Step 5 — GitHub
```bash
cd mediamaster_v2
git init
git add .
git commit -m "MediaMaster AI v2: Supabase + 3 tasks + Hinglish"
git branch -M main
git remote add origin https://github.com/<USERNAME>/mediamaster-bot.git
git push -u origin main
```
GitHub par repo pehle **Private** banao. `.env` `.gitignore` me hai, commit nahi hoga.
Aage ke updates: `git add . && git commit -m "update" && git push` -> Koyeb khud redeploy karega.

## Step 6 — Koyeb deploy
1. koyeb.com -> **Create Service** -> **GitHub** -> repo select karo
2. Builder: **Dockerfile** (sabse reliable) ya Buildpack (Procfile `web: python bot.py` use hota hai)
3. Instance: **Free**
4. **Environment variables** -> add karo: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (Secret type), `ADMIN_IDS`
5. Exposed port: **8000** (HTTP), path `/`; health check: HTTP `/`
6. Deploy dabao. Logs me `Polling mode` ya `Webhook mode` dikhna chahiye.

### Koyeb free instance ka sleep (IMPORTANT)
Koyeb docs ke mutabik Free Instance **1 ghante tak koi incoming traffic na ho to sleep** me chala jata hai (ise band nahi kar sakte).
Polling bot Telegram ko *outbound* call karta hai, isse sleep nahi rukta. Do tareeke:

**Option A — Polling + UptimeRobot (simple):** uptimerobot.com par free HTTP monitor banao, URL = tumhara Koyeb public URL, interval 5 min.

**Option B — Webhook mode (recommended):** Deploy hone ke baad Koyeb ka public URL copy karo, phir env vars me add karo:
```
WEBHOOK_URL=https://<app>-<org>.koyeb.app
WEBHOOK_SECRET=<koi bhi random 16+ characters, sirf A-Z a-z 0-9 _ ->
```
Redeploy karo. Ab Telegram har message par instance ko jaga dega (1-5 second cold start). Is mode me health check **TCP** rakho (HTTP `/` 404 dega).

## Render par deploy (alternative)
New -> Web Service -> repo -> Build: `pip install -r requirements.txt` -> Start: `python bot.py` -> same env vars.
Free web service 15 min idle par sleep hoti hai -> Option A (UptimeRobot) ya Option B (webhook) use karo.

## Environment variables
| Variable | Required | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Haan | - |
| `GEMINI_API_KEY` | Haan | - |
| `SUPABASE_URL` | Haan | - |
| `SUPABASE_KEY` | Haan | - |
| `ADMIN_IDS` | Recommended | khali |
| `CHANNEL_USERNAME` | Nahi | `@MediaAIOfficial` |
| `YOUTUBE_URL` / `SPONSOR_URL` | Nahi | tumhare diye links |
| `GEMINI_MODEL` | Nahi | `gemini-2.5-flash` |
| `START_CREDITS` / `REFERRAL_BONUS` | Nahi | `3` / `2` |
| `BONUS_CREDITS` / `BONUS_DAILY_CAP` | Nahi | `1` / `3` |
| `YT_MIN_SECONDS` / `SPONSOR_MIN_SECONDS` / `BONUS_MIN_SECONDS` | Nahi | `10` / `15` / `15` |
| `MAX_CONCURRENT_ANALYSES` | Nahi | `2` |
| `WEBHOOK_URL` / `WEBHOOK_SECRET` | Nahi | khali (polling mode) |
| `PORT` | Nahi | `8000` |

## Admin commands
- `/addcredits <user_id> <amount>` — credits jodo (negative se ghata bhi sakte ho)
- `/stats` — total users, verified users, total video requests

## Zaroori sachchai (limits)
- **YouTube aur Sponsor tasks verify nahi ho sakte.** Telegram/YouTube koi API nahi deta jo bata de ki user ne subscribe kiya ya link dekha. Bot sirf friction lagata hai: user ko pehle link-button dabana padta hai, aur "Done" kam se kam 10-15 second baad chalta hai. Koi chahe to bina kiye "Done" daba sakta hai. Sirf **Telegram join** asli verification hai (`getChatMember`, har video par dobara check).
- **Adsterra policy check karo.** Users ko credits dekar ad/smart link par bhejna "incentivized/motivated traffic" ho sakta hai, jo ad networks aksar allow nahi karte. Account ban hone ka risk hai — apne account ki rules padh lo.
- Telegram Bot API **20 MB** se badi video download nahi karta.
- Gemini free tier ke rate limits hain; users badhne par paid key lo.
- Users ki videos Google Gemini ko bheji jaati hain (processing ke baad Gemini se delete hoti hain) — apni privacy policy me ye likho.
- Ye code is sandbox me library ke saath run nahi kiya gaya (package install block tha); sirf syntax check hua hai. Pehle apne local machine par ek test run zaroor karo.

## Troubleshooting
| Problem | Wajah / Fix |
|---|---|
| "Telegram channel check nahi ho pa raha" | Bot channel ka admin nahi hai (Step 3) |
| `Missing env` error startup par | Koyeb me variables sahi naam se daale? |
| `RPC ... fail` logs | `schema.sql` run nahi hua, ya `SUPABASE_KEY` anon key hai |
| Bot jawab nahi deta (kuch ghante baad) | Free instance sleep — Option A ya B (upar) |
| Webhook mode me 404 health check | Health check ko TCP par karo |
