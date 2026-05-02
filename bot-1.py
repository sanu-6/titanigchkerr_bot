"""
╔══════════════════════════════════════════════╗
║   📸  Instagram Stats Telegram Bot           ║
║   🚂  Railway App Ready Version              ║
╚══════════════════════════════════════════════╝
"""

import logging
import asyncio
import json
import os
import random
import string
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode
import instaloader

# ═══════════════════════════════════════════════════════════
#  ⚙️  CONFIG — Set these in Railway Dashboard → Variables
# ═══════════════════════════════════════════════════════════

BOT_TOKEN        = os.environ.get("BOT_TOKEN",        "8351425853:AAG0Q6lIroNgzDAhJqPp08eN7zTXaKYTUow")
ADMIN_ID         = int(os.environ.get("ADMIN_ID",     "6198353113"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@your_channel")
CHANNEL_LINK     = os.environ.get("CHANNEL_LINK",     "https://t.me/+ACM_9BbOOtQ2ZTA9")

NEW_USER_CREDITS = 20
REFERRAL_CREDIT  = 1
COST_PER_CHECK   = 1
MAX_BATCH        = 10
DB_FILE          = "database.json"

# ════════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Database ─────────────────────────────────────────────────────────────────

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def get_user(db, user_id: int, username: str = ""):
    uid = str(user_id)
    if uid not in db["users"]:
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        db["users"][uid] = {
            "id": uid, "username": username,
            "credits": NEW_USER_CREDITS,
            "referral_code": ref_code,
            "referred_by": None, "referral_count": 0,
            "total_checks": 0,
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save_db(db)
    elif username:
        db["users"][uid]["username"] = username
    return db["users"][uid]

def save_user(db, user):
    db["users"][user["id"]] = user
    save_db(db)

# ─── Channel gate ─────────────────────────────────────────────────────────────

async def is_member(bot, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return m.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception:
        return False

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I Joined — Continue", callback_data="check_joined")],
    ])

# ─── Instagram scraper ────────────────────────────────────────────────────────

def _scrape_ig(username: str) -> dict:
    try:
        L = instaloader.Instaloader(
            download_pictures=False, download_videos=False,
            download_video_thumbnails=False, download_comments=False,
            save_metadata=False, compress_json=False, quiet=True,
        )
        profile = instaloader.Profile.from_username(L.context, username)
        posts_data = []
        for i, post in enumerate(profile.get_posts()):
            if i >= 10: break
            posts_data.append({
                "num": i + 1,
                "likes": post.likes,
                "comments": post.comments,
                "type": "🎬 Reel" if post.is_video else "📷 Photo",
                "date": post.date.strftime("%d %b %Y"),
            })
        return {
            "ok": True,
            "username": profile.username,
            "full_name": profile.full_name,
            "followers": profile.followers,
            "following": profile.followees,
            "total_posts": profile.mediacount,
            "is_private": profile.is_private,
            "posts": posts_data,
        }
    except instaloader.exceptions.ProfileNotExistsException:
        return {"ok": False, "error": "Profile not found ❌"}
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        return {"ok": False, "error": "Private profile 🔒"}
    except Exception as e:
        return {"ok": False, "error": f"Error: {str(e)[:80]}"}

async def fetch_ig(username: str) -> dict:
    return await asyncio.get_event_loop().run_in_executor(None, _scrape_ig, username)

# ─── Formatters ───────────────────────────────────────────────────────────────

def fmt(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)

def bar(likes, max_likes):
    if max_likes == 0: return "░░░░░░░░"
    f = round((likes / max_likes) * 8)
    return "█" * f + "░" * (8 - f)

def format_result(data, input_username=""):
    if not data["ok"]:
        return f"❌ @{input_username} — {data['error']}"
    u = data
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📸 *@{u['username']}*",
    ]
    if u['full_name']: lines.append(f"👤 {u['full_name']}")
    lines += [
        f"{'🔒 Private' if u['is_private'] else '🌐 Public'}",
        "",
        f"👥 Followers: *{fmt(u['followers'])}*",
        f"➡️  Following: *{fmt(u['following'])}*",
        f"📊 Total Posts: *{u['total_posts']}*",
    ]
    if u["posts"]:
        max_l = max(p["likes"] for p in u["posts"]) or 1
        avg_l = sum(p["likes"] for p in u["posts"]) // len(u["posts"])
        lines += [f"❤️  Avg Likes: *{fmt(avg_l)}*", "", "📋 *Recent Posts:*"]
        for p in u["posts"]:
            lines.append(
                f"  `#{p['num']}` {p['type']}  {p['date']}\n"
                f"  ❤️ *{fmt(p['likes'])}*  💬 {fmt(p['comments'])}\n"
                f"  {bar(p['likes'], max_l)}"
            )
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

# ════════════════════════════════════════════════════════════════
#   USER HANDLERS
# ════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = load_db()
    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text(
            "👋 *Welcome to IG Stats Bot!*\n\n📢 Join our channel first to use this bot:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=join_keyboard()
        )
        return
    u = get_user(db, user.id, user.username or "")
    if ctx.args:
        ref_code = ctx.args[0].upper()
        if u["referred_by"] is None:
            referrer = next((v for v in db["users"].values()
                             if v["referral_code"] == ref_code and v["id"] != str(user.id)), None)
            if referrer:
                u["referred_by"] = referrer["id"]
                u["credits"] += REFERRAL_CREDIT
                referrer["referral_count"] = referrer.get("referral_count", 0) + 1
                referrer["credits"] += REFERRAL_CREDIT
                save_user(db, referrer)
                try:
                    await ctx.bot.send_message(int(referrer["id"]),
                        f"🎉 *New referral!* +{REFERRAL_CREDIT} credit!\n💎 Balance: *{referrer['credits']}*",
                        parse_mode=ParseMode.MARKDOWN)
                except Exception: pass
    save_user(db, u)
    await update.message.reply_text(
        f"👋 Hello *{user.first_name}*!\n\n"
        f"💎 Credits: *{u['credits']}*\n"
        f"🔗 Ref Code: `{u['referral_code']}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📖 *HOW TO USE:*\n"
        f"Send usernames (1 per line, max 10):\n"
        f"```\nchristiano\ntherock\n```\n"
        f"Or: `/check username1 username2`\n\n"
        f"💡 1 check = 1 credit | /referral for free credits",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_credits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text("Join our channel first!", reply_markup=join_keyboard())
        return
    db = load_db()
    u = get_user(db, user.id, user.username or "")
    await update.message.reply_text(
        f"💎 *Your Credits: {u['credits']}*\n\n"
        f"📊 Total Checks: {u.get('total_checks', 0)}\n"
        f"🔗 Referrals: {u.get('referral_count', 0)}\n"
        f"📅 Joined: {u.get('joined_at','?')}",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_referral(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text("Join our channel first!", reply_markup=join_keyboard())
        return
    db = load_db()
    u = get_user(db, user.id, user.username or "")
    link = f"https://t.me/{ctx.bot.username}?start={u['referral_code']}"
    await update.message.reply_text(
        f"🔗 *Your Referral Link:*\n`{link}`\n\n"
        f"Code: `{u['referral_code']}`\n"
        f"Referred: *{u.get('referral_count',0)}* people\n"
        f"Earned: *{u.get('referral_count',0) * REFERRAL_CREDIT}* credits\n\n"
        f"Each referral = *+{REFERRAL_CREDIT} credit* for you! 🎁",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *COMMANDS:*\n\n"
        "/start — Welcome\n"
        "/credits — Your balance\n"
        "/referral — Earn free credits\n"
        "/check username — Check IG account\n\n"
        "*Or just send usernames (1 per line):*\n"
        "```\nusername1\nusername2\n```\n\n"
        f"💎 {NEW_USER_CREDITS} free credits on signup\n"
        f"📊 1 credit per IG check\n"
        f"🔗 +{REFERRAL_CREDIT} credit per referral",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text("Join our channel first!", reply_markup=join_keyboard())
        return
    if not ctx.args:
        await update.message.reply_text("Usage: `/check username1 username2`", parse_mode=ParseMode.MARKDOWN)
        return
    await process_usernames(update, ctx, list(ctx.args))

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_member(ctx.bot, user.id):
        await update.message.reply_text("Join our channel first!", reply_markup=join_keyboard())
        return
    text = update.message.text.strip()
    if text.startswith("/"): return
    usernames = list(dict.fromkeys([
        line.strip().lstrip("@") for line in text.replace(",", "\n").splitlines() if line.strip()
    ]))
    if usernames:
        await process_usernames(update, ctx, usernames)

async def process_usernames(update: Update, ctx: ContextTypes.DEFAULT_TYPE, usernames: list):
    user = update.effective_user
    db = load_db()
    u = get_user(db, user.id, user.username or "")
    if len(usernames) > MAX_BATCH:
        await update.message.reply_text(f"⚠️ Max {MAX_BATCH} at once. Using first {MAX_BATCH}.")
        usernames = usernames[:MAX_BATCH]
    cost = len(usernames) * COST_PER_CHECK
    if user.id != ADMIN_ID and u["credits"] < cost:
        link = f"https://t.me/{ctx.bot.username}?start={u['referral_code']}"
        await update.message.reply_text(
            f"❌ *Not enough credits!*\n\nNeed: *{cost}* | Have: *{u['credits']}*\n\n"
            f"🔗 Earn more — share your link:\n`{link}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    if user.id != ADMIN_ID:
        u["credits"] -= cost
        u["total_checks"] = u.get("total_checks", 0) + len(usernames)
        save_user(db, u)
    remaining = "∞" if user.id == ADMIN_ID else u["credits"]
    status = await update.message.reply_text(f"⏳ Checking *{len(usernames)}* account(s)...", parse_mode=ParseMode.MARKDOWN)
    results = await asyncio.gather(*[fetch_ig(un) for un in usernames])
    try: await status.delete()
    except Exception: pass
    for uname, result in zip(usernames, results):
        text = format_result(result, uname)
        try: await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception: await update.message.reply_text(text.replace("*","").replace("`",""))
        await asyncio.sleep(0.3)
    await update.message.reply_text(
        f"✅ Done! *{len(usernames)}* checked.\n💎 Credits left: *{remaining}*",
        parse_mode=ParseMode.MARKDOWN
    )

# ════════════════════════════════════════════════════════════════
#   ADMIN HANDLERS
# ════════════════════════════════════════════════════════════════

def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ Admin only.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper

@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    u_list = db["users"].values()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users", callback_data="admin_users"),
         InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast Help", callback_data="admin_broadcast"),
         InlineKeyboardButton("💎 Credits Help", callback_data="admin_add_credits")],
    ])
    await update.message.reply_text(
        f"⚙️ *Admin Panel*\n\n"
        f"👥 Users: *{len(db['users'])}*\n"
        f"📊 Checks: *{sum(u.get('total_checks',0) for u in u_list)}*\n"
        f"🔗 Referrals: *{sum(u.get('referral_count',0) for u in u_list)}*\n\n"
        f"*Commands:*\n"
        f"`/broadcast TEXT` — Message all users\n"
        f"`/addcredits ID AMT` — Add credits\n"
        f"`/removecredits ID AMT` — Remove credits\n"
        f"`/users` — List all users\n"
        f"`/stats` — Full statistics",
        parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )

@admin_only
async def cmd_addcredits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/addcredits USER_ID AMOUNT`", parse_mode=ParseMode.MARKDOWN)
        return
    db = load_db()
    tid, amt = ctx.args[0], int(ctx.args[1])
    if tid not in db["users"]:
        await update.message.reply_text("❌ User not found.")
        return
    db["users"][tid]["credits"] += amt
    save_db(db)
    await update.message.reply_text(f"✅ Added *{amt}* credits → `{tid}`\nBalance: *{db['users'][tid]['credits']}*", parse_mode=ParseMode.MARKDOWN)
    try: await ctx.bot.send_message(int(tid), f"🎁 Admin added *{amt}* credits!\n💎 Balance: *{db['users'][tid]['credits']}*", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass

@admin_only
async def cmd_removecredits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/removecredits USER_ID AMOUNT`", parse_mode=ParseMode.MARKDOWN)
        return
    db = load_db()
    tid, amt = ctx.args[0], int(ctx.args[1])
    if tid not in db["users"]:
        await update.message.reply_text("❌ User not found.")
        return
    db["users"][tid]["credits"] = max(0, db["users"][tid]["credits"] - amt)
    save_db(db)
    await update.message.reply_text(f"✅ Removed *{amt}* credits from `{tid}`\nBalance: *{db['users'][tid]['credits']}*", parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/broadcast Your message`", parse_mode=ParseMode.MARKDOWN)
        return
    msg = " ".join(ctx.args)
    db = load_db()
    sent = failed = 0
    s = await update.message.reply_text(f"📢 Sending to {len(db['users'])} users...")
    for uid in db["users"]:
        try:
            await ctx.bot.send_message(int(uid), f"📢 *Admin Message:*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception: failed += 1
    await s.edit_text(f"✅ Done! Sent: {sent} | Failed: {failed}")

@admin_only
async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    ul = list(db["users"].values())
    text = f"👥 *Users ({len(ul)} total — showing last 20):*\n\n"
    for u in ul[-20:]:
        text += f"🆔 `{u['id']}` @{u.get('username','?')} | 💎{u['credits']} | 📊{u.get('total_checks',0)} checks\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    ul = list(db["users"].values())
    top = max(ul, key=lambda u: u.get("total_checks", 0), default=None)
    await update.message.reply_text(
        f"📊 *Bot Stats*\n\n"
        f"👥 Users: *{len(ul)}*\n"
        f"📊 Checks: *{sum(u.get('total_checks',0) for u in ul)}*\n"
        f"🔗 Referrals: *{sum(u.get('referral_count',0) for u in ul)}*\n"
        f"💎 Credits: *{sum(u['credits'] for u in ul)}*\n"
        f"🏆 Top: `{top['id'] if top else 'N/A'}` ({top.get('total_checks',0) if top else 0} checks)",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "check_joined":
        if await is_member(ctx.bot, q.from_user.id):
            db = load_db()
            u = get_user(db, q.from_user.id, q.from_user.username or "")
            await q.message.edit_text(
                f"✅ *Welcome! You're verified!*\n\n💎 Credits: *{u['credits']}*\n\nSend me Instagram usernames to check!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await q.message.reply_text("❌ Not joined yet!", reply_markup=join_keyboard())
    elif q.data == "admin_users" and q.from_user.id == ADMIN_ID:
        db = load_db()
        ul = list(db["users"].values())[-10:]
        text = "👥 *Recent Users:*\n\n" + "".join(f"`{u['id']}` @{u.get('username','?')} 💎{u['credits']}\n" for u in ul)
        await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    elif q.data == "admin_broadcast" and q.from_user.id == ADMIN_ID:
        await q.message.reply_text("📢 Use:\n`/broadcast Your message here`", parse_mode=ParseMode.MARKDOWN)
    elif q.data == "admin_add_credits" and q.from_user.id == ADMIN_ID:
        await q.message.reply_text("💎 Use:\n`/addcredits USER_ID AMOUNT`\n\nExample:\n`/addcredits 987654321 50`", parse_mode=ParseMode.MARKDOWN)
    elif q.data == "admin_stats" and q.from_user.id == ADMIN_ID:
        db = load_db()
        await q.message.reply_text(f"📊 Users: {len(db['users'])} | Checks: {sum(u.get('total_checks',0) for u in db['users'].values())}")

# ════════════════════════════════════════════════════════════════
#   MAIN
# ════════════════════════════════════════════════════════════════

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: BOT_TOKEN not set!")
        print("   Set it in Railway Dashboard → Variables → BOT_TOKEN")
        return
    print(f"🤖 Bot starting... Admin={ADMIN_ID} Channel={CHANNEL_USERNAME}")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(CommandHandler("credits",       cmd_credits))
    app.add_handler(CommandHandler("referral",      cmd_referral))
    app.add_handler(CommandHandler("check",         cmd_check))
    app.add_handler(CommandHandler("admin",         cmd_admin))
    app.add_handler(CommandHandler("addcredits",    cmd_addcredits))
    app.add_handler(CommandHandler("removecredits", cmd_removecredits))
    app.add_handler(CommandHandler("broadcast",     cmd_broadcast))
    app.add_handler(CommandHandler("users",         cmd_users))
    app.add_handler(CommandHandler("stats",         cmd_stats))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot is live!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
